import json
from pathlib import Path

from shader_toolchain.main_part_family_miner import mine_main_part_families


SOURCE = '''
void commonPS(
  float3 viewPosition : VIEW_POSITION0,
  float2 uv : UV0,
  float3 normal : NORMAL0,
  float4 color : VERTEXCOLOR0,
  float3 screenUv : SCREEN_UV0,
  float4 fog : FOG_COLOR0,
  uint face : SV_IsFrontFace0,
  out float4 target : SV_Target0,
  out float4 auxiliary : SV_Target1)
{
  float4 partPositionState;
  target = partPositionState;
  auxiliary = 0;
}
'''


def test_family_miner_discovers_complete_policy_matrix(tmp_path: Path) -> None:
    snippets = tmp_path / "semantic" / "include" / "main_part"
    snippets.mkdir(parents=True)
    shaders = []
    policies = (
        ("A", (), "PS_REFLECTION_OFF"),
        ("B", (), "PS_REFLECTION_SINGLE"),
        ("C", ("PS_SHADER_QUALITY_HIGH",), "PS_REFLECTION_OFF"),
        ("D", ("PS_SHADER_QUALITY_HIGH",), "PS_REFLECTION_SINGLE"),
    )
    for suffix, quality, reflection in policies:
        selector = f"SM_SHADER_{suffix}"
        shaders.append({
            "selector": selector,
            "source_name": "main_part",
            "stage": "pixel",
            "defines": [
                "PIXEL_SHADER", "PS_PERM_TRANSPARANT_SURFACE",
                reflection, *quality,
            ],
        })
        (snippets / f"{selector}.hlsl").write_text(SOURCE, encoding="utf-8")
    (tmp_path / "manifest.json").write_text(
        json.dumps({"shaders": shaders}), encoding="utf-8"
    )

    report = mine_main_part_families(tmp_path)
    assert report["candidate_count"] == 1
    candidate = report["candidates"][0]
    assert candidate["member_count"] == 4
    assert candidate["matrix_complete"]
    assert candidate["missing_policies"] == ()
    assert candidate["graph_specification_draft"]["axes"] == {
        "quality": ["default", "high"],
        "reflection": ["off", "single"],
    }

