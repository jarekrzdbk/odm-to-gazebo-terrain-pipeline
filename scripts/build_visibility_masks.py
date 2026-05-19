#!/usr/bin/env python3
import argparse, json
from pathlib import Path
import numpy as np
from PIL import Image
import tifffile, yaml

def read_geotiff(path: Path):
    with tifffile.TiffFile(path) as tf:
        page = tf.pages[0]; arr = page.asarray().astype(np.float32)
        pixel_scale_x = pixel_scale_y = 1.0; nodata = None
        scale_tag = page.tags.get("ModelPixelScaleTag")
        if scale_tag is not None:
            vals = scale_tag.value
            if len(vals) >= 2: pixel_scale_x, pixel_scale_y = float(vals[0]), float(vals[1])
        nodata_tag = page.tags.get("GDAL_NODATA")
        if nodata_tag is not None:
            raw = nodata_tag.value
            if isinstance(raw, bytes): raw = raw.decode("utf-8", errors="ignore")
            raw = str(raw).strip().strip("\x00")
            try: nodata = float(raw)
            except ValueError: nodata = None
    valid = np.isfinite(arr)
    if nodata is not None: valid &= arr != nodata
    return arr, abs(pixel_scale_x), abs(pixel_scale_y), valid

def world_to_grid(x_m, y_m, width_m, height_m, px, py, rows, cols):
    col = int(round((x_m + 0.5 * width_m) / px)); row_from_bottom = int(round((y_m + 0.5 * height_m) / py)); row = rows - 1 - row_from_bottom
    return np.clip(row, 0, rows - 1), np.clip(col, 0, cols - 1)

def bresenham(r0, c0, r1, c1):
    points = []; dr, dc = abs(r1-r0), abs(c1-c0); sr = 1 if r0 < r1 else -1; sc = 1 if c0 < c1 else -1; err = dc - dr; r, c = r0, c0
    while True:
        points.append((r,c))
        if r == r1 and c == c1: break
        e2 = 2 * err
        if e2 > -dr: err -= dr; c += sc
        if e2 < dc: err += dc; r += sr
    return points

def is_visible(dem, line_pts, z0, z1):
    if len(line_pts) <= 1: return True
    total = len(line_pts) - 1
    for i, (r, c) in enumerate(line_pts[1:-1], start=1):
        alpha = i / total; z_line = (1.0 - alpha) * z0 + alpha * z1
        if dem[r, c] > z_line: return False
    return True

def load_map_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))

def save_mask_yaml(ref_yaml: dict, image_name: str, out_yaml: Path):
    data = {"image": image_name, "mode": ref_yaml.get("mode", "trinary"), "resolution": ref_yaml["resolution"], "origin": ref_yaml["origin"], "negate": 0, "occupied_thresh": 0.65, "free_thresh": 0.196}
    out_yaml.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", required=True); ap.add_argument("--obs-x-m", type=float, required=True); ap.add_argument("--obs-y-m", type=float, required=True); ap.add_argument("--obs-height-m", type=float, default=2.0); ap.add_argument("--target-height-m", type=float, default=0.5); ap.add_argument("--max-range-m", type=float, default=300.0); ap.add_argument("--map-yaml", required=True); ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    dem, px, py, valid = read_geotiff(Path(args.dem)); rows, cols = dem.shape; width_m, height_m = cols * px, rows * py
    obs_r, obs_c = world_to_grid(args.obs_x_m, args.obs_y_m, width_m, height_m, px, py, rows, cols)
    ref_yaml = load_map_yaml(Path(args.map_yaml)); out_dir = Path(args.out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    vis_mask = np.zeros_like(dem, dtype=bool); radio_speed = np.zeros_like(dem, dtype=np.uint8)
    z0 = float(dem[obs_r, obs_c] + args.obs_height_m); max_cells = max(1, int(round(args.max_range_m / min(px, py))))
    for r in range(rows):
        for c in range(cols):
            if not valid[r, c]: continue
            dr, dc = r - obs_r, c - obs_c
            if dr * dr + dc * dc > max_cells * max_cells: continue
            z1 = float(dem[r, c] + args.target_height_m); pts = bresenham(obs_r, obs_c, r, c); visible = is_visible(dem, pts, z0, z1)
            vis_mask[r, c] = visible; radio_speed[r, c] = 90 if visible else 20
    keepout = np.where(vis_mask, 254, 0).astype(np.uint8)
    overlay = np.zeros((rows, cols, 3), dtype=np.uint8); overlay[...,0] = np.where(vis_mask, 40, 220); overlay[...,1] = np.where(vis_mask, 200, 40); overlay[...,2] = 40; overlay[obs_r, obs_c] = (255,255,255)
    keepout_pgm, keepout_yaml = out_dir / "visibility_keepout_mask.pgm", out_dir / "visibility_keepout_mask.yaml"
    radio_pgm, radio_yaml = out_dir / "radio_speed_mask.pgm", out_dir / "radio_speed_mask.yaml"
    overlay_png = out_dir / "visibility_overlay.png"
    Image.fromarray(np.flipud(keepout)).save(keepout_pgm); Image.fromarray(np.flipud(radio_speed)).save(radio_pgm); Image.fromarray(np.flipud(overlay)).save(overlay_png)
    save_mask_yaml(ref_yaml, keepout_pgm.name, keepout_yaml); save_mask_yaml(ref_yaml, radio_pgm.name, radio_yaml)
    print(json.dumps({"observer_grid": [int(obs_r), int(obs_c)], "visibility_keepout_mask": str(keepout_pgm), "visibility_keepout_yaml": str(keepout_yaml), "radio_speed_mask": str(radio_pgm), "radio_speed_yaml": str(radio_yaml), "overlay": str(overlay_png)}, indent=2))

if __name__ == "__main__":
    main()
