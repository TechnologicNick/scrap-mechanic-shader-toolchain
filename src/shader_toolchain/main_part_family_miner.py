"""Mine batch-sized graph families from the complete ``main_part`` corpus."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from .main_part_canonical_ir import (
    align_canonical_bodies,
    canonical_family_key,
    canonicalize_main_part_shader,
)
from .main_part_permutation_graph import (
    MainPartPermutationDescriptor,
    describe_main_part_permutation,
    match_validated_graph_template,
    resolve_phase_graph,
)
from .main_part_phase_contracts import fixture_closure


_REGISTER_STATE_MARKERS = (
    "partPositionState", "animationTransformState",
    "reflectionAndRefractionState", "gbufferAndPreviewState",
)


@dataclass(frozen=True)
class MinedFamilyMember:
    descriptor: MainPartPermutationDescriptor
    behavior_key: str
    canonical_body: str


@dataclass(frozen=True)
class MinedFamilyCandidate:
    family_key: str
    skeleton: tuple[str, ...]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    selectors: tuple[str, ...]
    qualities: tuple[str, ...]
    reflections: tuple[str, ...]
    observed_policies: tuple[tuple[str, str], ...]
    missing_policies: tuple[tuple[str, str], ...]
    behavior_variant_count: int
    common_token_ratio: float
    common_block_count: int
    variant_region_count: int
    required_assets: tuple[str, ...]
    activation_fixtures: tuple[str, ...]
    unlock_score: float

    @property
    def member_count(self) -> int:
        return len(self.selectors)

    @property
    def matrix_complete(self) -> bool:
        return not self.missing_policies

    def graph_specification_draft(self) -> dict[str, Any]:
        """Emit the data needed for a selector-independent graph spec."""
        return {
            "name": f"family_{self.family_key[:12]}",
            "match": list(self.skeleton),
            "interface": {
                "inputs": list(self.inputs),
                "outputs": list(self.outputs),
            },
            "axes": {
                "quality": list(self.qualities),
                "reflection": list(self.reflections),
            },
            "required_assets": list(self.required_assets),
            "activation_fixtures": list(self.activation_fixtures),
        }


def _instruction_ordered(source: str) -> bool:
    return any(marker in source for marker in _REGISTER_STATE_MARKERS)


def _short_family_key(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _candidate(
    family_key: str, members: list[MinedFamilyMember],
) -> MinedFamilyCandidate:
    descriptors = [member.descriptor for member in members]
    representative = descriptors[0]
    qualities = tuple(sorted({str(value.quality) for value in descriptors}))
    reflections = tuple(sorted({str(value.reflection) for value in descriptors}))
    observed = tuple(sorted({
        (str(value.quality), str(value.reflection)) for value in descriptors
    }))
    expected = {(quality, reflection)
                for quality in qualities for reflection in reflections}
    missing = tuple(sorted(expected - set(observed)))
    phase_keys = tuple(sorted({
        requirement.key
        for descriptor in descriptors
        for requirement in descriptor.requirements()
    }))
    assets = tuple(sorted({
        contract.asset
        for descriptor in descriptors
        for contract in resolve_phase_graph(descriptor).implementations
        if contract.asset
    }))
    density = len(observed) / max(1, len(expected))
    # Favor large complete matrices, then families with few mechanical bodies.
    behavior_count = len({member.behavior_key for member in members})
    alignment = align_canonical_bodies(
        member.canonical_body for member in members
    )
    reuse_factor = len(members) / max(1, behavior_count)
    score = len(members) * density * (1.0 + reuse_factor) \
        * (0.5 + alignment.common_token_ratio)
    return MinedFamilyCandidate(
        family_key=_short_family_key(family_key),
        skeleton=representative.skeleton(),
        inputs=representative.inputs,
        outputs=representative.outputs,
        selectors=tuple(sorted(value.selector for value in descriptors)),
        qualities=qualities,
        reflections=reflections,
        observed_policies=observed,
        missing_policies=missing,
        behavior_variant_count=behavior_count,
        common_token_ratio=alignment.common_token_ratio,
        common_block_count=alignment.common_block_count,
        variant_region_count=alignment.variant_region_count,
        required_assets=assets,
        activation_fixtures=fixture_closure(phase_keys),
        unlock_score=score,
    )


def mine_main_part_families(
    corpus: Path, *, minimum_members: int = 2,
) -> dict[str, Any]:
    """Rank uncomposed shaders by selector-independent family opportunity."""
    manifest = json.loads(
        (corpus / "manifest.json").read_text(encoding="utf-8")
    )
    snippets = corpus / "semantic" / "include" / "main_part"
    groups: dict[str, list[MinedFamilyMember]] = defaultdict(list)
    excluded: Counter[str] = Counter()

    for shader in manifest["shaders"]:
        if shader["source_name"] != "main_part" or shader["stage"] != "pixel":
            continue
        source = (snippets / f"{shader['selector']}.hlsl").read_text(
            encoding="utf-8"
        )
        if not _instruction_ordered(source):
            excluded["already_structural"] += 1
            continue
        descriptor = describe_main_part_permutation(
            shader["selector"], shader["defines"], source
        )
        if resolve_phase_graph(descriptor).missing:
            excluded["missing_phase"] += 1
            continue
        if match_validated_graph_template(shader["defines"], source):
            excluded["already_template_ready"] += 1
            continue
        ir = canonicalize_main_part_shader(descriptor, source)
        groups[canonical_family_key(ir)].append(
            MinedFamilyMember(descriptor, ir.behavior_key, ir.canonical_body)
        )

    candidates = [
        _candidate(key, members) for key, members in groups.items()
        if len(members) >= minimum_members
    ]
    candidates.sort(key=lambda value: (
        -value.unlock_score, -value.member_count,
        value.behavior_variant_count, value.family_key,
    ))
    grouped_selectors = sum(value.member_count for value in candidates)
    singleton_count = sum(len(members) == 1 for members in groups.values())
    return {
        "candidate_count": len(candidates),
        "grouped_shader_count": grouped_selectors,
        "complete_matrix_count": sum(value.matrix_complete for value in candidates),
        "singleton_family_count": singleton_count,
        "excluded": dict(sorted(excluded.items())),
        "candidates": [
            {
                **asdict(value),
                "member_count": value.member_count,
                "matrix_complete": value.matrix_complete,
                "graph_specification_draft": value.graph_specification_draft(),
            }
            for value in candidates
        ],
    }


def summarize_mined_families(
    report: dict[str, Any], *, limit: int = 25,
) -> dict[str, Any]:
    return {
        **{key: value for key, value in report.items() if key != "candidates"},
        "candidates": report["candidates"][:limit],
    }
