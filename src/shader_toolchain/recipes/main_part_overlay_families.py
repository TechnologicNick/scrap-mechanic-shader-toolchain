"""Typed editor-overlay and wireframe pixel policies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .common import replace_cbuffer_with_include
from .main_part_families import SemanticKey, parse_entry_signature


@dataclass(frozen=True)
class MainPartOverlayFamily:
    mode: str

    @property
    def name(self) -> str:
        return self.mode


def classify_main_part_overlay_family(
    defines: Iterable[str], source: str
) -> MainPartOverlayFamily | None:
    values = frozenset(defines)
    if "PS_PERM_WIREFRAME" in values:
        mode = "wireframe"
    elif "PS_PERM_OVERLAY" not in values:
        return None
    elif "PS_CONNECT_OVERLAY" in values:
        mode = "connect_overlay"
    elif "DISCARD_BEHIND_CENTER" in values:
        mode = "editor_overlay_clipped"
    elif "PS_EDITOR_TRANSFORM_TOOL" in values:
        mode = "editor_overlay"
    else:
        return None
    _signature, parameters = parse_entry_signature(source, "commonPS")
    semantics = {parameter.semantic for parameter in parameters}
    if SemanticKey("SV_TARGET", 0) not in semantics:
        return None
    return MainPartOverlayFamily(mode)


def lift_main_part_overlay_family(
    defines: Iterable[str], source: str
) -> tuple[str, str] | None:
    family = classify_main_part_overlay_family(defines, source)
    if family is None:
        return None
    signature, parameters = parse_entry_signature(source, "commonPS")
    variables = {parameter.semantic: parameter.variable for parameter in parameters}
    if "cbuffer CB_PROJECTION" in source:
        source = replace_cbuffer_with_include(
            source, "CB_PROJECTION", "main_part_projection_abi.hlsl"
        )
    prefix = source[:source.find("// 3Dmigoto declarations")].rstrip()
    output = variables[SemanticKey("SV_TARGET", 0)]
    if family.mode == "wireframe":
        lines = [f"  WriteMainPartWireframe({output});"]
    elif family.mode == "connect_overlay":
        lines = [
            "  RejectMainPartConnectOverlayBehindDepth(",
            f"      {variables[SemanticKey('SV_POSITION', 0)]});",
            "  WriteMainPartConnectOverlay(",
            f"      {variables[SemanticKey('UV', 0)]},",
            f"      {variables[SemanticKey('VERTEXCOLOR', 0)]}, {output});",
        ]
    else:
        lines = []
        if family.mode == "editor_overlay_clipped":
            lines.extend((
                "  RejectMainPartEditorOverlayBehindPlane(",
                f"      {variables[SemanticKey('VIEW_POSITION', 0)]},",
                f"      {variables[SemanticKey('PLANE_VIEW_POS', 0)]});",
            ))
        lines.extend((
            "  WriteMainPartEditorOverlay(",
            f"      {variables[SemanticKey('UV', 0)]}, {output});",
        ))
    return (
        family.name,
        prefix + f"\n\n#define MAIN_PART_{family.mode.upper()}_PHASE 1"
        + '\n#include "include/main_part_overlay_pixel.hlsl"\n\n'
        + signature + "\n{\n" + "\n".join(lines) + "\n}\n",
    )
