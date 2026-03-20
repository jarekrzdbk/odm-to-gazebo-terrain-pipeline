#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import numpy as np
import tifffile
from PIL import Image


def read_geotiff(path: Path):
    with tifffile.TiffFile(path) as tf:
        page = tf.pages[0]
        arr = page.asarray()

        pixel_scale_x = 1.0
        pixel_scale_y = 1.0
        nodata = None

        scale_tag = page.tags.get("ModelPixelScaleTag")
        if scale_tag is not None:
            vals = scale_tag.value
            if len(vals) >= 2:
                pixel_scale_x = float(vals[0])
                pixel_scale_y = float(vals[1])

        nodata_tag = page.tags.get("GDAL_NODATA")
        if nodata_tag is not None:
            raw = nodata_tag.value
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="ignore")
            raw = str(raw).strip().strip("\x00")
            try:
                nodata = float(raw)
            except ValueError:
                nodata = None

    return arr, abs(pixel_scale_x), abs(pixel_scale_y), nodata


def normalize_to_uint(arr: np.ndarray, bits: int, nodata):
    arr = arr.astype(np.float32)

    valid = np.isfinite(arr)
    if nodata is not None:
        if np.isnan(nodata):
            valid &= ~np.isnan(arr)
        else:
            valid &= arr != nodata

    if not valid.any():
        raise ValueError("Raster contains no valid values")

    valid_vals = arr[valid]

    z_min = float(valid_vals.min())
    z_max = float(valid_vals.max())

    if z_max <= z_min:
        out = np.zeros_like(arr, dtype=np.uint8 if bits == 8 else np.uint16)
        return out, z_min, z_max, valid

    maxv = 255.0 if bits == 8 else 65535.0
    scaled = np.zeros_like(arr, dtype=np.float32)
    scaled[valid] = (arr[valid] - z_min) / (z_max - z_min)
    out = np.clip(np.round(scaled * maxv), 0, maxv)
    out = out.astype(np.uint8 if bits == 8 else np.uint16)

    if not valid.all():
        fill = int(out[valid].min()) if valid.any() else 0
        out[~valid] = fill

    return out, z_min, z_max, valid


def next_pow2_plus_1(n: int) -> int:
    p = 1
    while p + 1 < n:
        p *= 2
    return p + 1


def clamp_pow2_plus_1(n: int, max_side: int) -> int:
    valid = []
    p = 1
    while p + 1 <= max_side:
        valid.append(p + 1)
        p *= 2

    if not valid:
        raise ValueError("max_side must be >= 2")

    for v in reversed(valid):
        if v <= n:
            return v

    return valid[0]


def resize_preserve_aspect(img: np.ndarray, target_side: int):
    h, w = img.shape
    scale = min(target_side / h, target_side / w)

    new_h = max(1, int(round(h * scale)))
    new_w = max(1, int(round(w * scale)))

    pil = Image.fromarray(img)
    pil = pil.resize((new_w, new_h), resample=Image.Resampling.BILINEAR)

    return np.array(pil), new_w, new_h


def pad_to_square(img: np.ndarray, side: int):
    h, w = img.shape
    fill = int(img.min()) if img.size else 0

    square = np.full((side, side), fill, dtype=img.dtype)

    top = (side - h) // 2
    left = (side - w) // 2
    square[top:top + h, left:left + w] = img

    return square, left, top


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Input GeoTIFF, e.g. odm_dem/dsm.tif")
    ap.add_argument("--out-dir", required=True, help="Output terrain directory")
    ap.add_argument("--primary-format", default="8", choices=["8", "16"])
    ap.add_argument("--max-side", type=int, default=2049)
    ap.add_argument("--flip-y", type=int, default=1)
    args = ap.parse_args()

    input_path = Path(args.input).resolve()
    out_dir = Path(args.out_dir).resolve()

    if not input_path.exists():
        raise FileNotFoundError(f"Missing input GeoTIFF: {input_path}")

    out_dir.mkdir(parents=True, exist_ok=True)

    arr, pixel_scale_x, pixel_scale_y, nodata = read_geotiff(input_path)
    if arr.ndim != 2:
        raise ValueError(f"Expected single-band raster, got shape {arr.shape}")

    h0, w0 = arr.shape
    world_width = float(w0) * pixel_scale_x
    world_height = float(h0) * pixel_scale_y

    arr8, z_min, z_max, _ = normalize_to_uint(arr, 8, nodata)
    arr16, _, _, _ = normalize_to_uint(arr, 16, nodata)

    target_side = next_pow2_plus_1(max(h0, w0))
    if target_side > args.max_side:
        target_side = clamp_pow2_plus_1(target_side, args.max_side)

    arr8_resized, new_w, new_h = resize_preserve_aspect(arr8, target_side)
    arr16_resized, _, _ = resize_preserve_aspect(arr16, target_side)

    sq8, left, top = pad_to_square(arr8_resized, target_side)
    sq16, _, _ = pad_to_square(arr16_resized, target_side)

    if args.flip_y:
        sq8 = np.flipud(sq8)
        sq16 = np.flipud(sq16)

    heightmap8 = out_dir / "heightmap8.png"
    heightmap16 = out_dir / "heightmap16.png"
    primary = out_dir / "heightmap.png"
    meta_path = out_dir / "terrain_meta.json"

    Image.fromarray(sq8).save(heightmap8)
    Image.fromarray(sq16).save(heightmap16)

    if args.primary_format == "8":
        Image.fromarray(sq8).save(primary)
        primary_bits = 8
    else:
        Image.fromarray(sq16).save(primary)
        primary_bits = 16

    meta = {
        "source_file": str(input_path),
        "width_m": world_width,
        "height_m": world_height,
        "world_width": world_width,
        "world_height": world_height,
        "pixel_scale_x": pixel_scale_x,
        "pixel_scale_y": pixel_scale_y,
        "z_min": z_min,
        "z_max": z_max,
        "z_range_m": max(z_max - z_min, 1.0),
        "world_height_range": max(z_max - z_min, 1.0),
        "original_width_px": int(w0),
        "original_height_px": int(h0),
        "resized_width_px": int(new_w),
        "resized_height_px": int(new_h),
        "heightmap_size_px": int(target_side),
        "pad_left_px": int(left),
        "pad_top_px": int(top),
        "primary_bits": primary_bits,
        "flip_y": int(args.flip_y),
        "nodata": nodata,
    }

    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"Wrote {heightmap8}")
    print(f"Wrote {heightmap16}")
    print(f"Wrote {primary} ({primary_bits}-bit)")
    print(f"Wrote {meta_path}")
    print(f"Heightmap size: {target_side} x {target_side}")
    print(f"World size: {world_width:.3f} m x {world_height:.3f} m")
    print(f"Elevation range: {max(z_max - z_min, 1.0):.3f} m")


if __name__ == "__main__":
    main()
