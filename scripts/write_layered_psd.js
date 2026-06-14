#!/usr/bin/env node
const fs = require("fs");
const path = require("path");
const { PNG } = require("pngjs");
const { writePsdBuffer } = require("ag-psd");

function usage() {
  console.error("Usage: node write_layered_psd.js <layer_manifest.json> <output.psd>");
  process.exit(2);
}

if (process.argv.length < 4) usage();

const manifestPath = path.resolve(process.argv[2]);
const outputPath = path.resolve(process.argv[3]);
const root = path.dirname(manifestPath);
const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));

function readPng(relPath) {
  const png = PNG.sync.read(fs.readFileSync(path.join(root, relPath)));
  return {
    width: png.width,
    height: png.height,
    data: new Uint8ClampedArray(png.data.buffer, png.data.byteOffset, png.data.byteLength),
  };
}

function findBounds(imageData) {
  const { width, height, data } = imageData;
  let left = width;
  let top = height;
  let right = -1;
  let bottom = -1;
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      if (data[(y * width + x) * 4 + 3] > 0) {
        if (x < left) left = x;
        if (x > right) right = x;
        if (y < top) top = y;
        if (y > bottom) bottom = y;
      }
    }
  }
  if (right < left || bottom < top) return null;
  return { left, top, right: right + 1, bottom: bottom + 1 };
}

function cropImageData(imageData, bounds) {
  const width = bounds.right - bounds.left;
  const height = bounds.bottom - bounds.top;
  const out = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y += 1) {
    const start = ((bounds.top + y) * imageData.width + bounds.left) * 4;
    out.set(imageData.data.subarray(start, start + width * 4), y * width * 4);
  }
  return { width, height, data: out };
}

function composePreview() {
  const width = manifest.width;
  const height = manifest.height;
  const data = new Uint8ClampedArray(width * height * 4);
  for (let i = 0; i < data.length; i += 4) {
    data[i] = 255;
    data[i + 1] = 255;
    data[i + 2] = 255;
    data[i + 3] = 255;
  }

  for (const layer of [...manifest.layers].reverse()) {
    if (layer.visible === false) continue;
    const image = readPng(layer.file);
    const opacity = layer.opacity == null ? 1 : Number(layer.opacity);
    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        const i = (y * width + x) * 4;
        const a = (image.data[i + 3] / 255) * opacity;
        if (a <= 0) continue;
        data[i] = Math.round(image.data[i] * a + data[i] * (1 - a));
        data[i + 1] = Math.round(image.data[i + 1] * a + data[i + 1] * (1 - a));
        data[i + 2] = Math.round(image.data[i + 2] * a + data[i + 2] * (1 - a));
        data[i + 3] = 255;
      }
    }
  }
  return { width, height, data };
}

function color(rgb) {
  const value = rgb || [20, 42, 25];
  return { r: value[0], g: value[1], b: value[2] };
}

function makeTextData(spec, bounds) {
  if (!spec) return undefined;
  return {
    text: spec.text,
    transform: [1, 0, 0, 1, spec.x || bounds.left, spec.y || bounds.top],
    antiAlias: "smooth",
    orientation: "horizontal",
    top: bounds.top,
    left: bounds.left,
    bottom: bounds.bottom,
    right: bounds.right,
    shapeType: "point",
    style: {
      font: { name: spec.font || "Helvetica" },
      fontSize: spec.fontSize || 24,
      tracking: spec.tracking || 0,
      fillColor: color(spec.color),
      fillFlag: true,
    },
    paragraphStyle: { justification: "center" },
    styleRuns: [
      {
        length: spec.text.length,
        style: {
          font: { name: spec.font || "Helvetica" },
          fontSize: spec.fontSize || 24,
          tracking: spec.tracking || 0,
          fillColor: color(spec.color),
          fillFlag: true,
        },
      },
    ],
    paragraphStyleRuns: [{ length: spec.text.length, style: { justification: "center" } }],
  };
}

function buildLayer(layerSpec) {
  const full = readPng(layerSpec.file);
  const bounds = findBounds(full);
  if (!bounds) {
    return {
      name: layerSpec.name,
      hidden: layerSpec.visible === false,
      opacity: layerSpec.opacity == null ? 1 : Number(layerSpec.opacity),
    };
  }
  const layer = {
    name: layerSpec.name,
    left: bounds.left,
    top: bounds.top,
    imageData: cropImageData(full, bounds),
    hidden: layerSpec.visible === false,
    opacity: layerSpec.opacity == null ? 1 : Number(layerSpec.opacity),
  };
  const text = makeTextData(layerSpec.text, bounds);
  if (text) layer.text = text;
  return layer;
}

let composite;
if (manifest.preview && fs.existsSync(path.join(root, manifest.preview))) {
  composite = readPng(manifest.preview);
} else {
  composite = composePreview();
}

const psd = {
  width: manifest.width,
  height: manifest.height,
  imageData: composite,
  children: manifest.layers.map(buildLayer),
};

fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, writePsdBuffer(psd, { useImageData: true, generateThumbnail: false }));
console.log(outputPath);
