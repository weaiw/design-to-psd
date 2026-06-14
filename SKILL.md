---
name: design-to-psd
description: Convert a flat design image, poster, cover, screenshot, KV, social media graphic, or visual reference into a layered editable PSD with transparent PNG layer assets and a preview render. Use when the user asks to "还原成 PSD", "海报还原 PSD", "设计稿转 PSD", recreate a design as PSD, produce editable Photoshop layers from a single image, or create a PSD-compatible handoff without controlling Photoshop.
---

# Design to PSD

Turn a flat design/reference image into a practical layered PSD. The goal is a usable editable reconstruction, not perfect recovery of the original source file.

## Deliverables

Always produce:

- `recreated.psd` or a task-specific PSD name.
- `preview.png` rendered from the generated layers.
- `layers/` with transparent PNGs for each layer.
- A short task-local note explaining which layers are editable text/vector-like rebuilds and which are extracted bitmap patches.

## Workflow

1. Inspect the source image dimensions and identify layer groups: hidden reference, background, extracted photo/illustration patches, editable text, recreated shapes/line art, overlays/effects.
2. Decide which elements are reconstructed and which are extracted.
   - Reconstruct global backgrounds, text, solid shapes, line art, badges, separators, shadows, and gradients as independent layers.
   - Extract bitmap patches only for complex subjects such as product photos, people, food, illustrations, handwriting, logos, and textured objects.
   - Do not slice the source into rectangular bands or tiles to approximate the layout.
3. Create a task output directory. Copy the bundled scripts there if custom edits are needed:
   - `scripts/rebuild_poster_layers.py`
   - `scripts/write_layered_psd.js`
4. Generate layer PNGs and `layer_manifest.json`.
   - Use raster text previews for visual fidelity.
   - Also include text metadata in the manifest for layers that should open as editable text in PSD-capable apps.
   - Keep a hidden semi-transparent source image layer named `reference_hidden`.
5. Write the PSD from the manifest.
6. Validate:
   - `file recreated.psd`
   - Read back with `ag-psd` and report canvas size, layer count, text layers, and hidden reference layer.
   - Visually inspect `preview.png`; iterate on masks/crops before final delivery.
   - Reject outputs with visible rectangular seams, tiled source chunks, or large source-background rectangles around extracted elements.

## Scripts

Use `scripts/rebuild_poster_layers.py` as a baseline generator. It supports:

- hidden source reference layer,
- blurred/soft background layer,
- crop layers with `rect`, `soft-rect`, `ellipse`, or `foreground` masks,
- centered raster text layers with PSD text metadata,
- rounded label layers,
- manifest and preview composition.

By default the script runs an anti-slicing QA pass. It rejects large `rect`/`soft-rect` crop bands and excessive rectangular crop area because those produce the common bad result where the design is cut into blocks. Use `--allow-rect-slices` only when the user explicitly wants a sliced reference PSD rather than a reconstructed editable PSD.

Example:

```bash
python3 scripts/rebuild_poster_layers.py source.png out \
  --crop-layer "main_subject|35,622,785,965|foreground" \
  --text-layer "subtitle|中 / 国 / 传 / 统 / 节 / 日|400,563|38|Songti|18,45,24|8|0" \
  --label-layer "date|农历五月初五|322,1288,478,1320|18"
```

Use `scripts/write_layered_psd.js` to turn the manifest into PSD:

```bash
node scripts/write_layered_psd.js out/layer_manifest.json out/recreated.psd
```

If `ag-psd` or `pngjs` is missing in the active project, install them locally:

```bash
npm install ag-psd pngjs
```

If `Pillow` or `numpy` is missing, install them in the active Python environment.

## Reconstruction Guidance

- Do not claim exact PSD recovery from a flat image. State that bitmap-heavy regions are extracted/rebuilt approximations.
- Never deliver a PSD that is just the original image cut into rectangular chunks. That is a failed reconstruction.
- Do not use crop layers for text, global background, simple shapes, decorative rules, labels, or flat color/gradient areas; rebuild those layers.
- Prefer editable text metadata plus a raster fallback image for each text layer; PSD text writing support varies by app.
- For complex subjects, create a rough extracted patch first, inspect the preview, then tighten alpha thresholds and spatial masks.
- If a crop layer still includes a visible rectangular background block, replace it with a tighter foreground mask or rebuild that area.
- Name layers by purpose, not generic numbers: `title_text`, `main_subject_extracted`, `background_gradient`, `decorative_lines`.
- Keep the original reference layer hidden but present so another designer can align edits.
- For copyrighted third-party designs, recreate structure/style for legitimate editing or learning; avoid presenting it as the original source PSD.

## References

Read `references/layer_manifest.md` when you need to manually write or patch `layer_manifest.json`.
