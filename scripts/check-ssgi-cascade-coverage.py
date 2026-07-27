"""Prove that the spatial SSGI corpus reaches the structurally lifted paths."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from shader_toolchain.gpu_fuzz import fuzz_semantic_shader
from shader_toolchain.reconstruct import ToolchainError, verify_output


COMMON_CANARIES = {
    "packed_decode": "return float3(16384.0, 8192.0, 4096.0);",
    "bilateral_weights": "return float4(16384.0, 8192.0, 4096.0, 2048.0);",
    "far_depth_exit": "o0.xy = float2(0.25, 0.75); return;",
}
PASS_CANARIES = {
    "PS_FINAL": ("final_resolve", "o0.xy = float2(0.25, 0.75); return;"),
    "PS_DOWN_RES": ("downsample", "o0.xy = float2(0.25, 0.75); return;"),
    "default": ("parent_upscale", "o0.xy = float2(0.25, 0.75); return;"),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--cases", type=int, default=256)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    verify_output(args.corpus, verify_hlsl_fingerprints=False)
    manifest = json.loads((args.corpus / "manifest.json").read_text(encoding="utf-8"))
    shaders = [
        shader for shader in manifest["shaders"]
        if shader["source_name"] == "ssgi_cascade" and shader["stage"] == "pixel"
    ]
    if len(shaders) != 4:
        raise ToolchainError(f"expected four SSGI cascade selectors, found {len(shaders)}")

    results = []
    with tempfile.TemporaryDirectory(prefix="sm-ssgi-cascade-canaries-") as root:
        for shader in shaders:
            probes = dict(COMMON_CANARIES)
            if not (
                "PS_DOWN_RES" in shader["defines"] or "PS_FINAL" in shader["defines"]
            ):
                probes.pop("bilateral_weights")
            if "PS_DOWN_RES" in shader["defines"] or "PS_FINAL" in shader["defines"]:
                probes["packed_encode"] = "return 0.123456791;"
            pass_key = next(
                (key for key in ("PS_FINAL", "PS_DOWN_RES") if key in shader["defines"]),
                "default",
            )
            probes[PASS_CANARIES[pass_key][0]] = PASS_CANARIES[pass_key][1]
            for branch, statement in probes.items():
                marker = f"// SM_COVERAGE_CANARY: {branch}"
                report = fuzz_semantic_shader(
                    args.corpus,
                    source_name="ssgi_cascade",
                    pixel_selector=shader["selector"],
                    cases=args.cases,
                    verify_corpus=False,
                    failure_dir=Path(root) / shader["selector"] / branch,
                    source_replacements={marker: f"{marker}\n    {statement}"},
                )
                reached = not report["comparison"]["passed"]
                results.append({
                    "selector": shader["selector"],
                    "branch": branch,
                    "reached": reached,
                    "differing_values": report["comparison"].get("differing_values", 0),
                })
                print(f"{'REACHED' if reached else 'MISSED '} {shader['selector']} {branch}")

    summary = {
        "passed": all(result["reached"] for result in results),
        "cases": args.cases,
        "results": results,
    }
    rendered = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8", newline="\n")
    if not summary["passed"]:
        print(rendered, end="")
        return 2
    print("PASS all SSGI cascade coverage canaries reached")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
