"""Canonical identities for mining equivalent ``main_part`` permutations."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Iterable

from .hlsl import TOKEN
from .main_part_permutation_graph import MainPartPermutationDescriptor
from .recipes.main_part_families import parse_entry_signature


_SELECTOR = re.compile(r"SM_SHADER_[0-9A-F]{16}")
_REGISTER_TEMP = re.compile(
    r"(?:[A-Za-z][A-Za-z0-9]*State|packedBitmask|integerDestination|"
    r"floatDestination|partScratch)"
)


@dataclass(frozen=True)
class CanonicalMainPartIR:
    """Stable semantic and mechanical identities for one shader."""

    selector: str
    semantic_key: str
    skeleton_key: str
    interface_key: str
    behavior_key: str
    canonical_body: str


@dataclass(frozen=True)
class CanonicalBodyAlignment:
    common_token_ratio: float
    common_block_count: int
    variant_region_count: int
    common_blocks: tuple[tuple[int, int], ...]


def _digest(value: object) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _entry_body(source: str, entry: str = "commonPS") -> str:
    marker = re.search(rf"\bvoid\s+{re.escape(entry)}\s*\(", source)
    if marker is None:
        return source
    opening = source.find("{", marker.end())
    if opening < 0:
        return source[marker.start():]
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening:index + 1]
    return source[opening:]


def canonicalize_main_part_body(source: str) -> str:
    """Normalize decompiler-only names while preserving operation order."""
    try:
        _signature, parameters = parse_entry_signature(source, "commonPS")
    except RuntimeError:
        parameters = ()
    identifiers = {
        parameter.variable: (
            f"%{'out' if parameter.output else 'in'}_"
            f"{parameter.semantic.name.lower()}{parameter.semantic.index}"
        )
        for parameter in parameters
    }
    temporary_names: dict[str, str] = {}
    output: list[str] = []
    for match in TOKEN.finditer(_entry_body(source)):
        token = match.group(0)
        if token.isspace() or token.startswith(("//", "/*")):
            continue
        token = _SELECTOR.sub("%selector", token)
        if token in identifiers:
            token = identifiers[token]
        elif _REGISTER_TEMP.fullmatch(token):
            token = temporary_names.setdefault(
                token, f"%temporary{len(temporary_names)}"
            )
        elif token.startswith(("0X", "0x")):
            token = token.lower()
        output.append(token)
    return " ".join(output)


def canonicalize_main_part_shader(
    descriptor: MainPartPermutationDescriptor,
    source: str,
) -> CanonicalMainPartIR:
    requirements = [requirement.key for requirement in descriptor.requirements()]
    skeleton = list(descriptor.skeleton())
    interface = {"inputs": descriptor.inputs, "outputs": descriptor.outputs}
    body = canonicalize_main_part_body(source)
    return CanonicalMainPartIR(
        selector=descriptor.selector,
        semantic_key=_digest(requirements),
        skeleton_key=_digest(skeleton),
        interface_key=_digest(interface),
        behavior_key=_digest(body),
        canonical_body=body,
    )


def canonical_family_key(ir: CanonicalMainPartIR) -> str:
    """Group permutations sharing semantics and an entry-point contract."""
    return _digest((ir.skeleton_key, ir.interface_key))


def align_canonical_bodies(
    bodies: Iterable[str], *, window: int = 12,
) -> CanonicalBodyAlignment:
    """Locate stable instruction regions shared by every family member.

    Positions refer to the first member's canonical token stream. Overlapping
    common shingles are merged into maximal blocks; gaps are the policy-driven
    regions a family backend must parameterize or isolate.
    """
    streams = [body.split() for body in bodies]
    if not streams or not streams[0]:
        return CanonicalBodyAlignment(0.0, 0, 0, ())
    width = max(1, min(window, *(len(stream) for stream in streams)))

    def shingles(stream: list[str]) -> set[tuple[str, ...]]:
        return {
            tuple(stream[index:index + width])
            for index in range(len(stream) - width + 1)
        }

    common = shingles(streams[0])
    for stream in streams[1:]:
        common &= shingles(stream)
    covered = [False] * len(streams[0])
    for index in range(len(streams[0]) - width + 1):
        if tuple(streams[0][index:index + width]) in common:
            covered[index:index + width] = [True] * width

    blocks: list[tuple[int, int]] = []
    start: int | None = None
    for index, value in enumerate((*covered, False)):
        if value and start is None:
            start = index
        elif not value and start is not None:
            blocks.append((start, index))
            start = None
    variant_regions = 0
    inside_variant = False
    for value in covered:
        if not value and not inside_variant:
            variant_regions += 1
            inside_variant = True
        elif value:
            inside_variant = False
    return CanonicalBodyAlignment(
        common_token_ratio=sum(covered) / len(covered),
        common_block_count=len(blocks),
        variant_region_count=variant_regions,
        common_blocks=tuple(blocks),
    )
