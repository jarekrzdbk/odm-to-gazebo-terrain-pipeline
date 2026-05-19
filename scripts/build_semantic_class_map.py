#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image
from huggingface_hub import hf_hub_download
from transformers import AutoConfig, AutoImageProcessor

Image.MAX_IMAGE_PIXELS = None


def normalize_label(s: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else " " for ch in s).strip()


def load_target_schema(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    target_ids = {k: int(v) for k, v in data["target_ids"].items()}
    matchers = {
        k: [normalize_label(x) for x in v]
        for k, v in data["matchers"].items()
    }
    return target_ids, matchers


def build_model_to_target_map(id2label: dict, target_ids: dict, matchers: dict):
    mapping = {}
    summary = {}
    for raw_id, raw_label in id2label.items():
        model_id = int(raw_id)
        label = normalize_label(raw_label)
        chosen = "background"
        for target_name, patterns in matchers.items():
            if any(p in label for p in patterns):
                chosen = target_name
                break
        mapping[model_id] = int(target_ids[chosen])
        summary[model_id] = {
            "model_label": raw_label,
            "target_name": chosen,
            "target_id": int(target_ids[chosen]),
        }
    return mapping, summary


def make_palette(target_ids: dict):
    n = max(target_ids.values()) + 1
    pal = np.zeros((n, 3), dtype=np.uint8)
    base = {
        "background": (0, 0, 0),
        "road": (180, 180, 180),
        "grass": (60, 180, 75),
        "building": (230, 25, 75),
        "water": (0, 130, 200),
        "rubble": (245, 130, 48),
        "vegetation": (34, 139, 34),
        "vehicle": (255, 225, 25),
    }
    for name, idx in target_ids.items():
        pal[int(idx)] = base.get(name, (255, 255, 255))
    return pal


def iter_positions(length: int, tile: int, stride: int):
    if length <= tile:
        return [0]
    out = list(range(0, max(1, length - tile + 1), stride))
    if out[-1] != length - tile:
        out.append(length - tile)
    return out


def crop_write_slices(y: int, x: int, h: int, w: int, H: int, W: int, overlap: int):
    top = 0 if y == 0 else overlap
    left = 0 if x == 0 else overlap
    bottom = h if y + h >= H else h - overlap
    right = w if x + w >= W else w - overlap
    ys = slice(y + top, y + bottom)
    xs = slice(x + left, x + right)
    tile_ys = slice(top, bottom)
    tile_xs = slice(left, right)
    return ys, xs, tile_ys, tile_xs


def load_session(model_id: str, providers: list[str]):
    onnx_path = hf_hub_download(repo_id=model_id, filename="model.onnx")
    sess = ort.InferenceSession(onnx_path, providers=providers)
    return onnx_path, sess


def prepare_inputs(processor, crop: np.ndarray, session: ort.InferenceSession):
    # use_fast=False avoids the "Only returning PyTorch tensors" issue
    batch = processor(images=crop, return_tensors="pt")
    ort_inputs = {}
    input_names = {inp.name for inp in session.get_inputs()}

    for k, v in batch.items():
        arr = v.detach().cpu().numpy()
        if k in input_names:
            ort_inputs[k] = arr.astype(np.float32)

    if not ort_inputs:
        first_input = session.get_inputs()[0].name
        ort_inputs[first_input] = batch["pixel_values"].detach().cpu().numpy().astype(np.float32)

    return ort_inputs


def extract_logits(outputs, num_labels: int):
    logits = outputs[0]

    if logits.ndim != 4:
        raise ValueError(f"Unexpected logits shape: {logits.shape}")

    # NCHW: (1, C, H, W)
    if logits.shape[1] == num_labels:
        logits = logits[0]
        logits = np.transpose(logits, (1, 2, 0))
        return logits.astype(np.float32)

    # NHWC: (1, H, W, C)
    if logits.shape[-1] == num_labels:
        logits = logits[0]
        return logits.astype(np.float32)

    raise ValueError(
        f"Cannot determine logits layout from shape {logits.shape} "
        f"with num_labels={num_labels}"
    )


def build_blend(rgb: np.ndarray, overlay: np.ndarray, out_labels: np.ndarray, alpha: float):
    rgb_f = rgb.astype(np.float32)
    overlay_f = overlay.astype(np.float32)

    # treat fully black orthophoto pixels as nodata/background
    valid = (rgb[..., 0] > 5) | (rgb[..., 1] > 5) | (rgb[..., 2] > 5)

    blend = rgb_f.copy()
    mask = valid & (out_labels != 0)

    blend[mask] = (1.0 - alpha) * rgb_f[mask] + alpha * overlay_f[mask]
    blend[~valid] = rgb_f[~valid]

    return np.clip(blend, 0, 255).astype(np.uint8), valid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--model-id", required=True)
    ap.add_argument("--schema-json", required=True)
    ap.add_argument("--out-class-map", required=True)
    ap.add_argument("--out-overlay", required=True)
    ap.add_argument("--out-metadata", required=True)
    ap.add_argument("--out-blend", default=None)
    ap.add_argument("--blend-alpha", type=float, default=0.35)
    ap.add_argument("--tile-size", type=int, default=512)
    ap.add_argument("--overlap", type=int, default=64)
    ap.add_argument("--providers", default="CPUExecutionProvider")
    args = ap.parse_args()

    image_path = Path(args.image)
    schema_path = Path(args.schema_json)
    out_class_map = Path(args.out_class_map)
    out_overlay = Path(args.out_overlay)
    out_metadata = Path(args.out_metadata)
    out_blend = Path(args.out_blend) if args.out_blend else None

    out_class_map.parent.mkdir(parents=True, exist_ok=True)
    out_overlay.parent.mkdir(parents=True, exist_ok=True)
    out_metadata.parent.mkdir(parents=True, exist_ok=True)
    if out_blend:
        out_blend.parent.mkdir(parents=True, exist_ok=True)

    image = Image.open(image_path).convert("RGB")
    rgb = np.array(image)
    H, W = rgb.shape[:2]

    processor = AutoImageProcessor.from_pretrained(args.model_id, use_fast=False)
    config = AutoConfig.from_pretrained(args.model_id)

    providers = [p.strip() for p in args.providers.split(",") if p.strip()]
    onnx_path, session = load_session(args.model_id, providers)

    target_ids, matchers = load_target_schema(schema_path)
    id2label = {int(k): v for k, v in config.id2label.items()}
    remap, mapping_summary = build_model_to_target_map(id2label, target_ids, matchers)
    palette = make_palette(target_ids)

    tile = int(args.tile_size)
    overlap = int(args.overlap)
    stride = max(1, tile - 2 * overlap)

    xs_all = iter_positions(W, tile, stride)
    ys_all = iter_positions(H, tile, stride)

    out = np.zeros((H, W), dtype=np.uint8)

    total = len(xs_all) * len(ys_all)
    done = 0

    for y in ys_all:
        for x in xs_all:
            crop = rgb[y:y + tile, x:x + tile]
            h, w = crop.shape[:2]

            ort_inputs = prepare_inputs(processor, crop, session)
            outputs = session.run(None, ort_inputs)
            logits = extract_logits(outputs, config.num_labels)

            logits = cv2.resize(logits, (w, h), interpolation=cv2.INTER_LINEAR)
            pred = np.argmax(logits, axis=-1).astype(np.int32)

            remapped = np.zeros_like(pred, dtype=np.uint8)
            for model_id, target_id in remap.items():
                remapped[pred == model_id] = target_id

            ys, xs, tys, txs = crop_write_slices(y, x, h, w, H, W, overlap)
            out[ys, xs] = remapped[tys, txs]

            done += 1
            if done % 10 == 0 or done == total:
                print(f"[{done}/{total}] tiled semantic inference", flush=True)

    overlay = palette[np.clip(out, 0, len(palette) - 1)]
    blend, valid = build_blend(rgb, overlay, out, args.blend_alpha)

    Image.fromarray(out, mode="L").save(out_class_map)
    Image.fromarray(overlay, mode="RGB").save(out_overlay)
    if out_blend:
        Image.fromarray(blend, mode="RGB").save(out_blend)

    metadata = {
        "model_id": args.model_id,
        "onnx_path": str(onnx_path),
        "image": str(image_path),
        "tile_size": tile,
        "overlap": overlap,
        "providers": providers,
        "blend_alpha": args.blend_alpha,
        "target_ids": target_ids,
        "model_to_target": mapping_summary,
        "output_class_map": str(out_class_map),
        "output_overlay": str(out_overlay),
        "output_blend": str(out_blend) if out_blend else None,
        "valid_pixel_fraction": float(valid.mean()),
    }
    out_metadata.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
