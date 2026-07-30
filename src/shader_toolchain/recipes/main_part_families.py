"""Declarative feature-family lifting for ``main_part`` vertex shaders.

The mechanical corpus contains one HLSL body for every complete define set.
This module deliberately matches at the smaller pipeline-family boundary:
structural features select an evaluator, transfer features only select fields,
and the recovered entry signature supplies the actual variable bindings.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from .common import replace_cbuffer_with_include


_PARAMETER = re.compile(
    r"^(?P<qualifiers>(?:(?:in|out|inout|linear|centroid|noperspective|"
    r"nointerpolation|sample)\s+)*)"
    r"(?P<type>(?:float|int|uint|bool)(?:[1-4](?:x[1-4])?)?)\s+"
    r"(?P<name>[A-Za-z_]\w*)\s*:\s*(?P<semantic>[A-Za-z_]\w*)$",
    re.IGNORECASE,
)
_SEMANTIC = re.compile(r"^(.*?)(\d+)?$")


@dataclass(frozen=True, order=True)
class SemanticKey:
    """Case-insensitive HLSL semantic identity."""

    name: str
    index: int = 0

    @classmethod
    def parse(cls, value: str) -> "SemanticKey":
        match = _SEMANTIC.fullmatch(value)
        if match is None:
            raise RuntimeError(f"invalid HLSL semantic: {value}")
        return cls(match.group(1).upper(), int(match.group(2) or 0))


@dataclass(frozen=True)
class HlslParameter:
    declaration: str
    type_name: str
    variable: str
    semantic: SemanticKey
    output: bool


@dataclass(frozen=True)
class InputBinding:
    semantic: SemanticKey | None = None
    swizzle: str = ""
    literal: str = ""


@dataclass(frozen=True)
class VertexMutation:
    """One composable post-geometry vertex phase."""

    field: str
    evaluator: str
    inputs: tuple[InputBinding, ...]
    requires_output: bool = True


@dataclass(frozen=True)
class MainPartVertexFamily:
    """One evaluator shared by a structural vertex feature family."""

    name: str
    required_defines: frozenset[str]
    optional_defines: frozenset[str]
    cbuffers: tuple[tuple[str, str], ...]
    assets: tuple[str, ...]
    result_type: str | None
    evaluator: str
    inputs: tuple[InputBinding, ...]
    outputs: tuple[tuple[SemanticKey, str], ...]
    direct_output: SemanticKey | None = None
    mutations: tuple[VertexMutation, ...] = ()
    prelude: tuple[str, ...] = ()

    @property
    def accepted_defines(self) -> frozenset[str]:
        return self.required_defines | self.optional_defines

    def matches(
        self, defines: Iterable[str], parameters: tuple[HlslParameter, ...]
    ) -> bool:
        values = frozenset(defines)
        if not self.required_defines <= values <= self.accepted_defines:
            return False
        inputs = {parameter.semantic for parameter in parameters if not parameter.output}
        outputs = {parameter.semantic for parameter in parameters if parameter.output}
        required_inputs = {
            binding.semantic for binding in self.inputs
            if binding.semantic is not None
        }
        if not required_inputs <= inputs:
            return False
        supported_outputs = {semantic for semantic, _field in self.outputs}
        if self.direct_output is not None:
            return outputs == {self.direct_output}
        mutated_fields = {
            mutation.field
            for mutation in self.mutations
            if mutation.requires_output
        }
        if mutated_fields:
            observed_mutated_fields = {
                field
                for semantic, field in self.outputs
                if semantic in outputs
            }
            if not mutated_fields <= observed_mutated_fields:
                return False
        return bool(outputs) and outputs <= supported_outputs


TRANSFER_SURFACE = frozenset(
    {
        "TRANSFER_COLOR",
        "TRANSFER_NORMAL",
        "TRANSFER_SCREEN_UV",
        "TRANSFER_TANGENTS",
        "TRANSFER_UV0",
        "TRANSFER_UV1",
        "TRANSFER_OCCLUSION",
        "TRANSFER_VIEW_POSITION",
        "TRANSFER_WORLD_POSITION",
        "TRANSFER_FOG_COLOR",
        "TRANSFER_CUTOFF",
        "TRANSFER_LASER_OFFSET",
        "TRANSFER_LASER_MASK",
    }
)

SURFACE_OUTPUTS = (
    (SemanticKey("SV_POSITION"), "clipPosition"),
    (SemanticKey("VIEW_POSITION"), "viewPosition"),
    (SemanticKey("UV", 0), "uv0"),
    (SemanticKey("UV", 1), "uv1"),
    (SemanticKey("OCCLUSION"), "occlusion"),
    (SemanticKey("NORMAL"), "normalView"),
    (SemanticKey("TANGENT"), "tangentView"),
    (SemanticKey("BITANGENT"), "bitangentView"),
    (SemanticKey("VERTEXCOLOR"), "color"),
    (SemanticKey("ACCSENTCOLOR"), "accentColor"),
    (SemanticKey("OBJECT_TANGENT"), "objectTangent"),
    (SemanticKey("SCREEN_UV"), "screenUv"),
    (SemanticKey("WORLD_POSITION"), "worldPosition"),
    (SemanticKey("FOG_COLOR"), "fogColor"),
    (SemanticKey("PLANE_VIEW_POS"), "planeViewPosition"),
    (SemanticKey("CUTOFF"), "cutoff"),
    # A leading ``=`` denotes an output expression rather than a result-struct
    # field.  Policy-only permutations use this for channels that are fixed by
    # the vertex feature set (for example the non-displaced laser offset).
    (SemanticKey("LASER_OFFSET"), "=0.0"),
    (SemanticKey("LASER_MASK"), "=$COLOR0.x"),
)

EXPLICIT_SURFACE_EXTENSIONS = frozenset({"ALPHA", "PARALLAX_PLANE"})

EXPLICIT_SURFACE_OUTPUT_KEYS = {
    SemanticKey("SV_POSITION"),
    SemanticKey("VIEW_POSITION"),
    SemanticKey("WORLD_POSITION"),
    SemanticKey("UV", 0),
    SemanticKey("UV", 1),
    SemanticKey("OCCLUSION"),
    SemanticKey("NORMAL"),
    SemanticKey("TANGENT"),
    SemanticKey("BITANGENT"),
    SemanticKey("VERTEXCOLOR"),
    SemanticKey("ACCSENTCOLOR"),
    SemanticKey("OBJECT_TANGENT"),
    SemanticKey("SCREEN_UV"),
    SemanticKey("FOG_COLOR"),
    SemanticKey("PLANE_VIEW_POS"),
    SemanticKey("CUTOFF"),
    SemanticKey("LASER_OFFSET"),
    SemanticKey("LASER_MASK"),
}


def _surface_outputs(*, uv1: bool = True) -> tuple[tuple[SemanticKey, str], ...]:
    accepted = set(EXPLICIT_SURFACE_OUTPUT_KEYS)
    if not uv1:
        accepted.remove(SemanticKey("UV", 1))
    return tuple(item for item in SURFACE_OUTPUTS if item[0] in accepted)


PACKED_SURFACE_OUTPUT_KEYS = {
    SemanticKey("SV_POSITION"),
    SemanticKey("VIEW_POSITION"),
    SemanticKey("WORLD_POSITION"),
    SemanticKey("UV", 0),
    SemanticKey("OCCLUSION"),
    SemanticKey("NORMAL"),
    SemanticKey("TANGENT"),
    SemanticKey("BITANGENT"),
    SemanticKey("VERTEXCOLOR"),
    SemanticKey("ACCSENTCOLOR"),
    SemanticKey("OBJECT_TANGENT"),
    SemanticKey("SCREEN_UV"),
    SemanticKey("FOG_COLOR"),
    SemanticKey("PLANE_VIEW_POS"),
    SemanticKey("CUTOFF"),
    SemanticKey("LASER_OFFSET"),
    SemanticKey("LASER_MASK"),
}

def _packed_surface_outputs(
    *, uv1: bool = False
) -> tuple[tuple[SemanticKey, str], ...]:
    accepted = set(PACKED_SURFACE_OUTPUT_KEYS)
    if uv1:
        accepted.add(SemanticKey("UV", 1))
    return tuple(item for item in SURFACE_OUTPUTS if item[0] in accepted)


PACKED_SURFACE_OUTPUTS = _packed_surface_outputs()


def _packed_multi_morph_family(
    pose_count: int, *, uv1: bool
) -> MainPartVertexFamily:
    pose_defines = {f"VS_POSE_{index}_ANIM" for index in range(pose_count)}
    inputs = [
        InputBinding(SemanticKey("POSITION", 0)),
        InputBinding(SemanticKey("TEXCOORD", 0), "xy"),
        (
            InputBinding(SemanticKey("TEXCOORD", 1))
            if uv1 else InputBinding(literal="float2(0.0, 0.0)")
        ),
        InputBinding(SemanticKey("NORMAL", 0)),
        InputBinding(SemanticKey("TANGENT", 0)),
    ]
    for index in range(1, pose_count + 1):
        inputs.extend(
            (
                InputBinding(SemanticKey("POSITION", index)),
                InputBinding(SemanticKey("NORMAL", index)),
            )
        )
    inputs.extend(
        (
            InputBinding(SemanticKey("LTWPACKED", 0)),
            InputBinding(SemanticKey("INSTANCE_DATA", 0)),
        )
    )
    pose_name = "dual" if pose_count == 2 else "triple"
    evaluator_pose = "Dual" if pose_count == 2 else "Triple"
    return MainPartVertexFamily(
        name=f"packed_ltw_{pose_name}_morph_tangent"
        + ("_uv1" if uv1 else "")
        + "_surface",
        required_defines=frozenset(
            {"VERTEX_SHADER", "VS_INPUT_TANGENTS", *pose_defines}
            | ({"VS_INPUT_UV1"} if uv1 else set())
        ),
        optional_defines=(
            TRANSFER_SURFACE
            if uv1 else TRANSFER_SURFACE - {"TRANSFER_UV1"}
        ) | frozenset({"ALPHA", "PARALLAX_PLANE"}),
        cbuffers=(
            ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
            ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
            ("CB_TRANSFORMS", "main_part_transforms_abi.hlsl"),
        ),
        assets=("main_part_packed_multi_morph_vertex.hlsl",),
        result_type="MainPartPackedTransformSurfaceVertex",
        evaluator=f"EvaluateMainPartPacked{evaluator_pose}MorphSurfaceVertex",
        inputs=tuple(inputs),
        outputs=_packed_surface_outputs(uv1=uv1),
    )


def _packed_normal_family(
    pose_count: int, *, uv1: bool
) -> MainPartVertexFamily:
    """Packed transform/morph family when no tangent frame is transferred.

    The tangent-capable evaluators remain the canonical geometry backend.  A
    constant tangent is sufficient here because none of the accepted output
    signatures can observe tangent or bitangent fields; HLSL dead-code
    elimination removes that branch of the evaluator.
    """

    pose_defines = {f"VS_POSE_{index}_ANIM" for index in range(pose_count)}
    inputs = [
        InputBinding(SemanticKey("POSITION", 0)),
        InputBinding(SemanticKey("TEXCOORD", 0), "xy"),
        (
            InputBinding(SemanticKey("TEXCOORD", 1))
            if uv1 else InputBinding(literal="float2(0.0, 0.0)")
        ),
    ]
    if pose_count <= 1:
        inputs.extend(
            (
                InputBinding(literal="0.0"),
                InputBinding(SemanticKey("NORMAL", 0)),
                InputBinding(literal="float4(0.0, 0.0, 0.0, 0.0)"),
                (
                    InputBinding(SemanticKey("POSITION", 1))
                    if pose_count else InputBinding(SemanticKey("POSITION", 0))
                ),
                (
                    InputBinding(SemanticKey("NORMAL", 1))
                    if pose_count else InputBinding(SemanticKey("NORMAL", 0))
                ),
            )
        )
        evaluator = "EvaluateMainPartPackedTransformSurfaceVertex"
        assets = ("main_part_packed_transform_vertex.hlsl",)
    else:
        inputs.extend(
            (
                InputBinding(SemanticKey("NORMAL", 0)),
                InputBinding(literal="float4(0.0, 0.0, 0.0, 0.0)"),
            )
        )
        for index in range(1, pose_count + 1):
            inputs.extend(
                (
                    InputBinding(SemanticKey("POSITION", index)),
                    InputBinding(SemanticKey("NORMAL", index)),
                )
            )
        evaluator_pose = "Dual" if pose_count == 2 else "Triple"
        evaluator = f"EvaluateMainPartPacked{evaluator_pose}MorphSurfaceVertex"
        assets = ("main_part_packed_multi_morph_vertex.hlsl",)
    inputs.extend(
        (
            InputBinding(SemanticKey("LTWPACKED", 0)),
            InputBinding(SemanticKey("INSTANCE_DATA", 0)),
        )
    )
    normal_outputs = tuple(
        item
        for item in _packed_surface_outputs(uv1=uv1)
        if item[0] not in {SemanticKey("TANGENT"), SemanticKey("BITANGENT")}
    )
    return MainPartVertexFamily(
        name=f"packed_ltw_pose{pose_count}_normal"
        + ("_uv1" if uv1 else "")
        + "_surface",
        required_defines=frozenset(
            {"VERTEX_SHADER", *pose_defines}
            | ({"VS_INPUT_UV1"} if uv1 else set())
        ),
        optional_defines=(
            TRANSFER_SURFACE - {"TRANSFER_TANGENTS"}
            if uv1 else
            TRANSFER_SURFACE - {"TRANSFER_TANGENTS", "TRANSFER_UV1"}
        ) | frozenset({"ALPHA"}),
        cbuffers=(
            ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
            ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
            ("CB_TRANSFORMS", "main_part_transforms_abi.hlsl"),
        ),
        assets=assets,
        result_type="MainPartPackedTransformSurfaceVertex",
        evaluator=evaluator,
        inputs=tuple(inputs),
        outputs=normal_outputs,
    )


def _explicit_normal_morph_family(
    pose_count: int, *, uv1: bool
) -> MainPartVertexFamily:
    """Explicit-LTW morph family whose signature omits tangent outputs."""

    if pose_count == 0 and not uv1:
        raise ValueError("the rigid normal family has a dedicated evaluator")
    if pose_count == 3 and uv1:
        raise ValueError("the triple-morph evaluator does not carry UV1")

    pose_defines = {f"VS_POSE_{index}_ANIM" for index in range(pose_count)}
    inputs = [
        InputBinding(SemanticKey("POSITION", 0)),
        InputBinding(SemanticKey("TEXCOORD", 0), "xy"),
    ]
    if pose_count <= 1:
        inputs.extend(
            (
                (
                    InputBinding(SemanticKey("TEXCOORD", 1))
                    if uv1 else InputBinding(literal="float2(0.0, 0.0)")
                ),
                InputBinding(SemanticKey("NORMAL", 0)),
                InputBinding(literal="float4(0.0, 0.0, 0.0, 0.0)"),
                (
                    InputBinding(SemanticKey("POSITION", 1))
                    if pose_count else InputBinding(SemanticKey("POSITION", 0))
                ),
                (
                    InputBinding(SemanticKey("NORMAL", 1))
                    if pose_count else InputBinding(SemanticKey("NORMAL", 0))
                ),
            )
        )
        evaluator = "EvaluateMainPartMorphVertex"
        result_type = "MainPartMorphVertex"
        assets = ("main_part_morph_vertex.hlsl",)
    elif pose_count == 2:
        inputs.extend(
            (
                (
                    InputBinding(SemanticKey("TEXCOORD", 1))
                    if uv1 else InputBinding(literal="float2(0.0, 0.0)")
                ),
                InputBinding(SemanticKey("NORMAL", 0)),
                InputBinding(literal="float4(0.0, 0.0, 0.0, 0.0)"),
                InputBinding(SemanticKey("POSITION", 1)),
                InputBinding(SemanticKey("NORMAL", 1)),
                InputBinding(SemanticKey("POSITION", 2)),
                InputBinding(SemanticKey("NORMAL", 2)),
            )
        )
        evaluator = "EvaluateMainPartDualMorphVertex"
        result_type = "MainPartDualMorphVertex"
        assets = (
            "main_part_morph_vertex.hlsl",
            "main_part_dual_morph_vertex.hlsl",
        )
    else:
        inputs.extend(
            (
                InputBinding(literal="0.0"),
                InputBinding(SemanticKey("NORMAL", 0)),
                InputBinding(literal="float4(0.0, 0.0, 0.0, 0.0)"),
                InputBinding(SemanticKey("POSITION", 1)),
                InputBinding(SemanticKey("NORMAL", 1)),
                InputBinding(SemanticKey("POSITION", 2)),
                InputBinding(SemanticKey("NORMAL", 2)),
                InputBinding(SemanticKey("POSITION", 3)),
                InputBinding(SemanticKey("NORMAL", 3)),
            )
        )
        evaluator = "EvaluateMainPartTripleMorphSurfaceVertex"
        result_type = "MainPartTripleMorphSurfaceVertex"
        assets = (
            "main_part_morph_vertex.hlsl",
            "main_part_triple_morph_vertex.hlsl",
        )
    inputs.extend(
        (
            InputBinding(SemanticKey("LTW", 0)),
            InputBinding(SemanticKey("LTW", 1)),
            InputBinding(SemanticKey("LTW", 2)),
            InputBinding(SemanticKey("INSTANCE_DATA", 0)),
        )
    )
    outputs = tuple(
        item
        for item in _surface_outputs(uv1=uv1)
        if item[0] not in {SemanticKey("TANGENT"), SemanticKey("BITANGENT")}
    )
    return MainPartVertexFamily(
        name=f"explicit_ltw_pose{pose_count}_normal"
        + ("_uv1" if uv1 else "")
        + "_surface",
        required_defines=frozenset(
            {"VERTEX_SHADER", "VS_FULL_TRANSFORM", *pose_defines}
            | ({"VS_INPUT_UV1"} if uv1 else set())
        ),
        optional_defines=(
            TRANSFER_SURFACE - {"TRANSFER_TANGENTS"}
            if uv1 else
            TRANSFER_SURFACE - {"TRANSFER_TANGENTS", "TRANSFER_UV1"}
        ) | EXPLICIT_SURFACE_EXTENSIONS,
        cbuffers=(
            ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
            ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ),
        assets=assets,
        result_type=result_type,
        evaluator=evaluator,
        inputs=tuple(inputs),
        outputs=outputs,
    )


def _skeletal_family(
    *, tangents: bool, uv1: bool, skip_optimization: bool
) -> MainPartVertexFamily:
    """Four-weight skinning followed by the common packed instance frame."""

    required = {"VERTEX_SHADER", "VS_SKEL_ANIM"}
    if tangents:
        required.add("VS_INPUT_TANGENTS")
    if uv1:
        required.add("VS_INPUT_UV1")
    if skip_optimization:
        required.add("VS_SKIP_OPTIMIZATION")
    optional = set(TRANSFER_SURFACE)
    if not tangents:
        optional.remove("TRANSFER_TANGENTS")
    if not uv1:
        optional.remove("TRANSFER_UV1")
    outputs = _packed_surface_outputs(uv1=uv1)
    if not tangents:
        outputs = tuple(
            item for item in outputs
            if item[0] not in {
                SemanticKey("TANGENT"), SemanticKey("BITANGENT")
            }
        )
    return MainPartVertexFamily(
        name="skeletal_4weight"
        + ("_tangent" if tangents else "_normal")
        + ("_uv1" if uv1 else "")
        + ("_skip_optimization" if skip_optimization else "")
        + "_surface",
        required_defines=frozenset(required),
        optional_defines=frozenset(optional) | {"ALPHA"},
        cbuffers=(
            ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
            ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
            ("CB_BONES", "main_part_bones_abi.hlsl"),
            ("CB_TRANSFORMS", "main_part_transforms_abi.hlsl"),
        ),
        assets=("main_part_skeletal_vertex.hlsl",),
        result_type="MainPartPackedTransformSurfaceVertex",
        evaluator="EvaluateMainPartSkeletalSurfaceVertex",
        inputs=(
            InputBinding(SemanticKey("POSITION", 0)),
            InputBinding(SemanticKey("TEXCOORD", 0), "xy"),
            (
                InputBinding(SemanticKey("TEXCOORD", 1))
                if uv1 else InputBinding(literal="float2(0.0, 0.0)")
            ),
            InputBinding(literal="0.0"),
            InputBinding(SemanticKey("NORMAL", 0)),
            (
                InputBinding(SemanticKey("TANGENT", 0))
                if tangents else InputBinding(literal="float4(0.0, 0.0, 0.0, 0.0)")
            ),
            InputBinding(SemanticKey("INDICES", 0)),
            InputBinding(SemanticKey("WEIGHTS", 0)),
            InputBinding(SemanticKey("LTWPACKED", 0)),
            InputBinding(SemanticKey("INSTANCE_DATA", 0)),
        ),
        outputs=outputs,
    )


MAIN_PART_VERTEX_FAMILIES = (
    *(
        _skeletal_family(
            tangents=tangents,
            uv1=uv1,
            skip_optimization=skip_optimization,
        )
        for tangents in (False, True)
        for uv1 in (False, True)
        for skip_optimization in (False, True)
    ),
    *(
        _packed_normal_family(pose_count, uv1=uv1)
        for pose_count in range(4)
        for uv1 in (False, True)
    ),
    *(
        _explicit_normal_morph_family(pose_count, uv1=uv1)
        for pose_count, uv1 in (
            (0, True),
            (1, False),
            (1, True),
            (2, False),
            (2, True),
            (3, False),
        )
    ),
    *(
        _packed_multi_morph_family(pose_count, uv1=uv1)
        for pose_count in (2, 3)
        for uv1 in (False, True)
    ),
    MainPartVertexFamily(
        name="packed_ltw_rigid_tangent_surface",
        required_defines=frozenset(
            {"VERTEX_SHADER", "VS_INPUT_TANGENTS"}
        ),
        optional_defines=(TRANSFER_SURFACE - {"TRANSFER_UV1"})
        | frozenset({"ALPHA"}),
        cbuffers=(
            ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
            ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
            ("CB_TRANSFORMS", "main_part_transforms_abi.hlsl"),
        ),
        assets=("main_part_packed_transform_vertex.hlsl",),
        result_type="MainPartPackedTransformSurfaceVertex",
        evaluator="EvaluateMainPartPackedTransformSurfaceVertex",
        inputs=(
            InputBinding(SemanticKey("POSITION", 0)),
            InputBinding(SemanticKey("TEXCOORD", 0), "xy"),
            InputBinding(literal="float2(0.0, 0.0)"),
            InputBinding(literal="0.0"),
            InputBinding(SemanticKey("NORMAL", 0)),
            InputBinding(SemanticKey("TANGENT", 0)),
            InputBinding(SemanticKey("POSITION", 0)),
            InputBinding(SemanticKey("NORMAL", 0)),
            InputBinding(SemanticKey("LTWPACKED", 0)),
            InputBinding(SemanticKey("INSTANCE_DATA", 0)),
        ),
        outputs=PACKED_SURFACE_OUTPUTS,
    ),
    MainPartVertexFamily(
        name="packed_ltw_pose1_tangent_surface",
        required_defines=frozenset(
            {"VERTEX_SHADER", "VS_INPUT_TANGENTS", "VS_POSE_0_ANIM"}
        ),
        optional_defines=(TRANSFER_SURFACE - {"TRANSFER_UV1"})
        | frozenset({"ALPHA"}),
        cbuffers=(
            ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
            ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
            ("CB_TRANSFORMS", "main_part_transforms_abi.hlsl"),
        ),
        assets=("main_part_packed_transform_vertex.hlsl",),
        result_type="MainPartPackedTransformSurfaceVertex",
        evaluator="EvaluateMainPartPackedTransformSurfaceVertex",
        inputs=(
            InputBinding(SemanticKey("POSITION", 0)),
            InputBinding(SemanticKey("TEXCOORD", 0), "xy"),
            InputBinding(literal="float2(0.0, 0.0)"),
            InputBinding(literal="0.0"),
            InputBinding(SemanticKey("NORMAL", 0)),
            InputBinding(SemanticKey("TANGENT", 0)),
            InputBinding(SemanticKey("POSITION", 1)),
            InputBinding(SemanticKey("NORMAL", 1)),
            InputBinding(SemanticKey("LTWPACKED", 0)),
            InputBinding(SemanticKey("INSTANCE_DATA", 0)),
        ),
        outputs=PACKED_SURFACE_OUTPUTS,
    ),
    MainPartVertexFamily(
        name="packed_ltw_rigid_tangent_uv1_surface",
        required_defines=frozenset(
            {"VERTEX_SHADER", "VS_INPUT_TANGENTS", "VS_INPUT_UV1"}
        ),
        optional_defines=TRANSFER_SURFACE | frozenset({"ALPHA"}),
        cbuffers=(
            ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
            ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
            ("CB_TRANSFORMS", "main_part_transforms_abi.hlsl"),
        ),
        assets=("main_part_packed_transform_vertex.hlsl",),
        result_type="MainPartPackedTransformSurfaceVertex",
        evaluator="EvaluateMainPartPackedTransformSurfaceVertex",
        inputs=(
            InputBinding(SemanticKey("POSITION", 0)),
            InputBinding(SemanticKey("TEXCOORD", 0), "xy"),
            InputBinding(SemanticKey("TEXCOORD", 1)),
            InputBinding(literal="0.0"),
            InputBinding(SemanticKey("NORMAL", 0)),
            InputBinding(SemanticKey("TANGENT", 0)),
            InputBinding(SemanticKey("POSITION", 0)),
            InputBinding(SemanticKey("NORMAL", 0)),
            InputBinding(SemanticKey("LTWPACKED", 0)),
            InputBinding(SemanticKey("INSTANCE_DATA", 0)),
        ),
        outputs=_packed_surface_outputs(uv1=True),
    ),
    MainPartVertexFamily(
        name="packed_ltw_pose1_tangent_uv1_surface",
        required_defines=frozenset(
            {
                "VERTEX_SHADER",
                "VS_INPUT_TANGENTS",
                "VS_INPUT_UV1",
                "VS_POSE_0_ANIM",
            }
        ),
        optional_defines=TRANSFER_SURFACE | frozenset({"ALPHA"}),
        cbuffers=(
            ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
            ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
            ("CB_TRANSFORMS", "main_part_transforms_abi.hlsl"),
        ),
        assets=("main_part_packed_transform_vertex.hlsl",),
        result_type="MainPartPackedTransformSurfaceVertex",
        evaluator="EvaluateMainPartPackedTransformSurfaceVertex",
        inputs=(
            InputBinding(SemanticKey("POSITION", 0)),
            InputBinding(SemanticKey("TEXCOORD", 0), "xy"),
            InputBinding(SemanticKey("TEXCOORD", 1)),
            InputBinding(literal="0.0"),
            InputBinding(SemanticKey("NORMAL", 0)),
            InputBinding(SemanticKey("TANGENT", 0)),
            InputBinding(SemanticKey("POSITION", 1)),
            InputBinding(SemanticKey("NORMAL", 1)),
            InputBinding(SemanticKey("LTWPACKED", 0)),
            InputBinding(SemanticKey("INSTANCE_DATA", 0)),
        ),
        outputs=_packed_surface_outputs(uv1=True),
    ),
    MainPartVertexFamily(
        name="explicit_ltw_rigid_normal_surface",
        required_defines=frozenset({"VERTEX_SHADER", "VS_FULL_TRANSFORM"}),
        optional_defines=(
            TRANSFER_SURFACE
            - {"TRANSFER_TANGENTS", "TRANSFER_UV1"}
        ) | EXPLICIT_SURFACE_EXTENSIONS,
        cbuffers=(
            ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
            ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ),
        assets=(
            "main_part_morph_vertex.hlsl",
            "main_part_rigid_normal_vertex.hlsl",
        ),
        result_type="MainPartRigidNormalVertex",
        evaluator="EvaluateMainPartRigidNormalVertex",
        inputs=(
            InputBinding(SemanticKey("POSITION", 0)),
            InputBinding(SemanticKey("TEXCOORD", 0), "xy"),
            InputBinding(SemanticKey("NORMAL", 0)),
            InputBinding(SemanticKey("LTW", 0)),
            InputBinding(SemanticKey("LTW", 1)),
            InputBinding(SemanticKey("LTW", 2)),
            InputBinding(SemanticKey("INSTANCE_DATA", 0)),
        ),
        outputs=tuple(
            item
            for item in _surface_outputs(uv1=False)
            if item[0]
            not in {SemanticKey("TANGENT"), SemanticKey("BITANGENT")}
        ),
    ),
    MainPartVertexFamily(
        name="explicit_ltw_pose1_surface",
        required_defines=frozenset(
            {
                "VERTEX_SHADER",
                "VS_FULL_TRANSFORM",
                "VS_INPUT_TANGENTS",
                "VS_INPUT_UV1",
                "VS_POSE_0_ANIM",
            }
        ),
        optional_defines=TRANSFER_SURFACE | EXPLICIT_SURFACE_EXTENSIONS,
        cbuffers=(
            ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
            ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ),
        assets=("main_part_vertex_fog.hlsl", "main_part_morph_vertex.hlsl"),
        result_type="MainPartMorphVertex",
        evaluator="EvaluateMainPartMorphVertex",
        inputs=(
            InputBinding(SemanticKey("POSITION", 0)),
            InputBinding(SemanticKey("TEXCOORD", 0), "xy"),
            InputBinding(SemanticKey("TEXCOORD", 1)),
            InputBinding(SemanticKey("NORMAL", 0)),
            InputBinding(SemanticKey("TANGENT", 0)),
            InputBinding(SemanticKey("POSITION", 1)),
            InputBinding(SemanticKey("NORMAL", 1)),
            InputBinding(SemanticKey("LTW", 0)),
            InputBinding(SemanticKey("LTW", 1)),
            InputBinding(SemanticKey("LTW", 2)),
            InputBinding(SemanticKey("INSTANCE_DATA", 0)),
        ),
        outputs=_surface_outputs(),
    ),
    MainPartVertexFamily(
        name="explicit_ltw_pose1_surface_no_uv1",
        required_defines=frozenset(
            {
                "VERTEX_SHADER",
                "VS_FULL_TRANSFORM",
                "VS_INPUT_TANGENTS",
                "VS_POSE_0_ANIM",
            }
        ),
        optional_defines=(TRANSFER_SURFACE - {"TRANSFER_UV1"})
        | EXPLICIT_SURFACE_EXTENSIONS,
        cbuffers=(
            ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
            ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ),
        assets=("main_part_vertex_fog.hlsl", "main_part_morph_vertex.hlsl"),
        result_type="MainPartMorphVertex",
        evaluator="EvaluateMainPartMorphVertex",
        inputs=(
            InputBinding(SemanticKey("POSITION", 0)),
            InputBinding(SemanticKey("TEXCOORD", 0), "xy"),
            InputBinding(literal="float2(0.0, 0.0)"),
            InputBinding(SemanticKey("NORMAL", 0)),
            InputBinding(SemanticKey("TANGENT", 0)),
            InputBinding(SemanticKey("POSITION", 1)),
            InputBinding(SemanticKey("NORMAL", 1)),
            InputBinding(SemanticKey("LTW", 0)),
            InputBinding(SemanticKey("LTW", 1)),
            InputBinding(SemanticKey("LTW", 2)),
            InputBinding(SemanticKey("INSTANCE_DATA", 0)),
        ),
        outputs=_surface_outputs(uv1=False),
    ),
    MainPartVertexFamily(
        name="explicit_ltw_pose2_surface",
        required_defines=frozenset(
            {
                "VERTEX_SHADER",
                "VS_FULL_TRANSFORM",
                "VS_INPUT_TANGENTS",
                "VS_POSE_0_ANIM",
                "VS_POSE_1_ANIM",
            }
        ),
        optional_defines=(TRANSFER_SURFACE - {"TRANSFER_UV1"})
        | EXPLICIT_SURFACE_EXTENSIONS,
        cbuffers=(
            ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
            ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ),
        assets=(
            "main_part_vertex_fog.hlsl",
            "main_part_morph_vertex.hlsl",
            "main_part_dual_morph_vertex.hlsl",
        ),
        result_type="MainPartDualMorphVertex",
        evaluator="EvaluateMainPartDualMorphVertex",
        inputs=(
            InputBinding(SemanticKey("POSITION", 0)),
            InputBinding(SemanticKey("TEXCOORD", 0), "xy"),
            InputBinding(literal="float2(0.0, 0.0)"),
            InputBinding(SemanticKey("NORMAL", 0)),
            InputBinding(SemanticKey("TANGENT", 0)),
            InputBinding(SemanticKey("POSITION", 1)),
            InputBinding(SemanticKey("NORMAL", 1)),
            InputBinding(SemanticKey("POSITION", 2)),
            InputBinding(SemanticKey("NORMAL", 2)),
            InputBinding(SemanticKey("LTW", 0)),
            InputBinding(SemanticKey("LTW", 1)),
            InputBinding(SemanticKey("LTW", 2)),
            InputBinding(SemanticKey("INSTANCE_DATA", 0)),
        ),
        outputs=_surface_outputs(uv1=False),
    ),
    MainPartVertexFamily(
        name="explicit_ltw_pose2_uv1_surface",
        required_defines=frozenset(
            {
                "VERTEX_SHADER",
                "VS_FULL_TRANSFORM",
                "VS_INPUT_TANGENTS",
                "VS_INPUT_UV1",
                "VS_POSE_0_ANIM",
                "VS_POSE_1_ANIM",
            }
        ),
        optional_defines=TRANSFER_SURFACE | EXPLICIT_SURFACE_EXTENSIONS,
        cbuffers=(
            ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
            ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ),
        assets=(
            "main_part_morph_vertex.hlsl",
            "main_part_dual_morph_vertex.hlsl",
        ),
        result_type="MainPartDualMorphVertex",
        evaluator="EvaluateMainPartDualMorphVertex",
        inputs=(
            InputBinding(SemanticKey("POSITION", 0)),
            InputBinding(SemanticKey("TEXCOORD", 0), "xy"),
            InputBinding(SemanticKey("TEXCOORD", 1)),
            InputBinding(SemanticKey("NORMAL", 0)),
            InputBinding(SemanticKey("TANGENT", 0)),
            InputBinding(SemanticKey("POSITION", 1)),
            InputBinding(SemanticKey("NORMAL", 1)),
            InputBinding(SemanticKey("POSITION", 2)),
            InputBinding(SemanticKey("NORMAL", 2)),
            InputBinding(SemanticKey("LTW", 0)),
            InputBinding(SemanticKey("LTW", 1)),
            InputBinding(SemanticKey("LTW", 2)),
            InputBinding(SemanticKey("INSTANCE_DATA", 0)),
        ),
        outputs=_surface_outputs(uv1=True),
    ),
    MainPartVertexFamily(
        name="explicit_ltw_pose3_surface",
        required_defines=frozenset(
            {
                "VERTEX_SHADER",
                "VS_FULL_TRANSFORM",
                "VS_INPUT_TANGENTS",
                "VS_POSE_0_ANIM",
                "VS_POSE_1_ANIM",
                "VS_POSE_2_ANIM",
            }
        ),
        optional_defines=(TRANSFER_SURFACE - {"TRANSFER_UV1"})
        | EXPLICIT_SURFACE_EXTENSIONS,
        cbuffers=(
            ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
            ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ),
        assets=(
            "main_part_morph_vertex.hlsl",
            "main_part_triple_morph_vertex.hlsl",
        ),
        result_type="MainPartTripleMorphSurfaceVertex",
        evaluator="EvaluateMainPartTripleMorphSurfaceVertex",
        inputs=(
            InputBinding(SemanticKey("POSITION", 0)),
            InputBinding(SemanticKey("TEXCOORD", 0), "xy"),
            InputBinding(literal="0.0"),
            InputBinding(SemanticKey("NORMAL", 0)),
            InputBinding(SemanticKey("TANGENT", 0)),
            InputBinding(SemanticKey("POSITION", 1)),
            InputBinding(SemanticKey("NORMAL", 1)),
            InputBinding(SemanticKey("POSITION", 2)),
            InputBinding(SemanticKey("NORMAL", 2)),
            InputBinding(SemanticKey("POSITION", 3)),
            InputBinding(SemanticKey("NORMAL", 3)),
            InputBinding(SemanticKey("LTW", 0)),
            InputBinding(SemanticKey("LTW", 1)),
            InputBinding(SemanticKey("LTW", 2)),
            InputBinding(SemanticKey("INSTANCE_DATA", 0)),
        ),
        outputs=_surface_outputs(uv1=False),
    ),
    MainPartVertexFamily(
        name="explicit_ltw_rigid_tangent_surface",
        required_defines=frozenset(
            {"VERTEX_SHADER", "VS_FULL_TRANSFORM", "VS_INPUT_TANGENTS"}
        ),
        optional_defines=(TRANSFER_SURFACE - {"TRANSFER_UV1"})
        | EXPLICIT_SURFACE_EXTENSIONS,
        cbuffers=(
            ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
            ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ),
        assets=(
            "main_part_vertex_fog.hlsl",
            "main_part_morph_vertex.hlsl",
            "main_part_rigid_vertex.hlsl",
        ),
        result_type="MainPartRigidSurfaceVertex",
        evaluator="EvaluateMainPartRigidSurfaceVertex",
        inputs=(
            InputBinding(SemanticKey("POSITION", 0)),
            InputBinding(SemanticKey("TEXCOORD", 0), "xy"),
            InputBinding(literal="float2(0.0, 0.0)"),
            InputBinding(SemanticKey("NORMAL", 0)),
            InputBinding(SemanticKey("TANGENT", 0)),
            InputBinding(SemanticKey("LTW", 0)),
            InputBinding(SemanticKey("LTW", 1)),
            InputBinding(SemanticKey("LTW", 2)),
            InputBinding(SemanticKey("INSTANCE_DATA", 0)),
        ),
        outputs=_surface_outputs(uv1=False),
    ),
    MainPartVertexFamily(
        name="explicit_ltw_rigid_tangent_uv1_surface",
        required_defines=frozenset(
            {
                "VERTEX_SHADER",
                "VS_FULL_TRANSFORM",
                "VS_INPUT_TANGENTS",
                "VS_INPUT_UV1",
            }
        ),
        optional_defines=TRANSFER_SURFACE | EXPLICIT_SURFACE_EXTENSIONS,
        cbuffers=(
            ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
            ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ),
        assets=(
            "main_part_vertex_fog.hlsl",
            "main_part_morph_vertex.hlsl",
            "main_part_rigid_vertex.hlsl",
        ),
        result_type="MainPartRigidSurfaceVertex",
        evaluator="EvaluateMainPartRigidSurfaceVertex",
        inputs=(
            InputBinding(SemanticKey("POSITION", 0)),
            InputBinding(SemanticKey("TEXCOORD", 0), "xy"),
            InputBinding(SemanticKey("TEXCOORD", 1)),
            InputBinding(SemanticKey("NORMAL", 0)),
            InputBinding(SemanticKey("TANGENT", 0)),
            InputBinding(SemanticKey("LTW", 0)),
            InputBinding(SemanticKey("LTW", 1)),
            InputBinding(SemanticKey("LTW", 2)),
            InputBinding(SemanticKey("INSTANCE_DATA", 0)),
        ),
        outputs=_surface_outputs(),
    ),
    MainPartVertexFamily(
        name="explicit_ltw_pose1_clip",
        required_defines=frozenset(
            {"VERTEX_SHADER", "VS_FULL_TRANSFORM", "VS_POSE_0_ANIM"}
        ),
        optional_defines=frozenset(),
        cbuffers=(
            ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
            ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
        ),
        assets=("main_part_morph_clip_vertex.hlsl",),
        result_type=None,
        evaluator="EvaluateMainPartMorphClipVertex",
        inputs=(
            InputBinding(SemanticKey("POSITION", 0)),
            InputBinding(SemanticKey("POSITION", 1)),
            InputBinding(SemanticKey("LTW", 0)),
            InputBinding(SemanticKey("LTW", 1)),
            InputBinding(SemanticKey("LTW", 2)),
            InputBinding(SemanticKey("INSTANCE_DATA", 0)),
        ),
        outputs=((SemanticKey("SV_POSITION"), ""),),
        direct_output=SemanticKey("SV_POSITION"),
    ),
    MainPartVertexFamily(
        name="explicit_ltw_rigid_uv_step_surface",
        required_defines=frozenset(
            {"VERTEX_SHADER", "VS_FULL_TRANSFORM", "VS_UV0_STEP"}
        ),
        optional_defines=frozenset(
            {
                "TRANSFER_COLOR",
                "TRANSFER_NORMAL",
                "TRANSFER_SCREEN_UV",
                "TRANSFER_UV0",
                "TRANSFER_VIEW_POSITION",
            }
        ),
        cbuffers=(
            ("CB_PROJECTION", "main_part_projection_abi.hlsl"),
            ("CB_PERFRAME", "main_part_perframe_abi.hlsl"),
            ("CB_UV_STEP", "main_part_uv_step_abi.hlsl"),
        ),
        assets=(
            "main_part_vertex_fog.hlsl",
            "main_part_morph_vertex.hlsl",
            "main_part_uv_step.hlsl",
            "main_part_rigid_uv_step_vertex.hlsl",
        ),
        result_type="MainPartRigidUvStepVertex",
        evaluator="EvaluateMainPartRigidUvStepVertex",
        inputs=(
            InputBinding(SemanticKey("POSITION", 0)),
            InputBinding(SemanticKey("TEXCOORD", 0)),
            InputBinding(SemanticKey("NORMAL", 0)),
            InputBinding(SemanticKey("LTW", 0)),
            InputBinding(SemanticKey("LTW", 1)),
            InputBinding(SemanticKey("LTW", 2)),
            InputBinding(SemanticKey("INSTANCE_DATA", 0)),
        ),
        outputs=tuple(
            item
            for item in SURFACE_OUTPUTS
            if item[0]
            in {
                SemanticKey("SV_POSITION"),
                SemanticKey("VIEW_POSITION"),
                SemanticKey("UV", 0),
                SemanticKey("NORMAL"),
                SemanticKey("VERTEXCOLOR"),
                SemanticKey("ACCSENTCOLOR"),
                SemanticKey("SCREEN_UV"),
            }
        ),
    ),
)


def _with_uv_animation(
    family: MainPartVertexFamily,
) -> MainPartVertexFamily:
    """Compose atlas-frame selection onto an existing geometry family."""

    return MainPartVertexFamily(
        name=family.name.removesuffix("_surface") + "_uv_animation_surface",
        required_defines=family.required_defines | {"VS_UV_ANIM"},
        optional_defines=family.optional_defines,
        cbuffers=family.cbuffers
        + (("CB_UVFRAME", "main_part_uvframe_abi.hlsl"),),
        assets=family.assets + ("main_part_uv_animation_vertex.hlsl",),
        result_type=family.result_type,
        evaluator=family.evaluator,
        inputs=family.inputs,
        outputs=family.outputs,
        direct_output=family.direct_output,
        mutations=family.mutations + (
            VertexMutation(
                field="uv0",
                evaluator="EvaluateMainPartAnimatedUv",
                inputs=(
                    InputBinding(literal="vertex.uv0"),
                    InputBinding(SemanticKey("INSTANCE_DATA", 0), "w"),
                ),
                requires_output=False,
            ),
        ),
        prelude=family.prelude,
    )


_UV_ANIMATION_BASE_FAMILIES = tuple(
    family
    for family in MAIN_PART_VERTEX_FAMILIES
    if family.direct_output is None
    and "VS_UV_ANIM" not in family.accepted_defines
    and SemanticKey("UV", 0) in {semantic for semantic, _ in family.outputs}
    and any(
        binding.semantic == SemanticKey("INSTANCE_DATA", 0)
        for binding in family.inputs
    )
)
_UV_ANIMATION_FAMILIES = tuple(
    _with_uv_animation(family) for family in _UV_ANIMATION_BASE_FAMILIES
)
MAIN_PART_VERTEX_FAMILIES += _UV_ANIMATION_FAMILIES


def _with_uv_scroll(family: MainPartVertexFamily) -> MainPartVertexFamily:
    """Compose time-based UV scrolling onto a geometry family."""

    return MainPartVertexFamily(
        name=family.name.removesuffix("_surface") + "_uv_scroll_surface",
        required_defines=family.required_defines | {"VS_UV0_SCROLL"},
        optional_defines=family.optional_defines,
        cbuffers=family.cbuffers
        + (("CB_UV_SCROLL", "main_part_uv_scroll_abi.hlsl"),),
        assets=family.assets + ("main_part_uv_scroll_vertex.hlsl",),
        result_type=family.result_type,
        evaluator=family.evaluator,
        inputs=family.inputs,
        outputs=family.outputs,
        direct_output=family.direct_output,
        mutations=family.mutations + (
            VertexMutation(
                field="uv0",
                evaluator="EvaluateMainPartScrolledUv",
                inputs=(InputBinding(literal="vertex.uv0"),),
                requires_output=False,
            ),
        ),
        prelude=family.prelude,
    )


_UV_SCROLL_FAMILIES = tuple(
    _with_uv_scroll(family) for family in _UV_ANIMATION_BASE_FAMILIES
)
_UV_ANIMATION_SCROLL_FAMILIES = tuple(
    _with_uv_scroll(family) for family in _UV_ANIMATION_FAMILIES
)
MAIN_PART_VERTEX_FAMILIES += (
    _UV_SCROLL_FAMILIES + _UV_ANIMATION_SCROLL_FAMILIES
)


def _with_uv_step(family: MainPartVertexFamily) -> MainPartVertexFamily:
    """Compose discrete time-stepped UV motion onto a geometry family."""

    return MainPartVertexFamily(
        name=family.name.removesuffix("_surface") + "_uv_step_surface",
        required_defines=family.required_defines | {"VS_UV0_STEP"},
        optional_defines=family.optional_defines,
        cbuffers=family.cbuffers
        + (("CB_UV_STEP", "main_part_uv_step_abi.hlsl"),),
        assets=family.assets + ("main_part_uv_step.hlsl",),
        result_type=family.result_type,
        evaluator=family.evaluator,
        inputs=family.inputs,
        outputs=family.outputs,
        direct_output=family.direct_output,
        mutations=family.mutations + (
            VertexMutation(
                field="uv0",
                evaluator="EvaluateMainPartSteppedUv",
                inputs=(InputBinding(literal="vertex.uv0"),),
                requires_output=False,
            ),
        ),
        prelude=family.prelude,
    )


_UV_STEP_FAMILIES = tuple(
    _with_uv_step(family)
    for family in _UV_ANIMATION_BASE_FAMILIES
    if "VS_UV0_STEP" not in family.accepted_defines
    and family.name != "explicit_ltw_rigid_normal_surface"
)
MAIN_PART_VERTEX_FAMILIES += _UV_STEP_FAMILIES


def _with_picking(family: MainPartVertexFamily) -> MainPartVertexFamily:
    """Replace instance color with the component-lane picking identifier."""

    return MainPartVertexFamily(
        name=family.name.removesuffix("_surface") + "_picking_surface",
        required_defines=family.required_defines | {"VS_PICKING_BUFFER"},
        optional_defines=family.optional_defines,
        cbuffers=family.cbuffers
        + (("CB_PICKING", "main_part_picking_abi.hlsl"),),
        assets=family.assets + ("main_part_picking_common.hlsl",),
        result_type=family.result_type,
        evaluator=family.evaluator,
        inputs=family.inputs,
        outputs=family.outputs,
        direct_output=family.direct_output,
        mutations=family.mutations + (
            VertexMutation(
                field="color",
                evaluator="MainPartDecodePickingColor",
                inputs=(InputBinding(SemanticKey("INSTANCE_DATA", 0), "y"),),
            ),
        ),
        prelude=family.prelude,
    )


_PICKING_BASE_FAMILIES = (
    _UV_ANIMATION_BASE_FAMILIES
    + _UV_ANIMATION_FAMILIES
    + _UV_SCROLL_FAMILIES
    + _UV_ANIMATION_SCROLL_FAMILIES
    + _UV_STEP_FAMILIES
)
_PICKING_FAMILIES = tuple(
    _with_picking(family) for family in _PICKING_BASE_FAMILIES
)
MAIN_PART_VERTEX_FAMILIES += _PICKING_FAMILIES


def _with_accent_color(
    family: MainPartVertexFamily,
) -> MainPartVertexFamily:
    """Decode the packed paint-palette mask as an independent output phase."""

    return MainPartVertexFamily(
        name=family.name.removesuffix("_surface")
        + "_accent_color_surface",
        required_defines=family.required_defines | {"TRANSFER_ACCENT_COLOR"},
        optional_defines=family.optional_defines,
        cbuffers=family.cbuffers
        + (("CB_PAINT_PALETTE", "main_part_paint_palette_abi.hlsl"),),
        assets=family.assets + ("main_part_accent_color_vertex.hlsl",),
        result_type=family.result_type,
        evaluator=family.evaluator,
        inputs=family.inputs,
        outputs=family.outputs,
        direct_output=family.direct_output,
        mutations=family.mutations + (
            VertexMutation(
                field="accentColor",
                evaluator="EvaluateMainPartAccentColor",
                inputs=(InputBinding(SemanticKey("INSTANCE_DATA", 0), "y"),),
            ),
        ),
        prelude=family.prelude,
    )


_ACCENT_COLOR_BASE_FAMILIES = (
    _UV_ANIMATION_BASE_FAMILIES
    + _UV_ANIMATION_FAMILIES
    + _UV_SCROLL_FAMILIES
    + _UV_ANIMATION_SCROLL_FAMILIES
    + _UV_STEP_FAMILIES
    + _PICKING_FAMILIES
)
_ACCENT_COLOR_FAMILIES = tuple(
    _with_accent_color(family)
    for family in _ACCENT_COLOR_BASE_FAMILIES
    if any(
        binding.semantic == SemanticKey("INSTANCE_DATA", 0)
        for binding in family.inputs
    )
)
MAIN_PART_VERTEX_FAMILIES += _ACCENT_COLOR_FAMILIES


def _with_object_tangent(
    family: MainPartVertexFamily,
) -> MainPartVertexFamily:
    """Derive the material's object-axis tangent after geometry evaluation."""

    packed = any(
        binding.semantic == SemanticKey("LTWPACKED", 0)
        for binding in family.inputs
    )
    required = {"TRANSFER_OBJECT_TANGENT"}
    if "VS_SKEL_ANIM" in family.required_defines:
        required.add("VS_OBJECT_TANGENT")
    if packed:
        evaluator = "EvaluateMainPartPackedObjectTangent"
        helper = "main_part_packed_object_tangent_vertex.hlsl"
        inputs = (
            InputBinding(literal="vertex.normalView"),
            InputBinding(SemanticKey("LTWPACKED", 0)),
            InputBinding(SemanticKey("INSTANCE_DATA", 0)),
        )
    else:
        evaluator = "EvaluateMainPartExplicitObjectTangent"
        helper = "main_part_object_tangent_vertex.hlsl"
        inputs = (
            InputBinding(literal="vertex.normalView"),
            InputBinding(SemanticKey("LTW", 0)),
            InputBinding(SemanticKey("LTW", 1)),
            InputBinding(SemanticKey("LTW", 2)),
        )
    return MainPartVertexFamily(
        name=family.name.removesuffix("_surface")
        + "_object_tangent_surface",
        required_defines=family.required_defines | required,
        optional_defines=family.optional_defines,
        cbuffers=family.cbuffers,
        assets=family.assets + (helper,),
        result_type=family.result_type,
        evaluator=family.evaluator,
        inputs=family.inputs,
        outputs=family.outputs,
        direct_output=family.direct_output,
        mutations=family.mutations + (
            VertexMutation(
                field="objectTangent",
                evaluator=evaluator,
                inputs=inputs,
            ),
        ),
        prelude=family.prelude,
    )


_OBJECT_TANGENT_BASE_FAMILIES = (
    _UV_ANIMATION_BASE_FAMILIES
    + _UV_ANIMATION_FAMILIES
    + _UV_SCROLL_FAMILIES
    + _UV_ANIMATION_SCROLL_FAMILIES
    + _UV_STEP_FAMILIES
    + _PICKING_FAMILIES
    + _ACCENT_COLOR_FAMILIES
)
_OBJECT_TANGENT_FAMILIES = tuple(
    _with_object_tangent(family)
    for family in _OBJECT_TANGENT_BASE_FAMILIES
    if "VS_INPUT_TANGENTS" in family.required_defines
    and (
        any(
            binding.semantic == SemanticKey("LTWPACKED", 0)
            for binding in family.inputs
        )
        or all(
            any(
                binding.semantic == SemanticKey("LTW", index)
                for binding in family.inputs
            )
            for index in range(3)
        )
    )
)
MAIN_PART_VERTEX_FAMILIES += _OBJECT_TANGENT_FAMILIES


def _with_packed_parallax_plane(
    family: MainPartVertexFamily,
) -> MainPartVertexFamily:
    """Expose the packed transform origin used by parallax materials."""

    return MainPartVertexFamily(
        name=family.name.removesuffix("_surface")
        + "_parallax_plane_surface",
        required_defines=family.required_defines | {"PARALLAX_PLANE"},
        optional_defines=family.optional_defines,
        cbuffers=family.cbuffers,
        assets=family.assets,
        result_type=family.result_type,
        evaluator=family.evaluator,
        inputs=family.inputs,
        outputs=family.outputs,
        direct_output=family.direct_output,
        mutations=family.mutations,
        prelude=family.prelude,
    )


_PACKED_PARALLAX_BASE_FAMILIES = (
    _UV_ANIMATION_BASE_FAMILIES
    + _UV_ANIMATION_FAMILIES
    + _UV_SCROLL_FAMILIES
    + _UV_ANIMATION_SCROLL_FAMILIES
    + _UV_STEP_FAMILIES
    + _PICKING_FAMILIES
    + _ACCENT_COLOR_FAMILIES
    + _OBJECT_TANGENT_FAMILIES
)
_PACKED_PARALLAX_FAMILIES = tuple(
    _with_packed_parallax_plane(family)
    for family in _PACKED_PARALLAX_BASE_FAMILIES
    if "PARALLAX_PLANE" not in family.accepted_defines
    and any(
        binding.semantic == SemanticKey("LTWPACKED", 0)
        for binding in family.inputs
    )
)
MAIN_PART_VERTEX_FAMILIES += _PACKED_PARALLAX_FAMILIES


def _with_occlusion(
    family: MainPartVertexFamily, channel: str
) -> MainPartVertexFamily:
    """Select one vertex-color channel as material occlusion."""

    return MainPartVertexFamily(
        name=family.name.removesuffix("_surface")
        + f"_occlusion_{channel}_surface",
        required_defines=family.required_defines
        | {"VS_INPUT_COLOR", f"VS_OCCLUSION_CHANNEL_{channel.upper()}"},
        optional_defines=family.optional_defines,
        cbuffers=family.cbuffers,
        assets=family.assets,
        result_type=family.result_type,
        evaluator=family.evaluator,
        inputs=family.inputs,
        outputs=family.outputs,
        direct_output=family.direct_output,
        mutations=family.mutations + (
            VertexMutation(
                field="occlusion",
                evaluator="",
                inputs=(InputBinding(SemanticKey("COLOR", 0), channel),),
                requires_output=False,
            ),
        ),
        prelude=family.prelude,
    )


_OCCLUSION_BASE_FAMILIES = (
    _UV_ANIMATION_BASE_FAMILIES
    + _UV_ANIMATION_FAMILIES
    + _UV_SCROLL_FAMILIES
    + _UV_ANIMATION_SCROLL_FAMILIES
    + _UV_STEP_FAMILIES
    + _PICKING_FAMILIES
)
_OCCLUSION_FAMILIES = tuple(
    _with_occlusion(family, channel)
    for family in _OCCLUSION_BASE_FAMILIES
    for channel in "rgba"
)
MAIN_PART_VERTEX_FAMILIES += _OCCLUSION_FAMILIES


def _with_push_policy(
    family: MainPartVertexFamily, flags: frozenset[str]
) -> MainPartVertexFamily:
    """Represent push-enabled layouts whose recovered VS path is a no-op."""

    label = "_and_".join(
        flag.removeprefix("VS_").lower() for flag in sorted(flags)
    )
    return MainPartVertexFamily(
        name=family.name.removesuffix("_surface")
        + f"_{label}_surface",
        required_defines=family.required_defines
        | flags
        | {"VS_INPUT_COLOR"},
        optional_defines=family.optional_defines,
        cbuffers=family.cbuffers,
        assets=family.assets,
        result_type=family.result_type,
        evaluator=family.evaluator,
        inputs=family.inputs,
        outputs=family.outputs,
        direct_output=family.direct_output,
        mutations=family.mutations,
        prelude=family.prelude,
    )


_PUSH_BASE_FAMILIES = (
    _UV_ANIMATION_BASE_FAMILIES
    + _UV_ANIMATION_FAMILIES
    + _UV_SCROLL_FAMILIES
    + _UV_STEP_FAMILIES
    + _PICKING_FAMILIES
    + _OCCLUSION_FAMILIES
)
_PUSH_FAMILIES = tuple(
    _with_push_policy(family, flags)
    for family in _PUSH_BASE_FAMILIES
    for flags in (
        frozenset({"VS_PUSH"}),
        frozenset({"VS_PUSH_PER_VERTEX"}),
        frozenset({"VS_PUSH", "VS_PUSH_PER_VERTEX"}),
    )
)
MAIN_PART_VERTEX_FAMILIES += _PUSH_FAMILIES


def _with_wave(
    family: MainPartVertexFamily, *, scaled: bool
) -> MainPartVertexFamily:
    """Apply wave displacement before the canonical morph/transform phase."""

    rewritten_inputs = []
    for binding in family.inputs:
        semantic = binding.semantic
        if semantic is not None and semantic.name == "POSITION":
            expression = (
                "waveBase"
                if semantic.index == 0
                else f"$POSITION{semantic.index} + waveOffset"
            )
            rewritten_inputs.append(
                InputBinding(semantic=semantic, literal=expression)
            )
        else:
            rewritten_inputs.append(binding)
    packed = any(
        binding.semantic == SemanticKey("LTWPACKED", 0)
        for binding in family.inputs
    )
    if scaled and packed:
        define = "VS_WAVE"
        helper_assets = (
            "main_part_scaled_wave_by_scale_common.hlsl",
            "main_part_packed_scaled_wave_vertex.hlsl",
        )
        wave_call = (
            "MainPartApplyPackedScaledWave($POSITION0, $NORMAL0, "
            "$LTWPACKED0, $INSTANCE_DATA0)"
        )
        label = "packed_scaled_wave"
    elif scaled:
        define = "VS_WAVE"
        helper_assets = ("main_part_scaled_wave_common.hlsl",)
        wave_call = (
            "MainPartApplyScaledWave($POSITION0, $NORMAL0, "
            "$LTW0, $LTW1, $LTW2)"
        )
        label = "scaled_wave"
    else:
        define = "VS_WAVE_NO_SCALE"
        helper_assets = ("main_part_wave_common.hlsl",)
        wave_call = "MainPartApplyNoScaleWave($POSITION0, $NORMAL0)"
        label = "wave_no_scale"
    return MainPartVertexFamily(
        name=family.name.removesuffix("_surface") + f"_{label}_surface",
        required_defines=family.required_defines | {define},
        optional_defines=family.optional_defines,
        cbuffers=family.cbuffers
        + (("CB_WAVE", "main_part_wave_abi.hlsl"),),
        assets=family.assets + helper_assets,
        result_type=family.result_type,
        evaluator=family.evaluator,
        inputs=tuple(rewritten_inputs),
        outputs=family.outputs,
        direct_output=family.direct_output,
        mutations=family.mutations,
        prelude=family.prelude + (
            f"float3 waveBase = {wave_call};",
            "float3 waveOffset = waveBase - $POSITION0;",
        ),
    )


_WAVE_PHASE_BASE_FAMILIES = (
    _UV_ANIMATION_BASE_FAMILIES
    + _UV_ANIMATION_FAMILIES
    + _UV_SCROLL_FAMILIES
    + _UV_ANIMATION_SCROLL_FAMILIES
    + _PICKING_FAMILIES
    + _OCCLUSION_FAMILIES
)
_SCALED_WAVE_FAMILIES = tuple(
    _with_wave(family, scaled=True)
    for family in _WAVE_PHASE_BASE_FAMILIES
    if "VS_FULL_TRANSFORM" in family.required_defines
    or any(
        binding.semantic == SemanticKey("LTWPACKED", 0)
        for binding in family.inputs
    )
)
_NO_SCALE_WAVE_FAMILIES = tuple(
    _with_wave(family, scaled=False)
    for family in _WAVE_PHASE_BASE_FAMILIES
)
MAIN_PART_VERTEX_FAMILIES += (
    _SCALED_WAVE_FAMILIES + _NO_SCALE_WAVE_FAMILIES
)


def _with_water_policy(
    family: MainPartVertexFamily, *, legacy_wave_flag: bool
) -> MainPartVertexFamily:
    """Attach the water material policy to an existing geometry path."""

    required = {"VS_WATER"}
    if legacy_wave_flag:
        required.add("WAVE")
    return MainPartVertexFamily(
        name=family.name.removesuffix("_surface")
        + ("_water_legacy_wave_surface" if legacy_wave_flag
           else "_water_surface"),
        required_defines=family.required_defines | required,
        optional_defines=family.optional_defines,
        cbuffers=family.cbuffers,
        assets=family.assets,
        result_type=family.result_type,
        evaluator=family.evaluator,
        inputs=family.inputs,
        outputs=family.outputs,
        direct_output=family.direct_output,
        mutations=family.mutations,
        prelude=family.prelude,
    )


_WATER_POLICY_BASE_FAMILIES = (
    _UV_ANIMATION_BASE_FAMILIES
    + _PICKING_FAMILIES
    + _SCALED_WAVE_FAMILIES
)
_WATER_POLICY_FAMILIES = tuple(
    _with_water_policy(family, legacy_wave_flag=legacy_wave_flag)
    for family in _WATER_POLICY_BASE_FAMILIES
    for legacy_wave_flag in (False, True)
    if "VS_INPUT_TANGENTS" in family.required_defines
    and not (
        legacy_wave_flag and "VS_WAVE" in family.required_defines
    )
)
MAIN_PART_VERTEX_FAMILIES += _WATER_POLICY_FAMILIES


def _with_laser_color_policy(
    family: MainPartVertexFamily,
) -> MainPartVertexFamily:
    """Attach the laser material tag when it does not alter vertex geometry.

    ``VS_LASER_COLOR`` selects the downstream laser pixel path.  In vertex
    permutations without the procedural laser flags it contributes no vertex
    instructions; geometry, UV animation, picking, and transfers remain the
    responsibility of their existing phases.
    """

    return MainPartVertexFamily(
        name=family.name.removesuffix("_surface")
        + "_laser_color_surface",
        required_defines=family.required_defines | {"VS_LASER_COLOR"},
        optional_defines=family.optional_defines,
        cbuffers=family.cbuffers,
        assets=family.assets,
        result_type=family.result_type,
        evaluator=family.evaluator,
        inputs=family.inputs,
        outputs=family.outputs,
        direct_output=family.direct_output,
        mutations=family.mutations,
        prelude=family.prelude,
    )


# Laser colour is an orthogonal policy, so compose it over every geometry and
# transfer family recovered so far.  Procedural laser displacement has its own
# backend below and cannot accidentally match because its VS_LASER_* flags are
# outside these families' accepted define sets.
_LASER_COLOR_POLICY_BASE_FAMILIES = tuple(MAIN_PART_VERTEX_FAMILIES)
_LASER_COLOR_POLICY_FAMILIES = tuple(
    _with_laser_color_policy(family)
    for family in _LASER_COLOR_POLICY_BASE_FAMILIES
)
MAIN_PART_VERTEX_FAMILIES += _LASER_COLOR_POLICY_FAMILIES


def _with_static_laser_policy(
    family: MainPartVertexFamily, *, glitch: bool, laser_geometry: bool
) -> MainPartVertexFamily:
    """Compose the non-displacing laser feature bundle.

    These flags drive material/effect policy, but the recovered vertex stage
    only forwards the ordinary geometry and writes a zero LASER_OFFSET channel.
    Keeping the bundle explicit prevents it being confused with
    ``VS_LASER_DISPLACEMENT``, whose deformation backend is genuinely distinct.
    """

    flags = {
        "VS_LASER_COLOR",
        "VS_LASER_FADE",
        "VS_LASER_FLICKER",
        "VS_LASER_SLICES",
        "VS_LASER_WAVE",
    }
    if glitch:
        flags.add("VS_LASER_GLITCH")
    if laser_geometry:
        flags.add("VS_LASER")
    label = "static_laser"
    if glitch:
        label += "_glitch"
    if laser_geometry:
        label += "_geometry"
    return MainPartVertexFamily(
        name=family.name.removesuffix("_surface") + f"_{label}_surface",
        required_defines=family.required_defines | flags,
        optional_defines=family.optional_defines,
        cbuffers=family.cbuffers,
        assets=family.assets,
        result_type=family.result_type,
        evaluator=family.evaluator,
        inputs=family.inputs,
        outputs=family.outputs,
        direct_output=family.direct_output,
        mutations=family.mutations,
        prelude=family.prelude,
    )


_STATIC_LASER_POLICY_FAMILIES = tuple(
    _with_static_laser_policy(
        family, glitch=glitch, laser_geometry=laser_geometry
    )
    for family in _LASER_COLOR_POLICY_BASE_FAMILIES
    for glitch, laser_geometry in ((False, False), (True, True))
)
MAIN_PART_VERTEX_FAMILIES += _STATIC_LASER_POLICY_FAMILIES


def _with_laser_displacement(
    family: MainPartVertexFamily,
) -> MainPartVertexFamily:
    """Insert procedural laser deformation before a geometry backend.

    Morph deltas remain relative to the deformed base vertex.  This keeps pose
    decoding in the established backend while sharing the nonlinear laser
    phase across explicit and packed transforms.
    """

    flags = {
        "VS_LASER_COLOR",
        "VS_LASER_DISPLACEMENT",
        "VS_LASER_FADE",
        "VS_LASER_FLICKER",
        "VS_LASER_GLITCH",
        "VS_LASER_SLICES",
        "VS_LASER_WAVE",
    }
    pose_indices = sorted({
        binding.semantic.index
        for binding in family.inputs
        if binding.semantic is not None
        and binding.semantic.name == "POSITION"
        and binding.semantic.index > 0
    })
    weight_expressions = {
        1: "(float)($INSTANCE_DATA0.z & 65535u) / 65535.0",
        2: "(float)($INSTANCE_DATA0.z >> 16u) / 65535.0",
        3: "(float)($INSTANCE_DATA0.w & 65535u) / 65535.0",
    }
    resolved_position = "$POSITION0"
    resolved_normal = "$NORMAL0"
    for index in pose_indices:
        weight = weight_expressions[index]
        resolved_position += (
            f" + ($POSITION{index} - $POSITION0) * {weight}"
        )
        resolved_normal += (
            f" + ($NORMAL{index} - $NORMAL0) * {weight}"
        )
    rewritten_inputs = []
    for binding in family.inputs:
        semantic = binding.semantic
        if semantic is not None and semantic.name == "POSITION":
            expression = "laserDeformation.position"
            rewritten_inputs.append(
                InputBinding(semantic=semantic, literal=expression)
            )
        elif semantic is not None and semantic.name == "NORMAL":
            expression = "laserDeformation.normalEncoded"
            rewritten_inputs.append(
                InputBinding(semantic=semantic, literal=expression)
            )
        else:
            rewritten_inputs.append(binding)
    outputs = tuple(
        (
            semantic,
            "=laserDeformation.offset"
            if semantic == SemanticKey("LASER_OFFSET") else field,
        )
        for semantic, field in family.outputs
    )
    return MainPartVertexFamily(
        name=family.name.removesuffix("_surface")
        + "_laser_displacement_surface",
        required_defines=family.required_defines | flags,
        optional_defines=family.optional_defines,
        cbuffers=family.cbuffers + ((
            "CB_LASER_DISPLACEMENT",
            "main_part_laser_displacement_abi.hlsl",
        ),),
        assets=family.assets + ("main_part_laser_deformation_vertex.hlsl",),
        result_type=family.result_type,
        evaluator=family.evaluator,
        inputs=tuple(rewritten_inputs),
        outputs=outputs,
        direct_output=family.direct_output,
        mutations=family.mutations + (
            VertexMutation(
                field="color",
                evaluator="",
                inputs=(InputBinding(
                    literal="vertex.color + float4("
                    "laserDeformation.color, 0.0)"
                ),),
                requires_output=False,
            ),
        ),
        prelude=family.prelude + (
            f"float3 laserResolvedPosition = {resolved_position};",
            f"float3 laserResolvedNormal = {resolved_normal};",
            "MainPartLaserDeformation laserDeformation = "
            "EvaluateMainPartLaserDeformation("
            "laserResolvedPosition, laserResolvedNormal, $TEXCOORD0.y);",
        ),
    )


_LASER_DISPLACEMENT_FAMILIES = tuple(
    _with_laser_displacement(family)
    for family in _LASER_COLOR_POLICY_BASE_FAMILIES
)
MAIN_PART_VERTEX_FAMILIES += _LASER_DISPLACEMENT_FAMILIES


def _with_planar_laser_mask(
    family: MainPartVertexFamily,
) -> MainPartVertexFamily:
    """Compose world-planar UV generation with the red laser-mask channel."""

    return MainPartVertexFamily(
        name=family.name.removesuffix("_surface")
        + "_planar_laser_mask_surface",
        required_defines=family.required_defines | {
            "VS_INPUT_COLOR",
            "VS_LASER_COLOR",
            "VS_LASER_MASK_CHANNEL_R",
            "VS_UV0_PLANAR_WORLD_SPACE",
        },
        optional_defines=family.optional_defines,
        cbuffers=family.cbuffers + ((
            "CB_UV_PLANAR_WORLD_SPACE", "main_part_planar_world_abi.hlsl"
        ),),
        assets=family.assets + ("main_part_planar_world_vertex.hlsl",),
        result_type=family.result_type,
        evaluator=family.evaluator,
        inputs=family.inputs,
        outputs=family.outputs,
        direct_output=family.direct_output,
        mutations=family.mutations + (
            VertexMutation(
                field="uv0",
                evaluator="EvaluateMainPartPlanarWorldUv",
                inputs=(
                    InputBinding(literal="vertex.worldPosition"),
                    InputBinding(literal="vertex.normalView"),
                ),
                requires_output=False,
            ),
        ),
        prelude=family.prelude,
    )


_PLANAR_LASER_MASK_FAMILIES = tuple(
    _with_planar_laser_mask(family)
    for family in _LASER_COLOR_POLICY_BASE_FAMILIES
)
MAIN_PART_VERTEX_FAMILIES += _PLANAR_LASER_MASK_FAMILIES


def _with_adaptive_uv_scale(
    family: MainPartVertexFamily,
) -> MainPartVertexFamily:
    """Replace ordinary UV scrolling with transform-adaptive tiling."""

    packed = any(
        binding.semantic == SemanticKey("LTWPACKED", 0)
        for binding in family.inputs
    )
    mutation_inputs = [InputBinding(SemanticKey("TEXCOORD", 0), "xy")]
    if packed:
        evaluator = "EvaluateMainPartPackedAdaptiveScrolledUv"
        adaptive_asset = "main_part_packed_adaptive_uv_vertex.hlsl"
        mutation_inputs.extend((
            InputBinding(SemanticKey("LTWPACKED", 0)),
            InputBinding(SemanticKey("INSTANCE_DATA", 0)),
        ))
    else:
        evaluator = "EvaluateMainPartAdaptiveScrolledUv"
        adaptive_asset = "main_part_adaptive_uv_vertex.hlsl"
        mutation_inputs.extend((
            InputBinding(SemanticKey("LTW", 0)),
            InputBinding(SemanticKey("LTW", 1)),
            InputBinding(SemanticKey("LTW", 2)),
        ))
    return MainPartVertexFamily(
        name=family.name.removesuffix("_surface")
        + "_adaptive_scale_surface",
        required_defines=family.required_defines | {"VS_UV0_ADAPTIVE_SCALE"},
        optional_defines=family.optional_defines,
        cbuffers=family.cbuffers,
        assets=family.assets + (adaptive_asset,),
        result_type=family.result_type,
        evaluator=family.evaluator,
        inputs=family.inputs,
        outputs=family.outputs,
        direct_output=family.direct_output,
        mutations=family.mutations + (
            VertexMutation(
                field="uv0",
                evaluator=evaluator,
                inputs=tuple(mutation_inputs),
                requires_output=False,
            ),
        ),
        prelude=family.prelude,
    )


_ADAPTIVE_UV_FAMILIES = tuple(
    _with_adaptive_uv_scale(family) for family in _UV_SCROLL_FAMILIES
)
MAIN_PART_VERTEX_FAMILIES += _ADAPTIVE_UV_FAMILIES


def _with_transform_buffer(
    family: MainPartVertexFamily,
) -> MainPartVertexFamily:
    """Resolve the optional parent transform-buffer indirection."""

    packed = any(
        binding.semantic == SemanticKey("LTWPACKED", 0)
        for binding in family.inputs
    )
    rewritten_inputs = []
    for binding in family.inputs:
        if (
            not packed
            and binding.semantic is not None
            and binding.semantic.name == "LTW"
        ):
            rewritten_inputs.append(InputBinding(
                semantic=binding.semantic,
                literal=f"bufferedLtw.row{binding.semantic.index}",
            ))
        else:
            rewritten_inputs.append(binding)
    outputs = tuple(
        (
            semantic,
            "=float3(vertex.uv0, MainPartBufferedLayer($INSTANCE_DATA0))"
            if semantic == SemanticKey("UV", 0) else field,
        )
        for semantic, field in family.outputs
    )
    prelude = family.prelude
    if not packed:
        prelude += (
            "MainPartBufferedLtw bufferedLtw = ResolveMainPartBufferedLtw("
            "$LTW0, $LTW1, $LTW2, $INSTANCE_DATA0);",
        )
    return MainPartVertexFamily(
        name=family.name.removesuffix("_surface")
        + "_transform_buffer_surface",
        required_defines=family.required_defines | {
            "INDEX_IN_UV0",
            "VS_BONE_OFFSET_IS_ARRAY_INDEX",
            "VS_TRANSFORM_BUFFER",
        },
        optional_defines=family.optional_defines,
        cbuffers=(
            family.cbuffers
            +
            (("CB_TRANSFORMS", "main_part_transforms_abi.hlsl"),)
            if not any(name == "CB_TRANSFORMS" for name, _asset in family.cbuffers)
            else family.cbuffers
        ),
        assets=family.assets + ("main_part_transform_buffer_vertex.hlsl",),
        result_type=family.result_type,
        evaluator=family.evaluator,
        inputs=tuple(rewritten_inputs),
        outputs=outputs,
        direct_output=family.direct_output,
        mutations=family.mutations,
        prelude=prelude,
    )


_TRANSFORM_BUFFER_FAMILIES = tuple(
    _with_transform_buffer(family)
    for family in _LASER_COLOR_POLICY_BASE_FAMILIES
)
MAIN_PART_VERTEX_FAMILIES += _TRANSFORM_BUFFER_FAMILIES


def _with_marker_policy(
    family: MainPartVertexFamily, define: str, suffix: str
) -> MainPartVertexFamily:
    """Attach a compile-time marker that changes only the transfer contract.

    ``DISCARD_BEHIND_CENTER`` requests the already-computed plane origin and
    ``LIGHT_CONE`` selects a reduced color/screen transfer set.  Neither marker
    changes the recovered geometry evaluator, so both belong in this small
    policy layer rather than duplicated vertex backends.
    """

    return MainPartVertexFamily(
        name=family.name.removesuffix("_surface") + suffix + "_surface",
        required_defines=family.required_defines | {define},
        optional_defines=family.optional_defines,
        cbuffers=family.cbuffers,
        assets=family.assets,
        result_type=family.result_type,
        evaluator=family.evaluator,
        inputs=family.inputs,
        outputs=family.outputs,
        direct_output=family.direct_output,
        mutations=family.mutations,
        prelude=family.prelude,
    )


_DISCARD_BEHIND_CENTER_FAMILIES = tuple(
    _with_marker_policy(family, "DISCARD_BEHIND_CENTER", "_discard_center")
    for family in _LASER_COLOR_POLICY_BASE_FAMILIES
)
_LIGHT_CONE_FAMILIES = tuple(
    _with_marker_policy(family, "LIGHT_CONE", "_light_cone")
    for family in _LASER_COLOR_POLICY_BASE_FAMILIES
)
MAIN_PART_VERTEX_FAMILIES += (
    _DISCARD_BEHIND_CENTER_FAMILIES + _LIGHT_CONE_FAMILIES
)


def _split_parameters(source: str, start: int, end: int) -> list[str]:
    chunks: list[str] = []
    chunk_start = start
    depth = 0
    for index in range(start, end):
        character = source[index]
        if character in "([<":
            depth += 1
        elif character in ")]>":
            depth -= 1
        elif character == "," and depth == 0:
            chunks.append(source[chunk_start:index])
            chunk_start = index + 1
    chunks.append(source[chunk_start:end])
    return chunks


def parse_entry_signature(
    source: str, entry_point: str = "mainVS"
) -> tuple[str, tuple[HlslParameter, ...]]:
    """Return the original signature and semantic parameter inventory."""
    match = re.search(rf"\bvoid\s+{re.escape(entry_point)}\s*\(", source)
    if match is None:
        raise RuntimeError(f"semantic source has no {entry_point} entry point")
    opening = source.find("(", match.start())
    depth = 0
    closing = None
    for index in range(opening, len(source)):
        if source[index] == "(":
            depth += 1
        elif source[index] == ")":
            depth -= 1
            if depth == 0:
                closing = index
                break
    if closing is None:
        raise RuntimeError(f"unterminated {entry_point} signature")
    parameters: list[HlslParameter] = []
    for raw in _split_parameters(source, opening + 1, closing):
        declaration = " ".join(raw.split())
        parameter = _PARAMETER.fullmatch(declaration)
        if parameter is None:
            raise RuntimeError(f"unsupported HLSL parameter: {declaration}")
        qualifiers = parameter.group("qualifiers").lower().split()
        parameters.append(
            HlslParameter(
                declaration=declaration,
                type_name=parameter.group("type"),
                variable=parameter.group("name"),
                semantic=SemanticKey.parse(parameter.group("semantic")),
                output="out" in qualifiers or "inout" in qualifiers,
            )
        )
    return source[match.start():closing + 1].rstrip(), tuple(parameters)


def classify_main_part_vertex_family(
    defines: Iterable[str], source: str
) -> MainPartVertexFamily | None:
    """Select one unambiguous family from defines plus runtime signature."""
    _signature, parameters = parse_entry_signature(source)
    matches = [
        family
        for family in MAIN_PART_VERTEX_FAMILIES
        if family.matches(defines, parameters)
    ]
    if len(matches) > 1:
        direct_matches = [
            family for family in matches if family.direct_output is not None
        ]
        if len(direct_matches) == 1:
            return direct_matches[0]
    if len(matches) > 1:
        names = ", ".join(family.name for family in matches)
        raise RuntimeError(f"ambiguous main_part vertex family: {names}")
    return matches[0] if matches else None


def _resolve_family_expression(
    expression: str, inputs: dict[SemanticKey, str]
) -> str:
    """Bind ``$SEMANTIC0`` references to recovered parameter variables."""

    def replace(match: re.Match[str]) -> str:
        semantic = SemanticKey(match.group(1), int(match.group(2)))
        return inputs[semantic]

    return re.sub(r"\$([A-Z_]+)(\d+)", replace, expression)


def lift_main_part_vertex_family(
    defines: Iterable[str], source: str
) -> tuple[str, str] | None:
    """Generate a thin wrapper for a recognized declarative vertex family."""
    signature, parameters = parse_entry_signature(source)
    family = classify_main_part_vertex_family(defines, source)
    if family is None:
        return None
    supplemental_cbuffer_includes = []
    for cbuffer, filename in family.cbuffers:
        if re.search(rf"\bcbuffer\s+{re.escape(cbuffer)}\b", source):
            source = replace_cbuffer_with_include(source, cbuffer, filename)
        elif filename not in source:
            # DXBC decompilation omits feature cbuffers when a permutation
            # enables the feature but transfers none of its resulting fields.
            # Supplying the exact ABI include is safe: dead helper paths are
            # removed and the unused binding does not enter reflection.
            supplemental_cbuffer_includes.append(
                f'#include "include/{filename}"'
            )
    declarations = source[:source.index("// 3Dmigoto declarations")].rstrip()
    if supplemental_cbuffer_includes:
        declarations += "\n\n" + "\n".join(supplemental_cbuffer_includes)
    inputs = {
        parameter.semantic: parameter.variable
        for parameter in parameters
        if not parameter.output
    }
    outputs = {
        parameter.semantic: parameter.variable
        for parameter in parameters
        if parameter.output
    }
    arguments = []
    for binding in family.inputs:
        if binding.literal:
            expression = _resolve_family_expression(binding.literal, inputs)
        else:
            assert binding.semantic is not None
            expression = inputs[binding.semantic]
            if binding.swizzle:
                expression += f".{binding.swizzle}"
        arguments.append(expression)
    prelude_lines = [
        "  " + _resolve_family_expression(line, inputs)
        for line in family.prelude
    ]
    include_block = "\n".join(
        f'#include "include/{filename}"' for filename in family.assets
    )
    call = f"{family.evaluator}(\n      " + ", ".join(arguments) + ")"
    if family.direct_output is not None:
        body = f"  {outputs[family.direct_output]} = {call};"
    else:
        assert family.result_type is not None
        mutation_lines = []
        observed_fields = {
            field
            for semantic, field in family.outputs
            if semantic in outputs
        }
        for mutation in family.mutations:
            if not mutation.requires_output and mutation.field not in observed_fields:
                continue
            mutation_arguments = []
            for binding in mutation.inputs:
                if binding.literal:
                    expression = _resolve_family_expression(
                        binding.literal, inputs
                    )
                else:
                    assert binding.semantic is not None
                    expression = inputs[binding.semantic]
                    if binding.swizzle:
                        expression += f".{binding.swizzle}"
                mutation_arguments.append(expression)
            mutation_call = (
                f"{mutation.evaluator}("
                + ", ".join(mutation_arguments)
                + ")"
                if mutation.evaluator else mutation_arguments[0]
            )
            mutation_lines.append(
                f"  vertex.{mutation.field} = {mutation_call};"
            )
        assignments = []
        for semantic, field in family.outputs:
            if semantic not in outputs:
                continue
            expression = (
                _resolve_family_expression(field[1:], inputs)
                if field.startswith("=") else f"vertex.{field}"
            )
            assignments.append(f"  {outputs[semantic]} = {expression};")
        body = (
            ("\n".join(prelude_lines) + "\n" if prelude_lines else "")
            + f"  {family.result_type} vertex = {call};\n"
            + "\n".join(mutation_lines)
            + ("\n" if mutation_lines else "")
            + "\n".join(assignments)
        )
    lifted = (
        declarations
        + "\n\n"
        + include_block
        + "\n\n"
        + signature
        + "\n{\n"
        + body
        + "\n}\n"
    )
    return family.name, lifted


def vertex_family_shape(defines: Iterable[str]) -> tuple[str, ...]:
    """Stable clustering key excluding transfer/output-only definitions."""
    return tuple(
        sorted(
            define
            for define in defines
            if define == "VERTEX_SHADER" or define.startswith("VS_")
        )
    )
