"""Prove that the volumetric GPU corpus reaches the structurally lifted paths."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from shader_toolchain.gpu_fuzz import fuzz_semantic_shader
from shader_toolchain.reconstruct import ToolchainError, verify_output


CANARIES = {
    "cone_mask": "radiance = float3(16384.0, 8192.0, 4096.0);",
    "cone_intersection": "return float3(16384.0, 8192.0, 4096.0);",
    "cone_march": "return float3(16384.0, 8192.0, 4096.0);",
    "cone_cookie": "attenuation += 16384.0;",
    "cone_shadow": "attenuation += 16384.0;",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--cases", type=int, default=256)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    verify_output(args.corpus, verify_hlsl_fingerprints=False)
    manifest = json.loads((args.corpus / "manifest.json").read_text(encoding="utf-8"))
    selectors = [
        shader["selector"]
        for shader in manifest["shaders"]
        if shader["source_name"] == "post_volumetric" and shader["stage"] == "pixel"
    ]
    if len(selectors) != 2:
        raise ToolchainError(
            f"expected two post_volumetric pixel selectors, found {len(selectors)}"
        )
    results = []
    with tempfile.TemporaryDirectory(prefix="sm-volumetric-canaries-") as failure_root:
        for selector in selectors:
            for branch, statement in CANARIES.items():
                marker = f"// SM_COVERAGE_CANARY: {branch}"
                report = fuzz_semantic_shader(
                    args.corpus,
                    source_name="post_volumetric",
                    pixel_selector=selector,
                    cases=args.cases,
                    verify_corpus=False,
                    failure_dir=Path(failure_root) / selector / branch,
                    source_replacements={marker: f"{marker}\n    {statement}"},
                )
                reached = not report["comparison"]["passed"]
                results.append({
                    "selector": selector,
                    "branch": branch,
                    "reached": reached,
                    "differing_values": report["comparison"].get("differing_values", 0),
                })
                print(
                    f"{'REACHED' if reached else 'MISSED '} {selector} {branch}",
                    flush=True,
                )

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
    print("PASS all volumetric coverage canaries reached")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
