import json
import hashlib

import pytest

from shader_toolchain.reconstruct import (
    ToolchainError,
    normalize_3dmigoto,
    output_digest,
    render_module,
    verify_output,
)


def test_normalize_3dmigoto_is_stable_and_repairs_compute_signature() -> None:
    source = """// ---- Created with 3Dmigoto v1.4.9 on an unstable date

void main)
{
  uint x = vThreadGroupID.x + vThreadIDInGroup.x;
}
"""
    assembly = "dcl_thread_group 8, 4, 2"

    normalized = normalize_3dmigoto(source, assembly, "mainCS")

    assert "unstable date" not in normalized
    assert "// Lifted with 3Dmigoto v1.4.9" in normalized
    assert "[numthreads(8, 4, 2)]" in normalized
    assert "void mainCS(uint3 vThreadGroupID : SV_GroupID, " in normalized
    assert "uint3 vThreadIDInGroup : SV_GroupThreadID)" in normalized


def test_render_module_uses_one_selector_branch_per_variant() -> None:
    variants = [
        {
            "selector": "SM_SHADER_A",
            "shader_key": "0x000000000000000a",
            "stage": "pixel",
            "entry_point": "mainPS",
            "descriptor": "example:mainPS  PIXEL_SHADER",
            "lift_status": "lifted",
            "backend": "3dmigoto",
            "hlsl": "void mainPS() {}\n",
        },
        {
            "selector": "SM_SHADER_B",
            "shader_key": "0x000000000000000b",
            "stage": "vertex",
            "entry_point": "mainVS",
            "descriptor": "example:mainVS  VERTEX_SHADER",
            "lift_status": "lifted",
            "backend": "3dmigoto",
            "hlsl": "void mainVS() {}\n",
        },
    ]

    result = render_module("example", variants)

    assert result.count("defined(SM_SHADER_") == 2
    assert "#if defined(SM_SHADER_A)" in result
    assert "#elif defined(SM_SHADER_B)" in result
    assert result.endswith("#endif\n")


def test_verify_output_checks_manifest_and_is_deterministic(tmp_path) -> None:
    output = tmp_path / "output"
    hlsl = output / "hlsl"
    hlsl.mkdir(parents=True)
    (hlsl / "example.hlsl").write_text(
        "#if defined(SM_SHADER_A)\n#endif\n", encoding="utf-8"
    )
    manifest = {
        "summary": {"module_count": 1, "shader_count": 1},
        "shaders": [
            {"source_name": "example", "selector": "SM_SHADER_A"}
        ],
    }
    (output / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = verify_output(output, expected_modules=1)

    assert result["module_count"] == 1
    assert result["shader_count"] == 1
    assert result["digest_sha256"] == output_digest(output)


def test_verify_output_rejects_missing_selector(tmp_path) -> None:
    output = tmp_path / "output"
    (output / "hlsl").mkdir(parents=True)
    (output / "hlsl" / "example.hlsl").write_text("// empty\n", encoding="utf-8")
    manifest = {
        "summary": {"module_count": 1, "shader_count": 1},
        "shaders": [{"source_name": "example", "selector": "SM_SHADER_A"}],
    }
    (output / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ToolchainError, match="shader selectors are missing"):
        verify_output(output, expected_modules=1)


def test_verify_output_checks_exact_dxbc_sidecar(tmp_path) -> None:
    output = tmp_path / "output"
    (output / "hlsl").mkdir(parents=True)
    (output / "dxbc").mkdir()
    (output / "hlsl" / "example.hlsl").write_text(
        "#if defined(SM_SHADER_A)\n#endif\n", encoding="utf-8"
    )
    bytecode = b"DXBC example"
    (output / "dxbc" / "a.dxbc").write_bytes(bytecode)
    manifest = {
        "summary": {"module_count": 1, "shader_count": 1},
        "shaders": [
            {
                "source_name": "example",
                "selector": "SM_SHADER_A",
                "dxbc_path": "dxbc/a.dxbc",
                "dxbc_sha256": hashlib.sha256(bytecode).hexdigest(),
            }
        ],
    }
    (output / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    verify_output(output, expected_modules=1)
    (output / "dxbc" / "a.dxbc").write_bytes(b"corrupt")

    with pytest.raises(ToolchainError, match="DXBC sidecars are missing or corrupt"):
        verify_output(output, expected_modules=1)
