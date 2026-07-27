"""Command-line interface for the Scrap Mechanic shader toolchain."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .build import build_cache
from .compare import compare_caches
from .gpu_fuzz import fuzz_semantic_shader
from .reconstruct import ToolchainError, reconstruct, verify_output
from .sbc import FormatError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sm-shaders")
    commands = parser.add_subparsers(dest="command", required=True)
    reconstruct_parser = commands.add_parser(
        "reconstruct", help="extract and lift shaders.sbc into 80 HLSL modules"
    )
    reconstruct_parser.add_argument("cache", type=Path)
    reconstruct_parser.add_argument("output", type=Path)
    reconstruct_parser.add_argument("--3dmigoto", type=Path, dest="migoto")
    reconstruct_parser.add_argument("--dxdecompiler", type=Path)
    verify_parser = commands.add_parser(
        "verify", help="validate and hash a reconstructed HLSL corpus"
    )
    verify_parser.add_argument("output", type=Path)
    build_parser = commands.add_parser(
        "build", help="compile an HLSL corpus back into shaders.sbc"
    )
    build_parser.add_argument("corpus", type=Path)
    build_parser.add_argument("output", type=Path)
    build_parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        help="parallel compiler workers (default: all logical CPUs)",
    )
    build_parser.add_argument(
        "--recompile-all",
        action="store_true",
        help="research mode: send unchanged branches through D3DCompile too",
    )
    build_parser.add_argument(
        "--allow-dxbc-fallback",
        action="store_true",
        help="with --recompile-all, use exact DXBC when compilation fails",
    )
    build_parser.add_argument(
        "--allow-interface-changes",
        action="store_true",
        help="allow edited shaders to change reflected runtime ABI",
    )
    build_parser.add_argument(
        "--strict",
        action="store_true",
        help="deprecated alias for --recompile-all",
    )
    compare_parser = commands.add_parser(
        "compare", help="compare shader assembly and runtime ABI between two caches"
    )
    compare_parser.add_argument("baseline", type=Path)
    compare_parser.add_argument("candidate", type=Path)
    compare_parser.add_argument("--report", type=Path)
    compare_parser.add_argument("--diff-dir", type=Path)
    fuzz_parser = commands.add_parser(
        "gpu-fuzz", help="differentially fuzz exact and semantic shaders on D3D11"
    )
    fuzz_parser.add_argument("corpus", type=Path)
    fuzz_parser.add_argument("--shader", default="post_fxaa", dest="source_name")
    fuzz_parser.add_argument("--cases", type=int, default=256)
    fuzz_parser.add_argument(
        "--seed", type=lambda value: int(value, 0), default=0x534D465841413031
    )
    fuzz_parser.add_argument("--width", type=int, default=64)
    fuzz_parser.add_argument("--height", type=int, default=64)
    fuzz_parser.add_argument("--absolute-tolerance", type=float, default=0.0)
    fuzz_parser.add_argument("--relative-tolerance", type=float, default=0.0)
    fuzz_parser.add_argument(
        "--failure-dir", type=Path, default=Path("gpu-fuzz-failure")
    )
    fuzz_parser.add_argument("--harness", type=Path)
    fuzz_parser.add_argument("--warp", action="store_true")
    fuzz_parser.add_argument("--report", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "reconstruct":
            summary = reconstruct(
                args.cache,
                args.output,
                migoto=args.migoto,
                dx_decompiler=args.dxdecompiler,
            )
            print(json.dumps(summary, indent=2, sort_keys=True))
            return 0
        if args.command == "verify":
            print(json.dumps(verify_output(args.output), indent=2, sort_keys=True))
            return 0
        if args.command == "build":
            summary = build_cache(
                args.corpus,
                args.output,
                recompile_all=args.recompile_all or args.strict,
                allow_dxbc_fallback=args.allow_dxbc_fallback,
                allow_interface_changes=args.allow_interface_changes,
                jobs=args.jobs,
                progress=lambda completed, total: print(
                    f"compiled {completed}/{total}", file=sys.stderr
                ),
            )
            print(json.dumps(summary, indent=2, sort_keys=True))
            return 0
        if args.command == "compare":
            summary = compare_caches(
                args.baseline,
                args.candidate,
                report_path=args.report,
                diff_dir=args.diff_dir,
            )
            print(json.dumps(summary, indent=2, sort_keys=True))
            return 0
        if args.command == "gpu-fuzz":
            report = fuzz_semantic_shader(
                args.corpus,
                source_name=args.source_name,
                cases=args.cases,
                seed=args.seed,
                width=args.width,
                height=args.height,
                absolute_tolerance=args.absolute_tolerance,
                relative_tolerance=args.relative_tolerance,
                failure_dir=args.failure_dir,
                harness=args.harness,
                warp=args.warp,
            )
            rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
            if args.report:
                if args.report.exists():
                    raise ToolchainError(f"report path already exists: {args.report}")
                args.report.parent.mkdir(parents=True, exist_ok=True)
                args.report.write_text(rendered, encoding="utf-8", newline="\n")
            print(rendered, end="")
            return 0 if report["comparison"]["passed"] else 2
    except (OSError, FormatError, RuntimeError, ToolchainError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
