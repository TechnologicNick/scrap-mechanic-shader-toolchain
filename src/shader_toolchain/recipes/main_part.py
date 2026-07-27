"""Recognize the complete part material and animation permutation family."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .main_character import apply_character_material_recipe


def apply_main_part_recipe(
    staging: Path,
    records: list[dict[str, Any]],
    blobs: list[bytes],
    compiler: Any,
) -> dict[str, Any] | None:
    """Lift every main_part permutation through the shared material pipeline."""
    return apply_character_material_recipe(
        staging, records, blobs, compiler,
        source_name="main_part", shader_count=1812, pixel_count=921,
    )
