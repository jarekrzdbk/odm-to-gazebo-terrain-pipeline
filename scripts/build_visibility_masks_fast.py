#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
import tifffile
import yaml


def read_geotiff(path: Path):
    with tifffile.TiffFile(path) as tf:
        page = tf.pages[0]
        arr = page.asarray().astype(np.float32)
        pixel_scale_x = pixel_scale_y = 1.0
        nodata = None
        scale_tag = page.tags.get('ModelPixelScaleTag')
        if scale_tag is not None:
            vals = scale_tag.value
            if len(vals) >= 2:
                pixel_scale_x, pixel_scale_y = float(vals[0]), float(vals[1])
        nodata_tag = page.tags.get('GDAL_NODATA')
        if nodata_tag is not None:
            raw = nodata_tag.value
            if isinstance(raw, bytes):
                raw = raw.decode('utf-8', errors='ignore')
            raw = str(raw).strip().strip('\x00')
            try:
                nodata = float(raw)
            except ValueError:
                nodata = None
    valid = np.isfinite(arr)
    if nodata is not None:
        valid &= arr != nodata
    return arr, abs(pixel_scale_x), abs(pixel_scale_y), valid


def load_map_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding='utf-8'))


def save_mask_yaml(ref_yaml: dict, image_name: str, out_yaml: Path):
    data = {
        'image': image_name,
        'mode': ref_yaml.get('mode', 'trinary'),
        'resolution': ref_yaml['resolution'],
        'origin': ref_yaml['origin'],
        'negate': 0,
        'occupied_thresh': 0.65,
        'free_thresh': 0.196,
    }
    out_yaml.write_text(yaml.safe_dump(data, sort_keys=False), encoding='utf-8')


def world_to_grid(x_m, y_m, width_m, height_m, cell_x, cell_y, rows, cols):
    col = int(round((x_m + 0.5 * width_m) / cell_x))
    row_from_bottom = int(round((y_m + 0.5 * height_m) / cell_y))
    row = rows - 1 - row_from_bottom
    return int(np.clip(row, 0, rows - 1)), int(np.clip(col, 0, cols - 1))


def bresenham(r0, c0, r1, c1):
    points = []
    dr = abs(r1 - r0)
    dc = abs(c1 - c0)
    sr = 1 if r0 < r1 else -1
    sc = 1 if c0 < c1 else -1
    err = dc - dr
    r, c = r0, c0
    while True:
        points.append((r, c))
        if r == r1 and c == c1:
            break
        e2 = 2 * err
        if e2 > -dr:
            err -= dr
            c += sc
        if e2 < dc:
            err += dc
            r += sr
    return points


def is_visible(dem, pts, z0, z1):
    if len(pts) <= 1:
        return True
    total = len(pts) - 1
    for i, (r, c) in enumerate(pts[1:-1], start=1):
        z_line = (1.0 - i / total) * z0 + (i / total) * z1
        if dem[r, c] > z_line:
            return False
    return True


def resize_nearest(arr, out_w, out_h):
    img = Image.fromarray(arr)
    return np.array(img.resize((out_w, out_h), resample=Image.Resampling.NEAREST))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dem', required=True)
    ap.add_argument('--obs-x-m', type=float, required=True)
    ap.add_argument('--obs-y-m', type=float, required=True)
    ap.add_argument('--obs-height-m', type=float, default=2.0)
    ap.add_argument('--target-height-m', type=float, default=0.5)
    ap.add_argument('--max-range-m', type=float, default=300.0)
    ap.add_argument('--map-yaml', required=True)
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--work-resolution-m', type=float, default=2.0)
    args = ap.parse_args()

    dem, px, py, valid = read_geotiff(Path(args.dem))
    ref_yaml = load_map_yaml(Path(args.map_yaml))
    map_img = np.array(Image.open(Path(args.map_yaml).parent / ref_yaml['image']))
    map_rows, map_cols = map_img.shape[:2]

    world_width = dem.shape[1] * px
    world_height = dem.shape[0] * py

    stride = max(1, int(round(args.work_resolution_m / min(px, py))))
    dem_c = dem[::stride, ::stride]
    valid_c = valid[::stride, ::stride]
    cell_x = px * stride
    cell_y = py * stride
    rows, cols = dem_c.shape

    obs_r, obs_c = world_to_grid(args.obs_x_m, args.obs_y_m, world_width, world_height, cell_x, cell_y, rows, cols)
    max_cells = max(1, int(round(args.max_range_m / min(cell_x, cell_y))))

    vis = np.zeros((rows, cols), dtype=bool)
    radio = np.zeros((rows, cols), dtype=np.uint8)
    z0 = float(dem_c[obs_r, obs_c] + args.obs_height_m)

    rmin = max(0, obs_r - max_cells)
    rmax = min(rows, obs_r + max_cells + 1)
    cmin = max(0, obs_c - max_cells)
    cmax = min(cols, obs_c + max_cells + 1)

    checked = 0
    for r in range(rmin, rmax):
        for c in range(cmin, cmax):
            if not valid_c[r, c]:
                continue
            dr, dc = r - obs_r, c - obs_c
            if dr * dr + dc * dc > max_cells * max_cells:
                continue
            z1 = float(dem_c[r, c] + args.target_height_m)
            pts = bresenham(obs_r, obs_c, r, c)
            visible = is_visible(dem_c, pts, z0, z1)
            vis[r, c] = visible
            radio[r, c] = 90 if visible else 20
            checked += 1
        if (r - rmin) % 25 == 0:
            print(f'processed coarse row {r-rmin+1}/{rmax-rmin}, checked={checked}', flush=True)

    keepout_c = np.where(vis, 254, 0).astype(np.uint8)
    overlay_c = np.zeros((rows, cols, 3), dtype=np.uint8)
    overlay_c[vis] = np.array([0, 200, 0], dtype=np.uint8)
    overlay_c[~vis] = np.array([220, 50, 50], dtype=np.uint8)

    keepout = resize_nearest(keepout_c, map_cols, map_rows)
    radio_full = resize_nearest(radio, map_cols, map_rows)
    overlay = np.array(Image.fromarray(overlay_c).resize((map_cols, map_rows), resample=Image.Resampling.NEAREST))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    keepout_pgm = out_dir / 'visibility_keepout_mask.pgm'
    keepout_yaml = out_dir / 'visibility_keepout_mask.yaml'
    radio_pgm = out_dir / 'radio_speed_mask.pgm'
    radio_yaml = out_dir / 'radio_speed_mask.yaml'
    overlay_png = out_dir / 'visibility_overlay.png'

    Image.fromarray(np.flipud(keepout)).save(keepout_pgm)
    Image.fromarray(np.flipud(radio_full)).save(radio_pgm)
    Image.fromarray(np.flipud(overlay)).save(overlay_png)
    save_mask_yaml(ref_yaml, keepout_pgm.name, keepout_yaml)
    save_mask_yaml(ref_yaml, radio_pgm.name, radio_yaml)

    result = {
        'coarse_shape': [int(rows), int(cols)],
        'map_shape': [int(map_rows), int(map_cols)],
        'stride': int(stride),
        'checked_cells': int(checked),
        'keepout_mask': str(keepout_pgm),
        'keepout_yaml': str(keepout_yaml),
        'radio_mask': str(radio_pgm),
        'radio_yaml': str(radio_yaml),
        'overlay': str(overlay_png),
    }
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
