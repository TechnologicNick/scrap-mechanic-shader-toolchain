import json
from pathlib import Path

from shader_toolchain.main_part_inventory import build_main_part_inventory


def test_inventory_clusters_transfer_variants_by_structural_shape(
    tmp_path: Path,
) -> None:
    corpus = tmp_path
    snippets = corpus / "semantic" / "include" / "main_part"
    snippets.mkdir(parents=True)
    shaders = []
    for index, transfers in enumerate(
        (["TRANSFER_UV0"], ["TRANSFER_COLOR", "TRANSFER_UV0"])
    ):
        selector = f"SM_SHADER_{index:016X}"
        shaders.append(
            {
                "selector": selector,
                "source_name": "main_part",
                "stage": "vertex",
                "defines": [
                    "VERTEX_SHADER",
                    "VS_FULL_TRANSFORM",
                    "VS_INPUT_TANGENTS",
                    "VS_INPUT_UV1",
                    "VS_POSE_0_ANIM",
                    *transfers,
                ],
            }
        )
        (snippets / f"{selector}.hlsl").write_text(
            '''void mainVS(
  float3 v0 : POSITION0, float4 v1 : TEXCOORD0,
  float2 v2 : TEXCOORD1, float3 v3 : NORMAL0,
  float4 v4 : TANGENT0, float3 v5 : POSITION1,
  float3 v6 : NORMAL1, float4 v7 : LTW0,
  float4 v8 : LTW1, float4 v9 : LTW2,
  uint4 v10 : INSTANCE_DATA0, out float4 o0 : SV_Position0,
  out float2 o1 : UV0) {}
''',
            encoding="utf-8",
        )
    (corpus / "manifest.json").write_text(
        json.dumps({"shaders": shaders}), encoding="utf-8"
    )
    report = build_main_part_inventory(corpus, large_threshold=0)
    assert report["structural_cluster_count"] == 1
    assert report["clusters"][0]["count"] == 2
    assert report["clusters"][0]["covered_count"] == 2
    assert report["covered_large_vertex_count"] == 2
