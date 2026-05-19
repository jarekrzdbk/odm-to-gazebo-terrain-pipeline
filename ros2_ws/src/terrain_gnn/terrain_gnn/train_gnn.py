#!/usr/bin/env python3
import argparse, json
from pathlib import Path
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--dataset", required=True, help="NPZ file with graph tensors / features"); args = ap.parse_args()
    path = Path(args.dataset)
    if not path.exists(): raise FileNotFoundError(path)
    print(json.dumps({"status": "stub", "message": "This is a scaffold for future GNN traversability training. For a first portfolio milestone, use classical slope+roughness+semantic+topology layers first.", "dataset": str(path)}, indent=2))
if __name__ == "__main__":
    main()
