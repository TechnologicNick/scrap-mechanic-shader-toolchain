"""Describe ``main_part`` pixel permutations as composable semantic phases.

This module is intentionally an inventory/compiler boundary, not another list
of selector hashes.  Recovered compile definitions and entry-point semantics
become a stable descriptor; a registry then explains which typed HLSL phase
implements each descriptor choice and which choices still need recovery.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from enum import StrEnum
import json
from pathlib import Path
from typing import Any, Iterable

from .recipes.main_part_families import parse_entry_signature


class OutputMode(StrEnum):
    TRANSPARENT_SURFACE = "transparent_surface"
    TRANSPARENT_BEHIND = "transparent_behind"
    TRANSPARENT_REFLECTION = "transparent_reflection"
    PREVIEW = "preview"
    VISUALIZATION = "visualization"
    GBUFFER = "gbuffer"
    GFORWARD = "gforward"
    EARLY_GFORWARD = "early_gforward"
    FORWARD = "forward"
    FORWARD_BEHIND = "forward_behind"
    DEPTH = "depth"
    PICKING = "picking"
    OVERLAY = "overlay"
    WIREFRAME = "wireframe"
    UNKNOWN = "unknown"


class Quality(StrEnum):
    DEFAULT = "default"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MaterialModel(StrEnum):
    STANDARD = "standard"
    GLASS = "glass"
    LEGACY_GLASS = "legacy_glass"
    WATER = "water"
    LASER = "laser"
    METAL = "metal"
    FOLIAGE = "foliage"
    TRANSLUCENT = "translucent"
    HAIR = "hair"


class NormalSource(StrEnum):
    GEOMETRIC = "geometric"
    TANGENT_MAP = "tangent_map"
    TANGENT_DETAIL = "tangent_detail"


class CoverageMode(StrEnum):
    OPAQUE = "opaque"
    ALPHA_CUTOUT = "alpha_cutout"
    DISSOLVE_UV0 = "dissolve_uv0"
    DISSOLVE_UV1 = "dissolve_uv1"
    DISSOLVE_3D = "dissolve_3d"


class LightingModel(StrEnum):
    STANDARD = "standard"
    TRANSMISSION = "transmission"
    WATER = "water"
    LASER = "laser"


class ReflectionMode(StrEnum):
    NONE = "none"
    OFF = "off"
    SINGLE = "single"
    MULTI = "multi"
    AS_DIFFUSE = "as_diffuse"


class RefractionMode(StrEnum):
    NONE = "none"
    BASIC = "basic"
    DEPTH_BLUR = "depth_blur"


class CompositionMode(StrEnum):
    STANDARD = "standard"
    RESPONSIVE = "responsive"
    TINTED = "tinted"


PERMUTATION_OUTPUTS = {
    "PS_PERM_TRANSPARANT_SURFACE": OutputMode.TRANSPARENT_SURFACE,
    "PS_PERM_TRANSPARANT_BEHIND": OutputMode.TRANSPARENT_BEHIND,
    "PS_PERM_TRANSPARANT_SURFACE_REFLECTION":
        OutputMode.TRANSPARENT_REFLECTION,
    "PS_PERM_PREVIEW": OutputMode.PREVIEW,
    "PS_PERM_VISUALIZATION": OutputMode.VISUALIZATION,
    "PS_PERM_GBUFFER": OutputMode.GBUFFER,
    "PS_PERM_GFORWARD": OutputMode.GFORWARD,
    "PS_PERM_EARLY_GFORWARD": OutputMode.EARLY_GFORWARD,
    "PS_PERM_FORWARD": OutputMode.FORWARD,
    "PS_PERM_FORWARD_BEHIND": OutputMode.FORWARD_BEHIND,
    "PS_PERM_DEPTH": OutputMode.DEPTH,
    "PS_PERM_PICKING": OutputMode.PICKING,
    "PS_PERM_OVERLAY": OutputMode.OVERLAY,
    "PS_PERM_WIREFRAME": OutputMode.WIREFRAME,
}


AXIS_DEFINES = frozenset({
    "PIXEL_SHADER", "ALPHA",
    *PERMUTATION_OUTPUTS,
    "PS_SHADER_QUALITY_LOW", "PS_SHADER_QUALITY_MEDIUM",
    "PS_SHADER_QUALITY_HIGH",
    "PS_REFLECTION_OFF", "PS_REFLECTION_SINGLE", "PS_REFLECTION_MULTI",
    "PS_REFLECTION_AS_DIFFUSE",
    "PS_GLASS", "PS_LEGACY_GLASS", "PS_WATER", "PS_LASER",
    "PS_MATERIAL_METAL", "PS_MATERIAL_FOILAGED",
    "PS_MATERIAL_TRANSLUCENT", "PS_MATERIAL_HAIR",
    "PS_NOR_TEX", "PS_NOR_D_TEX",
    "PS_ALPHA_CUTOFF", "PS_DISSOLVE_UV0", "PS_DISSOLVE_UV1",
    "PS_DISSOLVE_3D", "PS_TRANSMISSION",
    "PS_REFRACTION", "PS_DEPTH_BLUR_DISTANCE",
    "PS_RESPONSIVE_GLOW", "PS_TRANSPARENT_TINTED",
    "PS_ASG_TEX", "PS_ASG_UV1", "PS_TEXTURE_ARRAYS", "PS_NO_DIF_TEX",
    "PS_DIF_UV1",
})


@dataclass(frozen=True, order=True)
class PhaseRequirement:
    phase: str
    policy: str

    @property
    def key(self) -> str:
        return f"{self.phase}.{self.policy}"


@dataclass(frozen=True)
class MainPartPermutationDescriptor:
    selector: str
    output: OutputMode
    quality: Quality
    material: MaterialModel
    normal: NormalSource
    coverage: CoverageMode
    lighting: LightingModel
    reflection: ReflectionMode
    refraction: RefractionMode
    composition: CompositionMode
    diffuse_source: str
    asg_source: str
    features: tuple[str, ...]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]

    def requirements(self) -> tuple[PhaseRequirement, ...]:
        requirements = [
            PhaseRequirement("output", self.output),
            PhaseRequirement("quality", self.quality),
            PhaseRequirement("material", self.material),
            PhaseRequirement("diffuse", self.diffuse_source),
            PhaseRequirement("asg", self.asg_source),
            PhaseRequirement("normal", self.normal),
            PhaseRequirement("coverage", self.coverage),
            PhaseRequirement("lighting", self.lighting),
            PhaseRequirement("reflection", self.reflection),
            PhaseRequirement("refraction", self.refraction),
            PhaseRequirement("composition", self.composition),
        ]
        requirements.extend(
            PhaseRequirement("feature", feature.lower())
            for feature in self.features
        )
        return tuple(requirements)

    def shape(self) -> tuple[str, ...]:
        return tuple(requirement.key for requirement in self.requirements())

    def skeleton(self) -> tuple[str, ...]:
        """Return the semantic graph with cheap permutation axes removed."""
        return tuple(
            requirement.key for requirement in self.requirements()
            if requirement.phase not in {"quality", "reflection"}
        )


@dataclass(frozen=True)
class PhaseImplementation:
    phase: str
    policy: str
    symbol: str
    asset: str

    @property
    def key(self) -> str:
        return f"{self.phase}.{self.policy}"


@dataclass(frozen=True)
class ResolvedPhaseGraph:
    descriptor: MainPartPermutationDescriptor
    implementations: tuple[PhaseImplementation, ...]
    missing: tuple[PhaseRequirement, ...]

    @property
    def phase_inventory_complete(self) -> bool:
        return not self.missing


# This is the seed of the compiler's typed phase registry.  It records actual
# reusable semantic boundaries, not whole selector families.  A phase is added
# only after its HLSL boundary has been recovered and differentially exercised.
PHASE_IMPLEMENTATIONS = (
    PhaseImplementation(
        "output", "transparent_surface", "ComposeMainPartDissolveGlassSurface",
        "main_part_glass_surface_shared.hlsl",
    ),
    PhaseImplementation(
        "output", "transparent_behind", "ComposeMainPartBehindGlass",
        "main_part_glass_behind_light_cap.hlsl",
    ),
    PhaseImplementation("quality", "default", "CompileTimePolicy", ""),
    PhaseImplementation("quality", "low", "CompileTimePolicy", ""),
    PhaseImplementation("quality", "medium", "CompileTimePolicy", ""),
    PhaseImplementation("quality", "high", "CompileTimePolicy", ""),
    PhaseImplementation(
        "material", "standard", "EvaluateMainPartGBufferDiffuse",
        "main_part_gbuffer.hlsl",
    ),
    PhaseImplementation(
        "material", "glass", "EvaluateMainPartGlassMaterial",
        "main_part_glass_surface_shared.hlsl",
    ),
    PhaseImplementation(
        "material", "legacy_glass", "EvaluateMainPartLegacyGlassDirectional",
        "main_part_legacy_glass_multi.hlsl",
    ),
    PhaseImplementation(
        "material", "water", "EvaluateMainPartMultiWaterMaterial",
        "main_part_water_multi_high_frontend.hlsl",
    ),
    PhaseImplementation(
        "material", "laser", "EvaluateMainPartLaserBehind",
        "main_part_laser_behind.hlsl",
    ),
    PhaseImplementation(
        "material", "translucent", "EvaluateMainPartTranslucentPreview",
        "main_part_translucent_preview.hlsl",
    ),
    PhaseImplementation(
        "diffuse", "texture_uv0", "EvaluateMainPartGlassMaterial",
        "main_part_glass_surface_shared.hlsl",
    ),
    PhaseImplementation("diffuse", "none", "CompileTimePolicy", ""),
    PhaseImplementation(
        "diffuse", "texture_uv1", "EvaluateMainPartGBufferDiffuseSample",
        "main_part_gbuffer.hlsl",
    ),
    PhaseImplementation(
        "asg", "texture_uv0", "EvaluateMainPartGlassMaterial",
        "main_part_glass_surface_shared.hlsl",
    ),
    PhaseImplementation("asg", "none", "CompileTimePolicy", ""),
    PhaseImplementation(
        "asg", "texture_uv1", "ApplyMainPartGBufferAsgSample",
        "main_part_gbuffer.hlsl",
    ),
    PhaseImplementation(
        "normal", "geometric", "EvaluateMainPartGlassMaterialGeometricNormal",
        "main_part_glass_surface_shared.hlsl",
    ),
    PhaseImplementation(
        "normal", "tangent_map", "DecodeMainPartTwoSidedNormal",
        "main_part_glass_surface_shared.hlsl",
    ),
    PhaseImplementation(
        "normal", "tangent_detail", "OrientMainPartCustomTilingDetailNormal",
        "main_part_glass_custom_tiling_behind_low.hlsl",
    ),
    PhaseImplementation("coverage", "opaque", "CompileTimePolicy", ""),
    PhaseImplementation("coverage", "alpha_cutout", "CompileTimePolicy", ""),
    PhaseImplementation(
        "coverage", "dissolve_uv0", "EvaluateMainPartUvDissolve",
        "main_part_glass_surface_shared.hlsl",
    ),
    PhaseImplementation(
        "coverage", "dissolve_uv1", "EvaluateMainPartUvDissolve",
        "main_part_glass_surface_shared.hlsl",
    ),
    PhaseImplementation(
        "coverage", "dissolve_3d", "ApplyMainPartDepthDissolve3D",
        "main_part_depth_pixel.hlsl",
    ),
    PhaseImplementation(
        "lighting", "standard", "EvaluateMainPartStandardGlassDirectionalLighting",
        "main_part_glass_surface_shared.hlsl",
    ),
    PhaseImplementation(
        "lighting", "transmission", "EvaluateMainPartGlassDirectionalLighting",
        "main_part_glass_surface_shared.hlsl",
    ),
    PhaseImplementation(
        "lighting", "water", "EvaluateMainPartMultiWaterLighting",
        "main_part_water_multi_high_lighting.hlsl",
    ),
    PhaseImplementation(
        "lighting", "laser", "EvaluateMainPartLaserBehind",
        "main_part_laser_behind.hlsl",
    ),
    PhaseImplementation("reflection", "none", "CompileTimePolicy", ""),
    PhaseImplementation("reflection", "off", "CompileTimePolicy", ""),
    PhaseImplementation(
        "reflection", "single", "EvaluateMainPartSingleReflection",
        "main_part_glass_surface_shared.hlsl",
    ),
    PhaseImplementation(
        "reflection", "multi", "EvaluateMainPartGlassReflectionProbes",
        "main_part_glass_clustered_lighting.hlsl",
    ),
    PhaseImplementation("refraction", "none", "CompileTimePolicy", ""),
    PhaseImplementation("refraction", "basic", "CompileTimePolicy", ""),
    PhaseImplementation("refraction", "depth_blur", "CompileTimePolicy", ""),
    PhaseImplementation(
        "composition", "standard", "ComposeMainPartUnresponsiveGlassSurface",
        "main_part_glass_surface_shared.hlsl",
    ),
    PhaseImplementation(
        "composition", "responsive", "ComposeMainPartDissolveGlassSurface",
        "main_part_glass_surface_shared.hlsl",
    ),
    PhaseImplementation(
        "composition", "tinted", "ComposeMainPartTintedTransmissionGlassSurface",
        "main_part_tinted_glass_surface_transmission_common.hlsl",
    ),
    PhaseImplementation(
        "output", "gbuffer", "WriteMainPartGBuffer",
        "main_part_gbuffer.hlsl",
    ),
    PhaseImplementation(
        "output", "depth", "ApplyMainPartDepthPointAsg",
        "main_part_depth_pixel.hlsl",
    ),
    PhaseImplementation(
        "output", "picking", "WriteMainPartPickingColor",
        "main_part_picking_pixel.hlsl",
    ),
    PhaseImplementation(
        "output", "overlay", "WriteMainPartEditorOverlay",
        "main_part_overlay_pixel.hlsl",
    ),
    PhaseImplementation(
        "output", "wireframe", "WriteMainPartWireframe",
        "main_part_overlay_pixel.hlsl",
    ),
    PhaseImplementation(
        "output", "early_gforward", "WriteMainPartEarlyGForward",
        "main_part_early_gforward.hlsl",
    ),
    PhaseImplementation(
        "output", "preview", "EvaluateMainPartTranslucentPreview",
        "main_part_translucent_preview.hlsl",
    ),
    PhaseImplementation(
        "output", "visualization", "EvaluateMainPartVisualization",
        "main_part_visualization.hlsl",
    ),
    PhaseImplementation(
        "feature", "ps_flip_backface_normals", "DecodeMainPartTwoSidedNormal",
        "main_part_glass_surface_shared.hlsl",
    ),
    PhaseImplementation(
        "feature", "ps_light_cap", "ComputeMainPartLightCapUv",
        "main_part_light_cap.hlsl",
    ),
    PhaseImplementation(
        "feature", "ps_fbdrf_dif", "SampleMainPartDirectionalMapDiffuse",
        "main_part_directional_map.hlsl",
    ),
    PhaseImplementation(
        "feature", "ps_mat_cap_dif", "ApplyMainPartGBufferMatCapDiffuse",
        "main_part_gbuffer.hlsl",
    ),
    PhaseImplementation(
        "feature", "ps_mat_cap_masked", "ApplyMainPartGBufferMaskedMatCap",
        "main_part_gbuffer.hlsl",
    ),
    PhaseImplementation(
        "feature", "ps_light_cap_masked", "ApplyMainPartGBufferLightCap",
        "main_part_gbuffer.hlsl",
    ),
    PhaseImplementation(
        "feature", "ps_ao_tex", "ApplyMainPartGBufferAo",
        "main_part_gbuffer.hlsl",
    ),
    PhaseImplementation(
        "feature", "ps_custom_tiling", "OrientMainPartCustomTilingDetailNormal",
        "main_part_glass_custom_tiling_behind_low.hlsl",
    ),
    PhaseImplementation(
        "feature", "ps_set_params", "EvaluateMainPartSetParamsDirectionalLighting",
        "main_part_glass_set_params_behind_single.hlsl",
    ),
    PhaseImplementation(
        "feature", "ps_nor_d_uv1", "OrientMainPartCustomTilingDetailNormal",
        "main_part_glass_custom_tiling_behind_low.hlsl",
    ),
)


def phase_registry() -> dict[str, PhaseImplementation]:
    return {implementation.key: implementation
            for implementation in PHASE_IMPLEMENTATIONS}


def resolve_phase_graph(
    descriptor: MainPartPermutationDescriptor,
    registry: dict[str, PhaseImplementation] | None = None,
) -> ResolvedPhaseGraph:
    implementations_by_key = registry or phase_registry()
    implementations = []
    missing = []
    for requirement in descriptor.requirements():
        implementation = implementations_by_key.get(requirement.key)
        if implementation is None:
            missing.append(requirement)
        else:
            implementations.append(implementation)
    return ResolvedPhaseGraph(
        descriptor=descriptor,
        implementations=tuple(implementations),
        missing=tuple(missing),
    )


def match_validated_graph_template(
    defines: Iterable[str], source: str,
) -> str | None:
    """Return a template only when its complete wiring is already validated."""
    # Local import keeps inventory independent of recipe installation.
    from .recipes.main_part_graph_templates import (
        find_main_part_graph_template,
    )

    template = find_main_part_graph_template(defines, source)
    return template.name if template is not None else None


def _select(values: frozenset[str], mapping: dict[str, Any], default: Any) -> Any:
    selected = [value for define, value in mapping.items() if define in values]
    return selected[0] if len(selected) == 1 else default


def _semantic_label(parameter: Any) -> str:
    return f"{parameter.semantic.name}{parameter.semantic.index}"


def describe_main_part_permutation(
    selector: str, defines: Iterable[str], source: str,
) -> MainPartPermutationDescriptor:
    values = frozenset(defines)
    output = _select(values, PERMUTATION_OUTPUTS, OutputMode.UNKNOWN)
    quality = _select(values, {
        "PS_SHADER_QUALITY_LOW": Quality.LOW,
        "PS_SHADER_QUALITY_MEDIUM": Quality.MEDIUM,
        "PS_SHADER_QUALITY_HIGH": Quality.HIGH,
    }, Quality.DEFAULT)
    material = _select(values, {
        "PS_WATER": MaterialModel.WATER,
        "PS_LASER": MaterialModel.LASER,
        "PS_LEGACY_GLASS": MaterialModel.LEGACY_GLASS,
        "PS_GLASS": MaterialModel.GLASS,
        "PS_MATERIAL_METAL": MaterialModel.METAL,
        "PS_MATERIAL_FOILAGED": MaterialModel.FOLIAGE,
        "PS_MATERIAL_TRANSLUCENT": MaterialModel.TRANSLUCENT,
        "PS_MATERIAL_HAIR": MaterialModel.HAIR,
    }, MaterialModel.STANDARD)
    normal = (
        NormalSource.TANGENT_DETAIL if "PS_NOR_D_TEX" in values
        else NormalSource.TANGENT_MAP if "PS_NOR_TEX" in values
        else NormalSource.GEOMETRIC
    )
    coverage = (
        CoverageMode.DISSOLVE_3D if "PS_DISSOLVE_3D" in values
        else CoverageMode.DISSOLVE_UV1 if "PS_DISSOLVE_UV1" in values
        else CoverageMode.DISSOLVE_UV0 if "PS_DISSOLVE_UV0" in values
        else CoverageMode.ALPHA_CUTOUT if "PS_ALPHA_CUTOFF" in values
        else CoverageMode.OPAQUE
    )
    lighting = (
        LightingModel.WATER if material == MaterialModel.WATER
        else LightingModel.LASER if material == MaterialModel.LASER
        else LightingModel.TRANSMISSION if "PS_TRANSMISSION" in values
        else LightingModel.STANDARD
    )
    reflection = _select(values, {
        "PS_REFLECTION_AS_DIFFUSE": ReflectionMode.AS_DIFFUSE,
        "PS_REFLECTION_MULTI": ReflectionMode.MULTI,
        "PS_REFLECTION_SINGLE": ReflectionMode.SINGLE,
        "PS_REFLECTION_OFF": ReflectionMode.OFF,
    }, ReflectionMode.NONE)
    refraction = (
        RefractionMode.DEPTH_BLUR if "PS_DEPTH_BLUR_DISTANCE" in values
        else RefractionMode.BASIC if "PS_REFRACTION" in values
        else RefractionMode.NONE
    )
    composition = (
        CompositionMode.RESPONSIVE if "PS_RESPONSIVE_GLOW" in values
        else CompositionMode.TINTED if "PS_TRANSPARENT_TINTED" in values
        else CompositionMode.STANDARD
    )
    diffuse_source = (
        "none" if "PS_NO_DIF_TEX" in values
        else "texture_array" if "PS_TEXTURE_ARRAYS" in values
        else "texture_uv1" if "PS_DIF_UV1" in values
        else "texture_uv0"
    )
    asg_source = (
        "none" if "PS_ASG_TEX" not in values
        else "texture_uv1" if "PS_ASG_UV1" in values
        else "texture_uv0"
    )
    ignored = AXIS_DEFINES | frozenset(
        define for define in values if define.startswith("TRANSFER_")
    )
    features = tuple(sorted(values - ignored))
    try:
        _signature, parameters = parse_entry_signature(source, "commonPS")
    except RuntimeError:
        parameters = ()
    inputs = tuple(_semantic_label(parameter) for parameter in parameters
                   if not parameter.output)
    outputs = tuple(_semantic_label(parameter) for parameter in parameters
                    if parameter.output)
    return MainPartPermutationDescriptor(
        selector=selector, output=output, quality=quality,
        material=material, normal=normal, coverage=coverage,
        lighting=lighting, reflection=reflection, refraction=refraction,
        composition=composition, diffuse_source=diffuse_source,
        asg_source=asg_source, features=features, inputs=inputs,
        outputs=outputs,
    )


def _is_instruction_ordered(source: str) -> bool:
    return any(marker in source for marker in (
        "partPositionState", "animationTransformState",
        "reflectionAndRefractionState", "gbufferAndPreviewState",
    ))


def build_main_part_permutation_graph(corpus: Path) -> dict[str, Any]:
    manifest = json.loads(
        (corpus / "manifest.json").read_text(encoding="utf-8")
    )
    snippets = corpus / "semantic" / "include" / "main_part"
    registry = phase_registry()
    records: list[dict[str, Any]] = []
    shape_groups: dict[tuple[str, ...], list[str]] = defaultdict(list)
    missing_groups: Counter[tuple[str, ...]] = Counter()
    missing_phase_counts: Counter[str] = Counter()
    output_counts: Counter[str] = Counter()
    remaining_output_counts: Counter[str] = Counter()
    remaining_phase_complete_outputs: Counter[str] = Counter()
    phase_complete_count = 0
    instruction_ordered_count = 0
    instruction_ordered_phase_complete_count = 0
    instruction_ordered_template_ready_count = 0
    skeleton_groups: dict[tuple[str, ...], list[MainPartPermutationDescriptor]] = (
        defaultdict(list)
    )

    for shader in manifest["shaders"]:
        if shader["source_name"] != "main_part" or shader["stage"] != "pixel":
            continue
        source = (snippets / f"{shader['selector']}.hlsl").read_text(
            encoding="utf-8"
        )
        descriptor = describe_main_part_permutation(
            shader["selector"], shader["defines"], source
        )
        graph = resolve_phase_graph(descriptor, registry)
        requirements = descriptor.requirements()
        missing = tuple(sorted(requirement.key for requirement in graph.missing))
        instruction_ordered = _is_instruction_ordered(source)
        graph_template = match_validated_graph_template(
            shader["defines"], source
        )
        complete = graph.phase_inventory_complete
        phase_complete_count += int(complete)
        instruction_ordered_count += int(instruction_ordered)
        output_counts[descriptor.output] += 1
        if instruction_ordered:
            remaining_output_counts[descriptor.output] += 1
            if missing:
                missing_groups[missing] += 1
            missing_phase_counts.update(missing)
            instruction_ordered_phase_complete_count += int(complete)
            instruction_ordered_template_ready_count += int(
                graph_template is not None
            )
            if complete:
                remaining_phase_complete_outputs[descriptor.output] += 1
            skeleton_groups[descriptor.skeleton()].append(descriptor)
        shape_groups[descriptor.shape()].append(descriptor.selector)
        record = asdict(descriptor)
        record.update({
            "requirements": [requirement.key for requirement in requirements],
            "implementations": [implementation.symbol
                                for implementation in graph.implementations],
            "missing_phases": list(missing),
            "phase_inventory_complete": complete,
            "instruction_ordered": instruction_ordered,
            "graph_template": graph_template,
        })
        records.append(record)

    clusters = [
        {
            "count": len(selectors),
            "shape": list(shape),
            "selectors": selectors,
            "instruction_ordered_count": sum(
                next(record for record in records
                     if record["selector"] == selector)["instruction_ordered"]
                for selector in selectors
            ),
        }
        for shape, selectors in shape_groups.items()
    ]
    clusters.sort(key=lambda cluster: (-cluster["instruction_ordered_count"],
                                       -cluster["count"], cluster["shape"]))
    missing_rank = [
        {"count": count, "missing_phases": list(missing)}
        for missing, count in missing_groups.most_common()
    ]
    skeletons = [
        {
            "count": len(descriptors),
            "skeleton": list(skeleton),
            "qualities": sorted({descriptor.quality for descriptor in descriptors}),
            "reflections": sorted(
                {descriptor.reflection for descriptor in descriptors}
            ),
            "phase_inventory_complete_count": sum(
                not resolve_phase_graph(descriptor, registry).missing
                for descriptor in descriptors
            ),
            "selectors": [descriptor.selector for descriptor in descriptors],
        }
        for skeleton, descriptors in skeleton_groups.items()
    ]
    skeletons.sort(key=lambda item: (-item["count"], item["skeleton"]))
    return {
        "shader_count": len(records),
        "instruction_ordered_count": instruction_ordered_count,
        "structural_count": len(records) - instruction_ordered_count,
        "phase_inventory_complete_count": phase_complete_count,
        "instruction_ordered_phase_inventory_complete_count":
            instruction_ordered_phase_complete_count,
        # These have all individual typed ingredients, but no validated graph
        # template currently wires their particular combination together.
        "instruction_ordered_uncomposed_count":
            instruction_ordered_phase_complete_count
            - instruction_ordered_template_ready_count,
        "instruction_ordered_template_ready_count":
            instruction_ordered_template_ready_count,
        "output_counts": dict(sorted(output_counts.items())),
        "remaining_output_counts": dict(sorted(remaining_output_counts.items())),
        "remaining_phase_complete_outputs": dict(
            sorted(remaining_phase_complete_outputs.items())
        ),
        "phase_registry": [asdict(value) for value in PHASE_IMPLEMENTATIONS],
        "missing_phase_groups": missing_rank,
        "missing_phase_counts": dict(missing_phase_counts.most_common()),
        "cluster_count": len(clusters),
        "clusters": clusters,
        "skeleton_count": len(skeletons),
        "skeletons": skeletons,
        "records": records,
    }


def summarize_main_part_permutation_graph(
    report: dict[str, Any], *, limit: int = 25,
) -> dict[str, Any]:
    summary = {
        key: value for key, value in report.items()
        if key not in {"records", "clusters", "skeletons"}
    }
    summary["missing_phase_group_count"] = len(report["missing_phase_groups"])
    summary["missing_phase_groups"] = report["missing_phase_groups"][:limit]
    summary["largest_skeletons"] = report["skeletons"][:limit]
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    report = build_main_part_permutation_graph(args.corpus)
    if args.summary_only:
        report = summarize_main_part_permutation_graph(report)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
