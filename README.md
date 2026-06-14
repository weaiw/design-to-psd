# design-to-psd

`design-to-psd` is a Codex Skill for rebuilding a flat design image into a layered PSD-compatible handoff.

It is intended for posters, covers, screenshots, KV images, social media graphics, and other single-image visual references where you need a practical editable reconstruction rather than the original source file.

## What It Produces

- A layered `.psd` file.
- A `preview.png` rendered from the generated layers.
- A `layers/` folder containing transparent PNG layer assets.
- A `layer_manifest.json` file describing PSD layer order, visibility, opacity, and optional text metadata.

## How It Works

The workflow is code-based and does not require Photoshop:

1. Use Python, Pillow, and NumPy to crop/extract bitmap elements, build soft masks, recreate text previews, and generate layer PNGs.
2. Use Node.js, `ag-psd`, and `pngjs` to package those transparent PNG layers into a PSD.
3. Validate the PSD by reading it back and visually checking the preview.

The Skill is intentionally not a slicer. It rejects large rectangular crop bands by default because a useful PSD should rebuild backgrounds, text, line art, badges, and simple shapes as editable layers. Bitmap extraction is reserved for complex subjects such as people, products, food, illustrations, handwriting, logos, or textured objects.

## Install as a Codex Skill

Clone the repo and copy it into your Codex skills directory:

```bash
git clone https://github.com/weaiw/design-to-psd.git
mkdir -p "$HOME/.codex/skills"
cp -R ./design-to-psd "$HOME/.codex/skills/design-to-psd"
```

`$HOME/.codex/skills` means the installing user's local Codex skills directory. It is not a maintainer-specific path.

Then invoke it with:

```text
Use $design-to-psd to turn this design image into a layered PSD with preview PNGs.
```

## Script Usage

Install Node dependencies in the working project:

```bash
npm install
```

Install Python dependencies in your environment if needed:

```bash
python3 -m pip install Pillow numpy
```

Generate layer PNGs and a manifest:

```bash
python3 scripts/rebuild_poster_layers.py source.png out \
  --crop-layer "main_subject|35,622,785,965|foreground|1" \
  --text-layer "subtitle|TRADITIONAL FESTIVAL|400,614|24|times|20,42,25|7|0"
```

Write the PSD:

```bash
node scripts/write_layered_psd.js out/layer_manifest.json out/recreated.psd
```

## Limits

This does not recover the original design source file. Complex illustration, photography, gradients, lighting, and custom lettering are approximated with extracted bitmap layers or reconstructed layers. Text layers include raster previews plus PSD text metadata where possible, but PSD text compatibility varies by app.

If you explicitly need a sliced-reference PSD, pass `--allow-rect-slices`. Do not use that mode for normal design reconstruction.

## License

MIT
