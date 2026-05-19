#!/usr/bin/env python3
import argparse, json
from pathlib import Path
import numpy as np
from PIL import Image
import yaml

KEEP_OUT_CLASSES = {"building", "water"}
SLOW_CLASSES = {"grass": 60, "rubble": 30, "vegetation": 50}
PREFERRED_CLASSES = {"road": 95}

def load_map_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))

def save_mask_yaml(ref_yaml: dict, image_name: str, out_yaml: Path):
    data = {"image": image_name, "mode": ref_yaml.get("mode", "trinary"), "resolution": ref_yaml["resolution"], "origin": ref_yaml["origin"], "negate": 0, "occupied_thresh": 0.65, "free_thresh": 0.196}
    out_yaml.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

def colorize(class_map: np.ndarray, name_to_id: dict):
    colors = {"road": (180,180,180), "grass": (60,180,75), "building": (230,25,75), "water": (0,130,200), "rubble": (245,130,48), "vegetation": (34,139,34), "vehicle": (255,225,25)}
    out = np.zeros((*class_map.shape, 3), dtype=np.uint8)
    for name, cid in name_to_id.items():
        if name in colors: out[class_map == cid] = colors[name]
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--class-map", required=True); ap.add_argument("--map-yaml", required=True); ap.add_argument("--out-dir", required=True); ap.add_argument("--classes-json", required=True)
    args = ap.parse_args()
    class_map = np.array(Image.open(Path(args.class_map))); class_map = class_map[...,0] if class_map.ndim == 3 else class_map
    ref_yaml = load_map_yaml(Path(args.map_yaml)); name_to_id = json.loads(args.classes_json)
    out_dir = Path(args.out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    keepout = np.full(class_map.shape, 254, dtype=np.uint8); speed = np.zeros(class_map.shape, dtype=np.uint8)
    for name, cid in name_to_id.items():
        mask = class_map == cid
        if name in KEEP_OUT_CLASSES: keepout[mask] = 0
        if name in SLOW_CLASSES: speed[mask] = np.uint8(SLOW_CLASSES[name])
        if name in PREFERRED_CLASSES: speed[mask] = np.uint8(PREFERRED_CLASSES[name])
    keepout_pgm, keepout_yaml = out_dir / "keepout_mask.pgm", out_dir / "keepout_mask.yaml"
    speed_pgm, speed_yaml = out_dir / "speed_mask.pgm", out_dir / "speed_mask.yaml"
    overlay_png = out_dir / "semantic_overlay.png"
    Image.fromarray(np.flipud(keepout)).save(keepout_pgm); Image.fromarray(np.flipud(speed)).save(speed_pgm); Image.fromarray(np.flipud(colorize(class_map, name_to_id))).save(overlay_png)
    save_mask_yaml(ref_yaml, keepout_pgm.name, keepout_yaml); save_mask_yaml(ref_yaml, speed_pgm.name, speed_yaml)
    print(json.dumps({"keepout_mask": str(keepout_pgm), "keepout_yaml": str(keepout_yaml), "speed_mask": str(speed_pgm), "speed_yaml": str(speed_yaml), "overlay": str(overlay_png)}, indent=2))

if __name__ == "__main__":
    main()
