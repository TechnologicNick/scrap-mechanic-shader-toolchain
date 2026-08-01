"""Induce reusable graph templates from recovered ``main_part`` families.

This is deliberately a compiler pass, not another selector recognizer. It
normalizes entry bodies into operations, anti-unifies complete families, and
describes policy holes through typed live values and runtime effects.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

from .main_part_canonical_ir import canonicalize_main_part_body
from .main_part_family_miner import mine_main_part_families
from .main_part_phase_contracts import contract_is_typed, phase_contract_registry


_ASSIGNMENTS = frozenset({
    "=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=",
})
_VALUE = re.compile(r"%[A-Za-z0-9_]+")
_RESOURCE = re.compile(r"\b(?:t|ta|sb)[A-Z][A-Za-z0-9_]*\b")
_CBUFFER_VALUE = re.compile(r"\bcb_[A-Za-z0-9_]+\b")


@dataclass(frozen=True)
class NormalizedOperation:
    kind: str
    fingerprint: str
    reads: tuple[str, ...]
    writes: tuple[str, ...]
    resources: tuple[str, ...]
    effects: tuple[str, ...]
    control_depth: int


@dataclass(frozen=True)
class TypedValue:
    name: str
    type_name: str


@dataclass(frozen=True)
class InducedPolicyHole:
    index: int
    suggested_symbol: str
    operation_count: int
    variant_count: int
    controlled_by: tuple[str, ...]
    live_inputs: tuple[TypedValue, ...]
    live_outputs: tuple[TypedValue, ...]
    resources: tuple[str, ...]
    effects: tuple[str, ...]
    matched_phases: tuple[str, ...]
    variant_members: tuple[tuple[str, tuple[str, ...]], ...]


@dataclass(frozen=True)
class InducedFamilyTemplate:
    family_key: str
    suggested_name: str
    selectors: tuple[str, ...]
    skeleton: tuple[str, ...]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    common_operation_ratio: float
    common_region_count: int
    holes: tuple[InducedPolicyHole, ...]
    typed_phase_ratio: float
    axis_control_ratio: float
    readiness: str
    blockers: tuple[str, ...]


def _statements(canonical_body: str) -> list[tuple[list[str], int]]:
    tokens = canonical_body.split()
    statements: list[tuple[list[str], int]] = []
    current: list[str] = []
    control_depth = 0
    parentheses = 0
    for token in tokens:
        if token == "(" :
            parentheses += 1
        elif token == ")":
            parentheses = max(0, parentheses - 1)
        if token == "{" and parentheses == 0:
            if current:
                statements.append((current, control_depth))
                current = []
            control_depth += 1
            continue
        if token == "}" and parentheses == 0:
            if current:
                statements.append((current, control_depth))
                current = []
            control_depth = max(0, control_depth - 1)
            continue
        current.append(token)
        if token == ";" and parentheses == 0:
            statements.append((current, control_depth))
            current = []
    if current:
        statements.append((current, control_depth))
    return statements


def _kind(tokens: list[str]) -> str:
    first = tokens[0] if tokens else ""
    if first in {"if", "else", "switch"}:
        return "branch"
    if first in {"while", "for", "do"}:
        return "loop"
    if first in {"return", "discard", "break", "continue"}:
        return first
    if any(token in _ASSIGNMENTS for token in tokens):
        return "assignment"
    return "call" if "(" in tokens else "declaration"


def _value_type(name: str) -> str:
    lowered = name.lower()
    if lowered.startswith("%in_") or lowered.startswith("%out_"):
        for marker, type_name in (
            ("sv_isfrontface", "uint"), ("cutoff", "float"),
            ("uv", "float2"), ("screen_uv", "float3"),
            ("view_position", "float3"), ("normal", "float3"),
            ("tangent", "float3"), ("bitangent", "float3"),
            ("vertexcolor", "float4"), ("fog_color", "float4"),
            ("sv_position", "float4"), ("sv_target", "float4"),
        ):
            if marker in lowered:
                return type_name
    return "float4"


def build_operation_ir(source: str) -> tuple[NormalizedOperation, ...]:
    """Lower one recovered entry body to stable dependency-aware operations."""
    body = canonicalize_main_part_body(source)
    operations: list[NormalizedOperation] = []
    for tokens, depth in _statements(body):
        kind = _kind(tokens)
        assignment = next(
            (index for index, token in enumerate(tokens)
             if token in _ASSIGNMENTS),
            None,
        )
        values = _VALUE.findall(" ".join(tokens))
        writes = tuple(values[:1]) if assignment is not None else ()
        reads = tuple(dict.fromkeys(
            values[1:] if assignment is not None else values
        ))
        resources = tuple(sorted(set(
            _RESOURCE.findall(" ".join(tokens))
            + _CBUFFER_VALUE.findall(" ".join(tokens))
        )))
        effects = []
        text = " ".join(tokens)
        if kind == "discard" or " discard " in f" {text} ":
            effects.append("discard")
        if any(value in text for value in ("ddx", "ddy")):
            effects.append("derivatives")
        if any(value.startswith("%out_") for value in writes):
            effects.append("render_target")
        # Definition sequence is intentionally absent from the fingerprint;
        # decompiler register allocation remains data-flow metadata only.
        fingerprint_tokens = [
            "%value" if _VALUE.fullmatch(token) else token
            for token in tokens
        ]
        fingerprint = hashlib.sha256(
            (kind + "|" + " ".join(fingerprint_tokens)).encode("utf-8")
        ).hexdigest()[:20]
        operations.append(NormalizedOperation(
            kind=kind,
            fingerprint=fingerprint,
            reads=reads,
            writes=writes,
            resources=resources,
            effects=tuple(effects),
            control_depth=depth,
        ))
    return tuple(operations)


def _lcs(left: list[str], right: list[str]) -> list[str]:
    matcher = SequenceMatcher(a=left, b=right, autojunk=False)
    output: list[str] = []
    for block in matcher.get_matching_blocks():
        output.extend(left[block.a:block.a + block.size])
    return output


def _common_sequence(streams: list[list[str]]) -> list[str]:
    common = list(streams[0]) if streams else []
    for stream in streams[1:]:
        common = _lcs(common, stream)
        if not common:
            break
    return common


def _anchor_positions(stream: list[str], anchors: list[str]) -> list[int]:
    positions: list[int] = []
    cursor = 0
    for anchor in anchors:
        while cursor < len(stream) and stream[cursor] != anchor:
            cursor += 1
        if cursor == len(stream):
            raise RuntimeError("anti-unification anchor was lost")
        positions.append(cursor)
        cursor += 1
    return positions


def _segments(length: int, positions: list[int]) -> list[tuple[int, int]]:
    bounds = [-1, *positions, length]
    return [(bounds[index] + 1, bounds[index + 1])
            for index in range(len(bounds) - 1)]


def _live_values(
    operations: tuple[NormalizedOperation, ...], start: int, end: int,
) -> tuple[tuple[TypedValue, ...], tuple[TypedValue, ...]]:
    before = {value for operation in operations[:start]
              for value in operation.writes}
    defined: set[str] = set()
    live_inputs: set[str] = set()
    for operation in operations[start:end]:
        live_inputs.update(
            value for value in operation.reads
            if value not in defined
        )
        defined.update(operation.writes)
    later_reads = {value for operation in operations[end:]
                   for value in operation.reads}
    live_outputs = defined & later_reads
    # A recovered temporary read before its first local definition is still a
    # valid live-in even if the decompiler declared it at function scope.
    live_inputs |= {value for value in before if value in live_inputs}
    typed_inputs = tuple(
        TypedValue(value, _value_type(value)) for value in sorted(live_inputs)
    )
    typed_outputs = tuple(
        TypedValue(value, _value_type(value)) for value in sorted(live_outputs)
    )
    return typed_inputs, typed_outputs


def _phase_matches(resources: set[str], effects: set[str]) -> tuple[str, ...]:
    matches: set[str] = set()
    if resources & {"tDif", "tAsg", "tNor", "cb_dissolve"}:
        matches.add("material.glass")
    if "tCutoff" in resources or "cb_dissolve" in resources:
        matches.add("coverage.dissolve")
    if resources & {"tLightColorMap", "taCookies"}:
        matches.add("lighting.standard")
    if resources & {"taCascades", "tCloudMap"}:
        matches.add("lighting.high_visibility")
    if "taReflection" in resources:
        matches.add(
            "reflection.multi"
            if resources & {"sbVoxelLightIds", "cb_reflections"}
            else "reflection.single"
        )
    if resources & {"tFrame", "tIndirect"} or "render_target" in effects:
        matches.add("composition.standard")
    if "tDepth" in resources:
        matches.add("refraction.basic")
    return tuple(sorted(matches))


def _controlled_axes(
    variants: list[tuple[str, str, str]],
) -> tuple[str, ...]:
    controlled = []
    for axis, field in (("quality", 0), ("reflection", 1)):
        by_value: dict[str, set[str]] = {}
        for quality, reflection, fingerprint in variants:
            value = (quality, reflection)[field]
            by_value.setdefault(value, set()).add(fingerprint)
        if by_value and all(len(values) == 1 for values in by_value.values()):
            controlled.append(axis)
    if not controlled:
        # Some phases (notably reflection composition at high quality) are a
        # true product of both axes. A complete policy coordinate still gives
        # the compiler a deterministic compile-time implementation choice.
        by_coordinate: dict[tuple[str, str], set[str]] = {}
        for quality, reflection, fingerprint in variants:
            by_coordinate.setdefault((quality, reflection), set()).add(
                fingerprint
            )
        if by_coordinate and all(
            len(values) == 1 for values in by_coordinate.values()
        ):
            controlled.extend(("quality", "reflection"))
    return tuple(controlled)


def _pascal(value: str) -> str:
    return "".join(part.capitalize() for part in re.split(r"[^A-Za-z0-9]+", value)
                   if part)


def _suggested_family_name(
    skeleton: tuple[str, ...], inputs: tuple[str, ...] = (),
    outputs: tuple[str, ...] = (),
) -> str:
    """Name a graph from semantic decisions, never recovered identities.

    Output topology and normal strategy are deliberately retained: both have
    proved to distinguish otherwise similar transparent families.  Only true
    no-op defaults are omitted.  The interface is used as a final semantic
    discriminator for skeletons shared by multiple entry-point shapes.
    """
    preferred: list[str] = []
    defaults = {
        "material": {"standard"},
        "diffuse": {"texture_uv0"},
        "asg": {"texture_uv0"},
        "coverage": {"opaque"},
        "lighting": {"standard"},
        "reflection": {"none"},
        "refraction": {"none"},
        "composition": {"standard"},
        "feature": {"ps_flip_backface_normals"},
    }
    for key in skeleton:
        category, _, value = key.partition(".")
        if category not in {
            "output", "material", "diffuse", "asg", "normal", "coverage",
            "lighting", "reflection", "refraction", "composition", "feature",
        }:
            continue
        if value in defaults.get(category, set()):
            continue
        value = value.removeprefix("ps_")
        # Preserve the category where identical values can mean different
        # decisions (for example diffuse_uv1 versus asg_uv1).
        if category in {"diffuse", "asg", "reflection", "refraction"}:
            value = f"{category}_{value.removeprefix('texture_')}"
        preferred.append(value)
    if not preferred:
        preferred.append("main_part_surface")
    # Most entry interfaces are already encoded by output.*.  Add only
    # exceptional semantic channels, keeping names readable and deterministic.
    interface_markers = (
        ("FOG_COLOR", "fog"), ("CUTOFF", "cutoff"),
        ("PLANE", "plane"), ("OCCLUSION", "occlusion"),
    )
    interface = " ".join((*inputs, *outputs))
    preferred.extend(
        marker for semantic, marker in interface_markers
        if semantic in interface and marker not in preferred
    )
    return "_".join(dict.fromkeys(preferred))


def induce_family_template(
    candidate: dict[str, Any], sources: dict[str, str],
) -> InducedFamilyTemplate:
    selectors = tuple(candidate["selectors"])
    operations = {selector: build_operation_ir(sources[selector])
                  for selector in selectors}
    streams = {
        selector: [operation.fingerprint for operation in operations[selector]]
        for selector in selectors
    }
    common = _common_sequence(list(streams.values()))
    positions = {
        selector: _anchor_positions(streams[selector], common)
        for selector in selectors
    }
    segments = {
        selector: _segments(len(streams[selector]), positions[selector])
        for selector in selectors
    }
    policy_by_selector = {
        selector: tuple(policy)
        for selector, policy in zip(
            candidate["selectors"], candidate["observed_policies"], strict=True
        )
    }
    # Selectors and observed policies are independently sorted in the miner.
    # Recover policies from wrapper-independent manifest metadata when supplied.
    policy_by_selector.update(candidate.get("selector_policies", {}))

    candidate_inputs = tuple(candidate.get("inputs", ()))
    candidate_outputs = tuple(candidate.get("outputs", ()))
    family_name = _suggested_family_name(
        tuple(candidate["skeleton"]), candidate_inputs, candidate_outputs,
    )
    holes: list[InducedPolicyHole] = []
    for segment_index in range(len(common) + 1):
        slices = {
            selector: operations[selector][
                segments[selector][segment_index][0]:
                segments[selector][segment_index][1]
            ]
            for selector in selectors
        }
        if not any(slices.values()):
            continue
        variants_by_hash: dict[str, list[str]] = {}
        policy_variants: list[tuple[str, str, str]] = []
        for selector, values in slices.items():
            fingerprint = hashlib.sha256(
                "|".join(value.fingerprint for value in values).encode("ascii")
            ).hexdigest()[:16]
            variants_by_hash.setdefault(fingerprint, []).append(selector)
            policy = policy_by_selector.get(selector, ("unknown", "unknown"))
            policy_variants.append((policy[0], policy[1], fingerprint))
        baseline_selector = selectors[0]
        start, end = segments[baseline_selector][segment_index]
        live_inputs, live_outputs = _live_values(
            operations[baseline_selector], start, end
        )
        all_operations = [operation for values in slices.values()
                          for operation in values]
        resources = {resource for operation in all_operations
                     for resource in operation.resources}
        effects = {effect for operation in all_operations
                   for effect in operation.effects}
        matched_phases = _phase_matches(resources, effects)
        semantic_role = matched_phases[0] if len(matched_phases) == 1 \
            else "policy_region"
        suggested_symbol = (
            f"Evaluate{_pascal(family_name)}{_pascal(semantic_role)}"
            f"{len(holes)}"
        )
        holes.append(InducedPolicyHole(
            index=len(holes),
            suggested_symbol=suggested_symbol,
            operation_count=max(map(len, slices.values())),
            variant_count=len(variants_by_hash),
            controlled_by=_controlled_axes(policy_variants),
            live_inputs=live_inputs,
            live_outputs=live_outputs,
            resources=tuple(sorted(resources)),
            effects=tuple(sorted(effects)),
            matched_phases=matched_phases,
            variant_members=tuple(sorted(
                (key, tuple(sorted(value)))
                for key, value in variants_by_hash.items()
            )),
        ))

    phase_registry = phase_contract_registry()
    skeleton = tuple(candidate["skeleton"])
    typed = sum(
        contract_is_typed(phase_registry.get(key))
        for key in skeleton
    )
    typed_ratio = typed / max(1, len(skeleton))
    controlled_holes = sum(bool(hole.controlled_by) for hole in holes)
    axis_ratio = controlled_holes / max(1, len(holes))
    matched_holes = sum(bool(hole.matched_phases) for hole in holes)
    matched_hole_ratio = matched_holes / max(1, len(holes))
    blockers = []
    if not candidate["matrix_complete"]:
        blockers.append("incomplete_policy_matrix")
    if axis_ratio < 0.6:
        blockers.append("non_axis_structural_divergence")
    if len(holes) > 24:
        blockers.append("fragmented_control_flow")
    if not blockers and typed_ratio >= 0.35 and matched_hole_ratio == 1.0:
        readiness = "auto_composable"
    elif not blockers and (
        typed_ratio >= 0.35 or matched_hole_ratio >= 0.25
    ):
        readiness = "auto_with_typed_residuals"
    elif not blockers:
        readiness = "needs_phase_contracts"
    elif "non_axis_structural_divergence" in blockers:
        readiness = "needs_semantic_partition"
    else:
        readiness = "irregular"
    common_regions = 0
    previous = -2
    baseline_positions = positions[selectors[0]]
    for value in baseline_positions:
        if value != previous + 1:
            common_regions += 1
        previous = value
    return InducedFamilyTemplate(
        family_key=candidate["family_key"], suggested_name=family_name,
        selectors=selectors,
        skeleton=skeleton,
        inputs=candidate_inputs, outputs=candidate_outputs,
        common_operation_ratio=len(common) / max(1, len(streams[selectors[0]])),
        common_region_count=common_regions,
        holes=tuple(holes), typed_phase_ratio=typed_ratio,
        axis_control_ratio=axis_ratio, readiness=readiness,
        blockers=tuple(blockers),
    )


def build_synthesis_readiness_report(
    corpus: Path, *, minimum_members: int = 2,
) -> dict[str, Any]:
    family_report = mine_main_part_families(
        corpus, minimum_members=minimum_members
    )
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    policies = {
        shader["selector"]: {
            "quality": (
                "high" if "PS_SHADER_QUALITY_HIGH" in shader["defines"]
                else "medium" if "PS_SHADER_QUALITY_MEDIUM" in shader["defines"]
                else "default"
            ),
            "reflection": (
                "multi" if "PS_REFLECTION_MULTI" in shader["defines"]
                else "single" if "PS_REFLECTION_SINGLE" in shader["defines"]
                else "off"
            ),
        }
        for shader in manifest["shaders"]
    }
    snippet_root = corpus / "semantic" / "include" / "main_part"
    templates = []
    for candidate in family_report["candidates"]:
        candidate = dict(candidate)
        candidate["selector_policies"] = {
            selector: (
                policies[selector]["quality"],
                policies[selector]["reflection"],
            )
            for selector in candidate["selectors"]
        }
        sources = {
            selector: (snippet_root / f"{selector}.hlsl").read_text(
                encoding="utf-8"
            )
            for selector in candidate["selectors"]
        }
        templates.append(induce_family_template(candidate, sources))
    templates.sort(key=lambda value: (
        {"auto_composable": 0, "auto_with_typed_residuals": 1,
         "needs_phase_contracts": 2, "needs_semantic_partition": 3,
         "irregular": 4}[value.readiness],
        -len(value.selectors), -value.axis_control_ratio,
        -value.common_operation_ratio, value.family_key,
    ))
    readiness = Counter(template.readiness for template in templates)
    contracts = phase_contract_registry()
    contract_gap_families: Counter[str] = Counter()
    contract_gap_shaders: Counter[str] = Counter()
    matched_phases: Counter[str] = Counter()
    for template in templates:
        for key in template.skeleton:
            contract = contracts.get(key)
            if contract is not None and not contract_is_typed(contract):
                contract_gap_families[key] += 1
                contract_gap_shaders[key] += len(template.selectors)
        for hole in template.holes:
            matched_phases.update(hole.matched_phases)
    contract_backlog = [
        {
            "phase": key,
            "family_count": contract_gap_families[key],
            "shader_count": contract_gap_shaders[key],
            "symbol": contracts[key].symbol,
            "asset": contracts[key].asset,
        }
        for key in sorted(
            contract_gap_families,
            key=lambda value: (
                -contract_gap_shaders[value],
                -contract_gap_families[value], value,
            ),
        )
    ]
    return {
        "family_count": len(templates),
        "shader_count": sum(len(template.selectors) for template in templates),
        "readiness_counts": dict(sorted(readiness.items())),
        "auto_synthesizable_shader_count": sum(
            len(template.selectors) for template in templates
            if template.readiness in {
                "auto_composable", "auto_with_typed_residuals"
            }
        ),
        "unmatched_residual_hole_count": sum(
            not hole.matched_phases
            for template in templates for hole in template.holes
        ),
        "matched_phase_counts": dict(sorted(matched_phases.items())),
        "phase_contract_backlog": contract_backlog,
        "templates": [asdict(template) for template in templates],
    }


def summarize_synthesis_readiness(
    report: dict[str, Any], *, limit: int = 25,
) -> dict[str, Any]:
    return {
        **{key: value for key, value in report.items() if key != "templates"},
        "templates": report["templates"][:limit],
    }


def write_synthesis_specifications(
    report: dict[str, Any], destination: Path,
) -> dict[str, Any]:
    """Write declarative inputs for the generic graph renderer.

    Filenames and symbols are semantic. Duplicate names are rejected instead
    of being hidden behind selector or content hashes.
    """
    destination.mkdir(parents=True, exist_ok=True)
    ready = [
        template for template in report["templates"]
        if template["readiness"] in {
            "auto_composable", "auto_with_typed_residuals"
        }
    ]
    names = [template["suggested_name"] for template in ready]
    duplicates = sorted(
        name for name, count in Counter(names).items() if count > 1
    )
    if duplicates:
        raise RuntimeError(
            "synthesis family names need more semantic axes: "
            + ", ".join(duplicates)
        )
    files = []
    for template in ready:
        specification = {
            "family": template["suggested_name"],
            "selectors": template["selectors"],
            "match": template["skeleton"],
            "interface": {
                "inputs": template.get("inputs", ()),
                "outputs": template.get("outputs", ()),
            },
            "axes": sorted({
                axis
                for hole in template["holes"]
                for axis in hole["controlled_by"]
            }),
            "common_operation_ratio": template["common_operation_ratio"],
            "phases": [
                {
                    "symbol": hole["suggested_symbol"],
                    "controlled_by": hole["controlled_by"],
                    "inputs": hole["live_inputs"],
                    "outputs": hole["live_outputs"],
                    "resources": hole["resources"],
                    "effects": hole["effects"],
                    "matches": hole["matched_phases"],
                    "implementations": hole["variant_members"],
                }
                for hole in template["holes"]
            ],
        }
        filename = f"{template['suggested_name']}.json"
        (destination / filename).write_text(
            json.dumps(specification, indent=2, sort_keys=True) + "\n",
            encoding="utf-8", newline="\n",
        )
        files.append(filename)
    campaign = {
        "family_count": len(ready),
        "shader_count": sum(len(value["selectors"]) for value in ready),
        "specifications": files,
    }
    (destination / "campaign.json").write_text(
        json.dumps(campaign, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    return campaign
