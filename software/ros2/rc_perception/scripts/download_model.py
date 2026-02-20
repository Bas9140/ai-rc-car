#!/usr/bin/env python3
"""
download_model.py
Download het YOLOv8n blob bestand voor de Myriad X chip van de OAK-D Lite.

Gebruik:
  python3 scripts/download_model.py
  python3 scripts/download_model.py --model yolov8s_coco_640x352 --shaves 5

Het blob wordt gecached in ~/.cache/rc_car/blobs/
Na het downloaden kun je de blob pad kopiëren naar params.yaml.
"""

import argparse
import sys
from pathlib import Path

# Zorg dat het pakket vindbaar is bij directe aanroep
sys.path.insert(0, str(Path(__file__).parent.parent))

from rc_perception.model_utils import get_model_path, DEFAULT_MODEL_NAME


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download YOLOv8 blob voor OAK-D Lite Myriad X")
    parser.add_argument(
        "--model", default=DEFAULT_MODEL_NAME,
        help=f"Model naam (default: {DEFAULT_MODEL_NAME})")
    parser.add_argument(
        "--shaves", type=int, default=6,
        help="Aantal Myriad X shaves (4-6, default: 6)")
    parser.add_argument(
        "--cache-dir", default=None,
        help="Cache map voor blobs (default: ~/.cache/rc_car/blobs)")
    args = parser.parse_args()

    print(f"Model: {args.model}")
    print(f"Shaves: {args.shaves}")
    print("Downloaden…")

    try:
        blob_path = get_model_path(args.model, args.cache_dir, args.shaves)
        print(f"\nGeslaagd! Blob opgeslagen in:\n  {blob_path}")
        print(f"\nVoeg toe aan params.yaml:\n"
              f"  oak_node:\n"
              f"    ros__parameters:\n"
              f"      model_name: '{args.model}'\n"
              f"      shaves: {args.shaves}\n")
    except RuntimeError as exc:
        print(f"\nFout: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
