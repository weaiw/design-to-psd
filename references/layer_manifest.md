# Layer Manifest

`layer_manifest.json` is the handoff between layer generation and PSD writing.

Minimal shape:

```json
{
  "width": 800,
  "height": 1422,
  "preview": "preview.png",
  "layers": [
    {
      "name": "reference_hidden",
      "file": "layers/00_reference_hidden.png",
      "visible": false,
      "opacity": 1
    },
    {
      "name": "subtitle_text",
      "file": "layers/01_subtitle_text.png",
      "visible": true,
      "opacity": 1,
      "text": {
        "text": "TRADITIONAL FESTIVAL",
        "font": "Times New Roman",
        "fontSize": 24,
        "x": 400,
        "y": 625,
        "color": [20, 42, 25],
        "tracking": 180
      }
    }
  ]
}
```

Layer order is top-to-bottom as it should appear in Photoshop. Preview composition should draw layers in reverse order. `write_layered_psd.js` also reverses this list at PSD serialization time because PSD writer order is opposite to the layer panel order shown by Photoshop/Photopea.

Fields:

- `width`, `height`: PSD canvas size in pixels.
- `preview`: optional preview image relative to the manifest directory. If absent, `write_layered_psd.js` composites visible layers.
- `layers[].name`: PSD layer name.
- `layers[].file`: transparent PNG path relative to the manifest directory.
- `layers[].visible`: false writes a hidden layer.
- `layers[].opacity`: 0 to 1.
- `layers[].text`: optional PSD text metadata. Keep the PNG raster fallback even when this exists.

Text metadata:

- `text`: content.
- `font`: Photoshop font display name. Common safe values: `Songti SC`, `Times New Roman`, `Helvetica`.
- `fontSize`: point/pixel-like size.
- `x`, `y`: text transform origin.
- `color`: RGB array.
- `tracking`: Photoshop-style tracking value; rough, not guaranteed exact.
