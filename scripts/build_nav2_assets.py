#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import numpy as np
import tifffile
from PIL import Image, ImageOps
from scipy import ndimage as ndi

Image.MAX_IMAGE_PIXELS = None

try:
    import gudhi as gd
except Exception:
    gd = None


SEM_IDS = {
    "background": 0,
    "road": 1,
    "grass": 2,
    "building": 3,
    "water": 4,
    "rubble": 5,
    "vegetation": 6,
    "vehicle": 7,
}


def read_geotiff(path: Path):
    with tifffile.TiffFile(path) as tf:
        page = tf.pages[0]
        arr = page.asarray().astype(np.float32)
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


def valid_mask(arr: np.ndarray, nodata):
    valid = np.isfinite(arr)
    if nodata is not None:
        if np.isnan(nodata):
            valid &= ~np.isnan(arr)
        else:
            valid &= arr != nodata
    return valid


def fill_nodata_nearest(arr: np.ndarray, valid: np.ndarray):
    if valid.all():
        return arr.copy()
    inds = ndi.distance_transform_edt(
        ~valid, return_distances=False, return_indices=True
    )
    filled = arr.copy()
    filled[~valid] = arr[tuple(ind[~valid] for ind in inds)]
    return filled


def local_std(arr: np.ndarray, size: int = 5):
    mean = ndi.uniform_filter(arr, size=size, mode="nearest")
    mean_sq = ndi.uniform_filter(arr * arr, size=size, mode="nearest")
    return np.sqrt(np.maximum(mean_sq - mean * mean, 0.0))


def normalize01(arr: np.ndarray):
    arr = np.asarray(arr, dtype=np.float32)
    finite = np.isfinite(arr)
    if not finite.any():
        return np.zeros_like(arr, dtype=np.float32)
    mn = float(np.nanmin(arr))
    mx = float(np.nanmax(arr))
    if mx <= mn:
        return np.zeros_like(arr, dtype=np.float32)
    return ((arr - mn) / (mx - mn)).astype(np.float32)


def compute_traversability(height_m: np.ndarray, pixel_x: float, pixel_y: float):
    dz_dy, dz_dx = np.gradient(height_m, pixel_y, pixel_x)
    slope_deg = np.degrees(np.arctan(np.hypot(dz_dx, dz_dy))).astype(np.float32)
    rough = local_std(height_m, size=7).astype(np.float32)

    slope_score = np.exp(-((slope_deg / 18.0) ** 2)).astype(np.float32)
    rough_score = np.exp(-((rough / 0.20) ** 2)).astype(np.float32)

    trav = np.clip(0.75 * slope_score + 0.25 * rough_score, 0.0, 1.0).astype(
        np.float32
    )
    return slope_deg, rough, trav


def load_semantic_map(path: Path, shape_hw: tuple[int, int]) -> np.ndarray:
    arr = np.array(Image.open(path).convert("L"))
    if arr.shape != shape_hw:
        arr = np.array(
            Image.fromarray(arr, mode="L").resize(
                (shape_hw[1], shape_hw[0]), resample=Image.Resampling.NEAREST
            )
        )
    return arr.astype(np.uint8)


def apply_semantic_bias(trav: np.ndarray, sem: np.ndarray):
    out = trav.copy()

    # Hard keepouts
    out[sem == SEM_IDS["building"]] = 0.0
    out[sem == SEM_IDS["water"]] = 0.0
    out[sem == SEM_IDS["vehicle"]] = np.minimum(out[sem == SEM_IDS["vehicle"]], 0.05)

    # Soft penalties
    out[sem == SEM_IDS["vegetation"]] = np.clip(
        out[sem == SEM_IDS["vegetation"]] - 0.18, 0.0, 1.0
    )
    out[sem == SEM_IDS["rubble"]] = np.clip(
        out[sem == SEM_IDS["rubble"]] - 0.12, 0.0, 1.0
    )

    # Soft boosts
    out[sem == SEM_IDS["road"]] = np.clip(
        out[sem == SEM_IDS["road"]] + 0.18, 0.0, 1.0
    )
    out[sem == SEM_IDS["grass"]] = np.clip(
        out[sem == SEM_IDS["grass"]] + 0.05, 0.0, 1.0
    )

    return out


def comp_count(mask: np.ndarray):
    structure = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=np.uint8)
    labels, n = ndi.label(mask, structure=structure)
    counts = np.bincount(labels.ravel())[1:]
    return labels, n, counts


def count_holes(free_mask: np.ndarray):
    holes = ndi.binary_fill_holes(free_mask) & ~free_mask
    _, n, _ = comp_count(holes)
    return int(n)


def persistence_summary(prob_traversable: np.ndarray):
    if gd is None:
        return {
            "h0_top": [],
            "h1_top": [],
            "main_region_persistence": 0.0,
            "corridor_stability_score": 0.0,
        }

    cost = 1.0 - np.nan_to_num(prob_traversable, nan=0.0)
    cc = gd.CubicalComplex(top_dimensional_cells=cost.astype(np.float64))
    diag = cc.persistence()
    h0, h1 = [], []
    for dim, (birth, death) in diag:
        length = 1.0 - float(birth) if np.isinf(death) else float(death - birth)
        if dim == 0:
            h0.append(length)
        elif dim == 1:
            h1.append(length)
    h0.sort(reverse=True)
    h1.sort(reverse=True)
    return {
        "h0_top": h0[:10],
        "h1_top": h1[:10],
        "main_region_persistence": h0[0] if h0 else 0.0,
        "corridor_stability_score": h1[0] if h1 else 0.0,
    }


def select_threshold(prob_traversable: np.ndarray, valid: np.ndarray):
    thresholds = np.linspace(0.35, 0.80, 19)
    best = None
    total_valid = max(int(valid.sum()), 1)

    for thr in thresholds:
        free = (prob_traversable >= thr) & valid
        _, _, counts = comp_count(free)
        free_count = int(free.sum())

        if free_count == 0 or counts.size == 0:
            largest_frac, island_frac, holes, score = 0.0, 1.0, 0, -1e9
        else:
            largest = int(counts.max())
            small_islands = int(counts[counts < 100].sum())
            holes = count_holes(free)
            largest_frac = largest / max(free_count, 1)
            island_frac = small_islands / total_valid
            score = (
                1.6 * largest_frac
                - 0.7 * island_frac
                - 0.08 * holes
                - 0.15 * abs(float(thr) - 0.55)
            )

        row = {
            "threshold": float(thr),
            "score": float(score),
            "largest_free_component_fraction": float(largest_frac),
            "small_island_fraction": float(island_frac),
            "hole_count": int(holes),
        }
        if best is None or row["score"] > best["score"]:
            best = row

    return best


def cleanup_free_mask(
    free: np.ndarray,
    valid: np.ndarray,
    min_free_region_px: int,
    hole_fill_px: int,
    inflate_px: int,
):
    free = free & valid

    free = ndi.binary_opening(free, structure=np.ones((3, 3), dtype=bool))
    free = ndi.binary_closing(free, structure=np.ones((5, 5), dtype=bool))

    labels, _, counts = comp_count(free)
    for label_id, count in enumerate(counts, start=1):
        if count < min_free_region_px:
            free[labels == label_id] = False

    holes = ndi.binary_fill_holes(free) & ~free
    hole_labels, _, hole_counts = comp_count(holes)
    for label_id, count in enumerate(hole_counts, start=1):
        if count < hole_fill_px:
            free[hole_labels == label_id] = True

    occupied = (~free) & valid
    if inflate_px > 0:
        occupied = ndi.binary_dilation(occupied, iterations=inflate_px)

    free = (~occupied) & valid
    return free


def export_nav2_map(
    free_mask: np.ndarray,
    valid: np.ndarray,
    resolution_m: float,
    origin_xy: tuple[float, float],
    out_prefix: Path,
):
    occ = (~free_mask) & valid
    unk = ~valid

    img = np.full(free_mask.shape, 205, dtype=np.uint8)
    img[free_mask] = 254
    img[occ] = 0
    img[unk] = 205

    pgm_path = out_prefix.with_suffix(".pgm")
    yaml_path = out_prefix.with_suffix(".yaml")

    Image.fromarray(np.flipud(img)).save(pgm_path)
    yaml_path.write_text(
        (
            f"image: {pgm_path.name}\n"
            f"mode: trinary\n"
            f"resolution: {resolution_m:.6f}\n"
            f"origin: [{origin_xy[0]:.6f}, {origin_xy[1]:.6f}, 0.0]\n"
            f"negate: 0\n"
            f"occupied_thresh: 0.65\n"
            f"free_thresh: 0.196\n"
        ),
        encoding="utf-8",
    )
    return pgm_path, yaml_path, img


def save_debug_png(arr01: np.ndarray, path: Path):
    Image.fromarray(
        np.clip(np.round(arr01 * 255.0), 0, 255).astype(np.uint8)
    ).save(path)


def save_nav_debug_overlay(
    orthophoto: Path | None,
    free_mask: np.ndarray,
    valid: np.ndarray,
    out_path: Path,
):
    h, w = free_mask.shape

    if orthophoto is not None and orthophoto.exists():
        base = Image.open(orthophoto).convert("RGB")
        base = ImageOps.exif_transpose(base)
        base = base.resize((w, h), resample=Image.Resampling.BILINEAR)
        rgb = np.array(base, dtype=np.uint8)
    else:
        rgb = np.full((h, w, 3), 220, dtype=np.uint8)

    occ = (~free_mask) & valid
    out = rgb.astype(np.float32)

    # free = green tint, occupied = red tint, invalid = gray
    out[free_mask] = 0.75 * out[free_mask] + 0.25 * np.array([0, 255, 0], dtype=np.float32)
    out[occ] = 0.70 * out[occ] + 0.30 * np.array([255, 0, 0], dtype=np.float32)
    out[~valid] = 0.75 * out[~valid] + 0.25 * np.array([80, 80, 80], dtype=np.float32)

    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--source", choices=["dtm", "dsm"], default="dtm")
    ap.add_argument("--semantic-class-map")
    ap.add_argument("--orthophoto")
    ap.add_argument("--inflate-radius-m", type=float, default=0.45)
    ap.add_argument("--min-free-region-px", type=int, default=150)
    ap.add_argument("--hole-fill-px", type=int, default=500)
    args = ap.parse_args()

    dataset = Path(args.dataset).resolve()
    terrain_dir = dataset / "terrain"
    terrain_dir.mkdir(parents=True, exist_ok=True)

    dem_path = dataset / "odm_dem" / f"{args.source}.tif"
    if not dem_path.exists():
        raise FileNotFoundError(f"Missing DEM: {dem_path}")

    arr, px, py, nodata = read_geotiff(dem_path)
    valid = valid_mask(arr, nodata)
    filled = fill_nodata_nearest(arr, valid)

    slope_deg, rough, trav = compute_traversability(filled, px, py)

    semantic_used = False
    if args.semantic_class_map:
        sem_path = Path(args.semantic_class_map)
        if sem_path.exists():
            sem = load_semantic_map(sem_path, trav.shape)
            trav = apply_semantic_bias(trav, sem)
            semantic_used = True

    trav[~valid] = np.nan

    topo = persistence_summary(trav)
    best = select_threshold(np.nan_to_num(trav, nan=0.0), valid)

    avg_res = 0.5 * (px + py)
    inflate_px = int(round(args.inflate_radius_m / max(avg_res, 1e-6)))

    free = (np.nan_to_num(trav, nan=0.0) >= best["threshold"]) & valid
    free = cleanup_free_mask(
        free,
        valid,
        min_free_region_px=args.min_free_region_px,
        hole_fill_px=args.hole_fill_px,
        inflate_px=inflate_px,
    )

    world_width = arr.shape[1] * px
    world_height = arr.shape[0] * py
    origin_xy = (-0.5 * world_width, -0.5 * world_height)

    pgm_path, yaml_path, img = export_nav2_map(
        free,
        valid,
        avg_res,
        origin_xy,
        terrain_dir / "nav2_map",
    )

    save_debug_png(normalize01(np.nan_to_num(trav, nan=0.0)), terrain_dir / "traversability.png")
    save_debug_png(normalize01(slope_deg), terrain_dir / "slope.png")
    save_debug_png(normalize01(rough), terrain_dir / "roughness.png")

    ortho = Path(args.orthophoto).resolve() if args.orthophoto else None
    save_nav_debug_overlay(
        ortho if ortho and ortho.exists() else None,
        free,
        valid,
        terrain_dir / "nav_debug_overlay.png",
    )

    valid_vals = arr[valid]
    dem_min = float(np.nanmin(valid_vals))
    dem_max = float(np.nanmax(valid_vals))
    dem_range = float(max(dem_max - dem_min, 1.0))

    frame = {
        "source_dem": str(dem_path),
        "world_width_m": float(world_width),
        "world_height_m": float(world_height),
        "dem_min_m": dem_min,
        "dem_max_m": dem_max,
        "dem_range_m": dem_range,
        "gazebo_size_xyz": [float(world_width), float(world_height), dem_range],
        "gazebo_pos_xyz": [0.0, 0.0, -dem_min],
        "map_origin_xy": [float(origin_xy[0]), float(origin_xy[1])],
        "pixel_scale_xy_m": [float(px), float(py)],
        "selected_traversability_threshold": best["threshold"],
        "inflate_radius_m": float(args.inflate_radius_m),
        "inflate_radius_px": int(inflate_px),
        "semantic_prior_used": bool(semantic_used),
    }
    (terrain_dir / "terrain_frame.json").write_text(
        json.dumps(frame, indent=2),
        encoding="utf-8",
    )

    summary = {
        "selected_threshold": best,
        "topology": topo,
        "outputs": {
            "nav2_map_pgm": str(pgm_path),
            "nav2_map_yaml": str(yaml_path),
            "traversability_png": str(terrain_dir / "traversability.png"),
            "slope_png": str(terrain_dir / "slope.png"),
            "roughness_png": str(terrain_dir / "roughness.png"),
            "nav_debug_overlay": str(terrain_dir / "nav_debug_overlay.png"),
        },
    }
    (terrain_dir / "topology_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
