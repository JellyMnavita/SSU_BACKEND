"""Export / import images vers vision_data/labeled/ (réentraînement vision)."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

VISION_LABELS: tuple[str, ...] = (
    "arme",
    "foule",
    "vehicule_suspect",
    "accident",
    "incendie",
    "autre",
)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
EXPORTS_SINCE_TRAIN_KEY = "vision:exports_since_train"


def vision_data_dir() -> Path:
    return Path(os.environ.get("VISION_DATA_DIR", Path(settings.BASE_DIR).parent / "vision_data"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dataset_stats() -> dict:
    root = vision_data_dir()
    counts: dict[str, int] = {}
    total = 0
    for label in VISION_LABELS:
        class_dir = root / "labeled" / label
        n = (
            sum(1 for p in class_dir.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)
            if class_dir.is_dir()
            else 0
        )
        counts[label] = n
        total += n
    return {
        "vision_data_dir": str(root),
        "total": total,
        "by_class": counts,
        "exports_since_train": int(cache.get(EXPORTS_SINCE_TRAIN_KEY) or 0),
    }


def _find_by_digest(class_dir: Path, digest: str) -> Path | None:
    if not class_dir.is_dir():
        return None
    prefix = digest[:12]
    for path in class_dir.iterdir():
        if path.is_file() and path.name.startswith(prefix):
            return path
    return None


def _remove_previous_export(previous_rel: str | None, vision_root: Path) -> None:
    if not previous_rel:
        return
    old = vision_root / previous_rel
    if old.is_file():
        old.unlink()


def export_image_to_labeled(
    src: Path,
    label: str,
    *,
    suffix: str = "",
    previous_rel: str | None = None,
) -> dict:
    if label not in VISION_LABELS:
        raise ValueError(f"Label invalide : {label}")

    vision_root = vision_data_dir()
    _remove_previous_export(previous_rel, vision_root)

    dest_dir = vision_root / "labeled" / label
    dest_dir.mkdir(parents=True, exist_ok=True)

    digest = _sha256_file(src)
    existing = _find_by_digest(dest_dir, digest)
    if existing:
        return {
            "path": str(existing.relative_to(vision_root)),
            "label": label,
            "sha256": digest,
            "duplicate": True,
        }

    ext = src.suffix.lower() if src.suffix else ".jpg"
    tag = f"_{suffix}" if suffix else ""
    dest = dest_dir / f"{digest[:12]}{tag}{ext}"
    shutil.copy2(src, dest)

    cache.set(EXPORTS_SINCE_TRAIN_KEY, int(cache.get(EXPORTS_SINCE_TRAIN_KEY) or 0) + 1, None)

    return {
        "path": str(dest.relative_to(vision_root)),
        "label": label,
        "sha256": digest,
        "duplicate": False,
    }


def import_uploaded_files(files, label: str) -> dict:
    if label not in VISION_LABELS:
        raise ValueError(f"Label invalide : {label}")

    vision_root = vision_data_dir()
    dest_dir = vision_root / "labeled" / label
    dest_dir.mkdir(parents=True, exist_ok=True)

    imported: list[dict] = []
    skipped = 0
    for upload in files:
        name = getattr(upload, "name", "image.jpg") or "image.jpg"
        ext = Path(name).suffix.lower()
        if ext not in IMAGE_EXTENSIONS:
            skipped += 1
            continue
        data = upload.read()
        digest = _sha256_bytes(data)
        existing = _find_by_digest(dest_dir, digest)
        if existing:
            skipped += 1
            imported.append({"path": str(existing.relative_to(vision_root)), "duplicate": True})
            continue
        dest = dest_dir / f"{digest[:12]}_upload{ext}"
        dest.write_bytes(data)
        cache.set(EXPORTS_SINCE_TRAIN_KEY, int(cache.get(EXPORTS_SINCE_TRAIN_KEY) or 0) + 1, None)
        imported.append({"path": str(dest.relative_to(vision_root)), "duplicate": False})

    return {
        "label": label,
        "imported": len([i for i in imported if not i.get("duplicate")]),
        "skipped": skipped,
        "files": imported,
        "stats": dataset_stats(),
    }


def reset_exports_counter() -> None:
    cache.set(EXPORTS_SINCE_TRAIN_KEY, 0, None)
