#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


FONT_CANDIDATES = {
    "songti": [
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
    ],
    "heiti": [
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
    ],
    "times": [
        "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
        "/System/Library/Fonts/Times.ttc",
    ],
    "helvetica": [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNS.ttf",
    ],
}


def slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")
    return text[:60] or "layer"


def parse_box(value: str) -> tuple[int, int, int, int]:
    parts = [int(float(p.strip())) for p in value.split(",")]
    if len(parts) != 4:
        raise ValueError(f"Expected x0,y0,x1,y1, got {value!r}")
    return tuple(parts)


def parse_point(value: str) -> tuple[int, int]:
    parts = [int(float(p.strip())) for p in value.split(",")]
    if len(parts) != 2:
        raise ValueError(f"Expected x,y, got {value!r}")
    return tuple(parts)


def parse_rgb(value: str) -> tuple[int, int, int]:
    parts = [int(float(p.strip())) for p in value.split(",")]
    if len(parts) != 3:
        raise ValueError(f"Expected r,g,b, got {value!r}")
    return tuple(max(0, min(255, p)) for p in parts)


def rgba(width: int, height: int) -> Image.Image:
    return Image.new("RGBA", (width, height), (0, 0, 0, 0))


def choose_font(name: str, size: int) -> ImageFont.ImageFont:
    key = name.lower().strip()
    candidates = FONT_CANDIDATES.get(key, [])
    if Path(name).exists():
        candidates = [name] + candidates
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    try:
        return ImageFont.truetype(name, size)
    except Exception:
        return ImageFont.load_default()


def save_layer(out_dir: Path, manifest: dict, name: str, image: Image.Image, visible=True, opacity=1.0, text=None):
    layers_dir = out_dir / "layers"
    path = layers_dir / f"{len(manifest['layers']):02d}_{slug(name)}.png"
    image.save(path)
    spec = {
        "name": name,
        "file": str(path.relative_to(out_dir)),
        "visible": bool(visible),
        "opacity": float(opacity),
    }
    if text:
        spec["text"] = text
    manifest["layers"].append(spec)


def foreground_alpha(crop: Image.Image, blur=3.0) -> Image.Image:
    arr = np.array(crop.convert("RGBA")).astype(np.float32)
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    mx = np.maximum.reduce([r, g, b])
    mn = np.minimum.reduce([r, g, b])
    saturation = mx - mn
    darkness = 192 - mx
    edge_distance = np.sqrt((r - np.median(r)) ** 2 + (g - np.median(g)) ** 2 + (b - np.median(b)) ** 2)
    alpha = np.maximum.reduce([(saturation - 32) * 6.0, darkness * 2.3, (edge_distance - 36) * 3.0])
    alpha = np.clip((alpha - 22) * 1.45, 0, 255).astype(np.uint8)
    return Image.fromarray(alpha, "L").filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(blur))


def crop_layer(source: Image.Image, box, mask_kind: str, canvas_size, opacity=1.0) -> Image.Image:
    crop = source.crop(box).convert("RGBA")
    w, h = crop.size
    mask = Image.new("L", (w, h), 255)
    if mask_kind == "soft-rect":
        mask = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(mask)
        pad = max(8, int(min(w, h) * 0.05))
        d.rounded_rectangle((pad, pad, w - pad, h - pad), radius=pad, fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(pad))
    elif mask_kind == "ellipse":
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, w, h), fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(max(4, int(min(w, h) * 0.03))))
    elif mask_kind == "foreground":
        mask = foreground_alpha(crop)
    elif mask_kind != "rect":
        raise ValueError(f"Unknown mask kind: {mask_kind}")
    if opacity < 1:
        mask = mask.point(lambda p: int(p * opacity))
    crop.putalpha(mask)
    layer = rgba(*canvas_size)
    layer.alpha_composite(crop, (box[0], box[1]))
    return layer


def validate_crop_plan(crop_specs: list[str], canvas_size: tuple[int, int], allow_rect_slices: bool = False):
    if allow_rect_slices:
        return

    width, height = canvas_size
    canvas_area = width * height
    rect_area = 0
    rect_count = 0
    problems = []

    for spec in crop_specs:
        fields = spec.split("|")
        if len(fields) < 3:
            continue
        name = fields[0]
        box = parse_box(fields[1])
        mask = fields[2]
        w = max(0, box[2] - box[0])
        h = max(0, box[3] - box[1])
        area_ratio = (w * h) / canvas_area if canvas_area else 0

        if mask in {"rect", "soft-rect"}:
            rect_count += 1
            rect_area += w * h
            if area_ratio > 0.08:
                problems.append(f"{name}: {mask} crop covers {area_ratio:.1%} of canvas")
            if w / width > 0.55 and h / height > 0.06:
                problems.append(f"{name}: wide rectangular band detected")
            if h / height > 0.30 and w / width > 0.20:
                problems.append(f"{name}: tall rectangular chunk detected")

    if rect_count > 4:
        problems.append(f"{rect_count} rectangular crop layers detected")
    if rect_area / canvas_area > 0.24:
        problems.append(f"rectangular crops cover {rect_area / canvas_area:.1%} of the canvas")

    if problems:
        detail = "\n  - ".join(problems)
        raise SystemExit(
            "Anti-slicing QA failed. This looks like a tiled/chunked source reconstruction, "
            "not an editable design-to-PSD rebuild.\n"
            f"  - {detail}\n"
            "Rebuild backgrounds, text, simple shapes, and line art as separate layers. "
            "Use foreground/ellipse masks only for complex bitmap subjects. "
            "Pass --allow-rect-slices only for an explicit sliced-reference PSD."
        )


def make_background(source: Image.Image) -> Image.Image:
    small = source.convert("RGBA").resize((max(1, source.width // 12), max(1, source.height // 12)), Image.Resampling.BILINEAR)
    bg = small.resize(source.size, Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(28))
    veil = Image.new("RGBA", source.size, (245, 248, 242, 125))
    bg.alpha_composite(veil)
    return bg


def draw_centered_text(image, text, center, font_obj, fill, tracking=0, line_gap=0):
    draw = ImageDraw.Draw(image)
    lines = text.split("\\n")
    metrics = []
    for line in lines:
        width = sum(draw.textlength(ch, font=font_obj) for ch in line) + tracking * max(0, len(line) - 1)
        bbox = draw.textbbox((0, 0), line or " ", font=font_obj)
        metrics.append((line, width, bbox[3] - bbox[1]))
    block_h = sum(m[2] for m in metrics) + line_gap * max(0, len(metrics) - 1)
    y = center[1] - block_h / 2
    for line, width, height in metrics:
        x = center[0] - width / 2
        for ch in line:
            draw.text((x, y), ch, font=font_obj, fill=fill)
            x += draw.textlength(ch, font=font_obj) + tracking
        y += height + line_gap


def text_layer(spec: str, canvas_size) -> tuple[str, Image.Image, dict]:
    fields = spec.split("|")
    if len(fields) < 8:
        raise ValueError("text layer spec: name|text|x,y|size|font|r,g,b|tracking|line_gap")
    name, text, point_s, size_s, font_name, rgb_s, tracking_s, line_gap_s = fields[:8]
    point = parse_point(point_s)
    size = int(float(size_s))
    rgb = parse_rgb(rgb_s)
    tracking = int(float(tracking_s))
    line_gap = int(float(line_gap_s))
    image = rgba(*canvas_size)
    draw_centered_text(image, text.replace("\\\\n", "\\n"), point, choose_font(font_name, size), (*rgb, 245), tracking, line_gap)
    text_meta = {
        "text": text.replace("\\\\n", "\\n"),
        "font": {"songti": "Songti SC", "heiti": "Heiti SC", "times": "Times New Roman"}.get(font_name.lower(), font_name),
        "fontSize": size,
        "x": point[0],
        "y": point[1],
        "color": list(rgb),
        "tracking": tracking * 20,
    }
    return name, image, text_meta


def label_layer(spec: str, canvas_size) -> tuple[str, Image.Image]:
    fields = spec.split("|")
    if len(fields) < 5:
        raise ValueError("label layer spec: name|text|x0,y0,x1,y1|size|font")
    name, text, box_s, size_s, font_name = fields[:5]
    rgb = parse_rgb(fields[5]) if len(fields) > 5 else (30, 60, 35)
    box = parse_box(box_s)
    image = rgba(*canvas_size)
    d = ImageDraw.Draw(image)
    d.rounded_rectangle(box, radius=max(4, (box[3] - box[1]) // 2), outline=(*rgb, 220), width=1)
    center = ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2)
    draw_centered_text(image, text, center, choose_font(font_name, int(float(size_s))), (*rgb, 240), 1, 0)
    return name, image


def compose(out_dir: Path, manifest: dict) -> Image.Image:
    preview = Image.new("RGBA", (manifest["width"], manifest["height"]), (255, 255, 255, 255))
    for layer in reversed(manifest["layers"]):
        if not layer.get("visible", True):
            continue
        image = Image.open(out_dir / layer["file"]).convert("RGBA")
        opacity = layer.get("opacity", 1.0)
        if opacity < 1:
            image.putalpha(image.getchannel("A").point(lambda p: int(p * opacity)))
        preview.alpha_composite(image)
    return preview


def main():
    parser = argparse.ArgumentParser(description="Rebuild a flat design into PSD-ready layer PNGs.")
    parser.add_argument("source")
    parser.add_argument("out_dir")
    parser.add_argument("--crop-layer", action="append", default=[], help="name|x0,y0,x1,y1|rect|opacity")
    parser.add_argument("--text-layer", action="append", default=[], help="name|text|x,y|size|font|r,g,b|tracking|line_gap")
    parser.add_argument("--label-layer", action="append", default=[], help="name|text|x0,y0,x1,y1|size|font|r,g,b")
    parser.add_argument("--no-background", action="store_true")
    parser.add_argument("--allow-rect-slices", action="store_true", help="Disable anti-slicing QA for explicit sliced-reference PSDs.")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    layers_dir = out_dir / "layers"
    layers_dir.mkdir(parents=True, exist_ok=True)
    for path in layers_dir.glob("*.png"):
        path.unlink()

    source = Image.open(args.source).convert("RGBA")
    source.save(out_dir / "source.png")
    manifest = {"width": source.width, "height": source.height, "preview": "preview.png", "layers": []}
    canvas_size = (source.width, source.height)
    validate_crop_plan(args.crop_layer, canvas_size, allow_rect_slices=args.allow_rect_slices)

    reference = source.copy()
    reference.putalpha(reference.getchannel("A").point(lambda p: int(p * 0.35)))
    save_layer(out_dir, manifest, "reference_hidden", reference, visible=False)

    for spec in args.text_layer:
        name, image, meta = text_layer(spec, canvas_size)
        save_layer(out_dir, manifest, name, image, text=meta)

    for spec in args.label_layer:
        name, image = label_layer(spec, canvas_size)
        save_layer(out_dir, manifest, name, image)

    for spec in args.crop_layer:
        fields = spec.split("|")
        if len(fields) < 3:
            raise ValueError("crop layer spec: name|x0,y0,x1,y1|mask|opacity")
        name = fields[0]
        box = parse_box(fields[1])
        mask = fields[2]
        opacity = float(fields[3]) if len(fields) > 3 else 1.0
        save_layer(out_dir, manifest, name, crop_layer(source, box, mask, canvas_size, opacity=opacity))

    if not args.no_background:
        save_layer(out_dir, manifest, "soft_background", make_background(source))

    preview = compose(out_dir, manifest)
    preview.convert("RGB").save(out_dir / "preview.png", quality=95)
    (out_dir / "layer_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))

    note = [
        "# Design to PSD Reconstruction Notes",
        "",
        "- `reference_hidden` is a hidden alignment/reference layer.",
        "- Text layers include raster previews and PSD text metadata where possible.",
        "- Crop layers are bitmap extractions from the flat source image.",
        "- Inspect `preview.png` and iterate masks/crops before final handoff.",
    ]
    (out_dir / "NOTES.md").write_text("\\n".join(note) + "\\n")


if __name__ == "__main__":
    main()
