"""Run a bounded selector range without retaining a whole large-module audit."""

from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path

from shader_toolchain.gpu_fuzz import fuzz_semantic_shader


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", type=Path)
    parser.add_argument("module")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--cases", type=int, default=256)
    args = parser.parse_args()
    manifest = json.loads((args.corpus / "manifest.json").read_text(encoding="utf-8"))
    selectors = [
        shader
        for shader in manifest["shaders"]
        if shader["source_name"] == args.module and shader["stage"] != "vertex"
    ]
    selected = selectors[args.start : args.start + args.count]
    compared = 0
    for offset, shader in enumerate(selected, args.start + 1):
        report = fuzz_semantic_shader(
            args.corpus,
            source_name=args.module,
            pixel_selector=shader["selector"],
            cases=args.cases,
            verify_corpus=False,
        )
        comparison = report["comparison"]
        if not comparison["passed"]:
            print(f"FAIL {offset} {shader['selector']}", flush=True)
            return 2
        compared += int(comparison["compared_values"])
        gc.collect()
    print(
        f"PASS {args.module} selectors {args.start + 1}-"
        f"{args.start + len(selected)} values={compared}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
