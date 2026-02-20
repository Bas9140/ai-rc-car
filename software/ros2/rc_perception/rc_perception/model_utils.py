"""
model_utils.py
Hulpfuncties voor YOLO blob downloads en modelconversie.

De OAK-D Lite heeft een Myriad X chip (4 TOPS) die alleen .blob bestanden
accepteert die via blobconverter gecompileerd zijn voor OpenVINO.

Ondersteunde modellen (in volgorde van snelheid vs nauwkeurigheid):
  - yolov8n_coco_640x352   – snel, licht model (aanbevolen voor volgen)
  - yolov8s_coco_640x352   – kleine stap nauwkeuriger
  - yolov8m_coco_640x352   – zwaarder, waarschijnlijk te traag op Myriad X

COCO klassen die we gebruiken:
  - 0: person (persoon volgen)
  - 2: car, 7: truck, 3: motorcycle (obstakel detectie)
  - 16: dog, 15: cat (kleine dieren vermijden)
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Standaard model dat op Myriad X past en snel genoeg is
DEFAULT_MODEL_NAME = "yolov8n_coco_640x352"
DEFAULT_MODEL_ZOO  = "depthai"   # of "openmodel"

# COCO klasse IDs
COCO_PERSON      = 0
COCO_VEHICLE_IDS = {2, 3, 5, 7}   # car, motorcycle, bus, truck
COCO_ANIMAL_IDS  = {15, 16, 17}   # cat, dog, horse

# Labels voor logging / annotatie
COCO_LABELS: dict[int, str] = {
    0:  "person",
    1:  "bicycle",
    2:  "car",
    3:  "motorcycle",
    4:  "airplane",
    5:  "bus",
    6:  "train",
    7:  "truck",
    14: "bird",
    15: "cat",
    16: "dog",
    17: "horse",
    24: "backpack",
    25: "umbrella",
    63: "laptop",
    67: "cell phone",
}


def get_model_path(
    model_name: str = DEFAULT_MODEL_NAME,
    cache_dir: Optional[str] = None,
    shaves: int = 6,
) -> Path:
    """
    Download (indien nodig) het YOLO .blob bestand voor de Myriad X.

    Parameters
    ----------
    model_name : str
        Naam in de blobconverter zoo (bv. "yolov8n_coco_640x352").
    cache_dir : str | None
        Map voor gecachte blobs. Standaard: ~/.cache/rc_car/blobs/
    shaves : int
        Aantal Myriad X shaves (4-6 typisch voor OAK-D Lite).

    Returns
    -------
    Path
        Pad naar het .blob bestand.
    """
    if cache_dir is None:
        cache_dir = Path.home() / ".cache" / "rc_car" / "blobs"
    else:
        cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    blob_path = cache_dir / f"{model_name}_sh{shaves}.blob"

    if blob_path.exists():
        logger.info(f"Blob gevonden in cache: {blob_path}")
        return blob_path

    logger.info(f"Downloaden: {model_name} ({shaves} shaves)…")

    try:
        import blobconverter  # type: ignore
        downloaded = blobconverter.from_zoo(
            name=model_name,
            zoo_type=DEFAULT_MODEL_ZOO,
            shaves=shaves,
        )
        # blobconverter slaat op in eigen tmpdir; kopieer naar cache
        import shutil
        shutil.copy(downloaded, blob_path)
        logger.info(f"Blob opgeslagen: {blob_path}")
    except ImportError:
        raise RuntimeError(
            "blobconverter niet geïnstalleerd. Voer uit:\n"
            "  pip install blobconverter"
        )
    except Exception as exc:
        raise RuntimeError(f"Blob download mislukt: {exc}") from exc

    return blob_path


def label_for(class_id: int) -> str:
    """Geeft de leesbare naam terug voor een COCO klasse ID."""
    return COCO_LABELS.get(class_id, f"class_{class_id}")


def is_obstacle(class_id: int) -> bool:
    """True als dit object als obstakel behandeld moet worden."""
    return class_id in COCO_VEHICLE_IDS or class_id in COCO_ANIMAL_IDS


def is_person(class_id: int) -> bool:
    return class_id == COCO_PERSON
