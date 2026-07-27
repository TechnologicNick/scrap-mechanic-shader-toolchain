import json

from shader_toolchain.build import (
    module_variants,
    serialize_cache,
    serialize_payload,
    stable_diagnostic,
)
from shader_toolchain.sbc import parse_cache, parse_payload


def test_module_variants_extracts_generated_branches() -> None:
    source = """// module
#if defined(SM_SHADER_000000000000000A)
void first() {}
#elif defined(SM_SHADER_000000000000000B)
void second() {}
#endif
"""
    assert module_variants(source) == {
        "SM_SHADER_000000000000000A": "void first() {}\n",
        "SM_SHADER_000000000000000B": "void second() {}\n",
    }


def test_cache_metadata_serialization_round_trip(tmp_path) -> None:
    manifest = {
        "jobs": [{"job_key": "0x0000000000000020", "shader_index": 0}],
        "resource_ids": ["00" * 16],
        "shaders": [
            {
                "shader_key": "0x0000000000000010",
                "stage_value": 2,
                "resource_id_indices": [0],
                "descriptor": "example:mainPS  PIXEL_SHADER",
            }
        ],
    }
    bundle = b"BSCDexample"
    cache = serialize_cache(serialize_payload(manifest, bundle))
    path = tmp_path / "shaders.sbc"
    path.write_bytes(cache)

    header, payload = parse_cache(path)
    metadata, parsed_bundle = parse_payload(payload)

    assert header["shader_cache_version"] == 1
    assert parsed_bundle == bundle
    assert metadata["shaders"][0]["source_name"] == "example"
    assert metadata["jobs"] == manifest["jobs"]


def test_stable_diagnostic_removes_local_path() -> None:
    message = (
        "D3DCompile failed: C:\\machine\\reconstructed.hlsl(12,4): "
        "error X3004: undeclared identifier 'thing'\n\x00"
    )
    assert stable_diagnostic(message) == "error X3004: undeclared identifier 'thing'"
