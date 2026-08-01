"""Command-line interface for the Scrap Mechanic shader toolchain."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .build import build_cache
from .compare import compare_caches
from .gpu_fuzz import fuzz_semantic_shader
from .materialize import materialize_semantic_variant, semantic_records
from .main_part_permutation_graph import (
    build_main_part_permutation_graph,
    summarize_main_part_permutation_graph,
)
from .main_part_family_miner import (
    mine_main_part_families,
    summarize_mined_families,
)
from .main_part_synthesis import (
    build_synthesis_readiness_report,
    summarize_synthesis_readiness,
    write_synthesis_specifications,
)
from .main_part_synthesis_emitter import (
    emit_corpus_family,
    install_validated_family,
    validate_emitted_family,
)
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
    materialize_parser = commands.add_parser(
        "materialize",
        help="write one semantic permutation without generated selector dispatch",
    )
    materialize_parser.add_argument("corpus", type=Path)
    materialize_parser.add_argument("module")
    materialize_parser.add_argument("output", type=Path, nargs="?")
    materialize_parser.add_argument("--selector")
    materialize_parser.add_argument(
        "--define",
        dest="defines",
        action="append",
        default=[],
        help="require an exact recovered definition (repeatable)",
    )
    materialize_parser.add_argument(
        "--list", action="store_true", help="list selectors instead of writing HLSL"
    )
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
    fuzz_parser.add_argument("--selector", dest="pixel_selector")
    fuzz_parser.add_argument("--cases", type=int, default=256)
    fuzz_parser.add_argument(
        "--seed", type=lambda value: int(value, 0), default=0x534D465841413031
    )
    fuzz_parser.add_argument("--width", type=int, default=64)
    fuzz_parser.add_argument("--height", type=int, default=64)
    fuzz_parser.add_argument("--absolute-tolerance", type=float, default=0.0)
    fuzz_parser.add_argument("--relative-tolerance", type=float, default=0.0)
    fuzz_parser.add_argument("--ulp-tolerance", type=int, default=0)
    fuzz_parser.add_argument(
        "--failure-dir", type=Path, default=Path("gpu-fuzz-failure")
    )
    fuzz_parser.add_argument("--harness", type=Path)
    fuzz_parser.add_argument("--warp", action="store_true")
    fuzz_parser.add_argument(
        "--skip-corpus-verification",
        action="store_true",
        help="skip corpus verification when a trusted parent process already ran it",
    )
    fuzz_parser.add_argument("--report", type=Path)
    graph_parser = commands.add_parser(
        "main-part-graph",
        help="inventory main_part pixel shaders as composable semantic phases",
    )
    graph_parser.add_argument("corpus", type=Path)
    graph_parser.add_argument("--output", type=Path)
    graph_parser.add_argument("--summary-only", action="store_true")
    families_parser = commands.add_parser(
        "main-part-families",
        help="mine and rank selector-independent main_part graph families",
    )
    families_parser.add_argument("corpus", type=Path)
    families_parser.add_argument("--output", type=Path)
    families_parser.add_argument("--limit", type=int, default=25)
    families_parser.add_argument("--minimum-members", type=int, default=2)
    synthesis_parser = commands.add_parser(
        "main-part-synthesis",
        help="induce typed family templates and policy holes from main_part",
    )
    synthesis_parser.add_argument("corpus", type=Path)
    synthesis_parser.add_argument("--output", type=Path)
    synthesis_parser.add_argument("--limit", type=int, default=25)
    synthesis_parser.add_argument("--minimum-members", type=int, default=2)
    synthesis_parser.add_argument(
        "--spec-dir", type=Path,
        help="write semantic-named graph specifications for ready families",
    )
    emit_parser = commands.add_parser(
        "main-part-synthesis-emit",
        help="emit and validate one synthesized main_part family",
    )
    emit_parser.add_argument("corpus", type=Path)
    emit_parser.add_argument("--family", required=True)
    emit_parser.add_argument("--apply", action="store_true")
    emit_parser.add_argument(
        "--gpu-cases", type=int, default=64,
        help="GPU differential cases per member when applying (default: 64)",
    )
    emit_parser.add_argument("--output", type=Path)
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
        if args.command == "materialize":
            if args.list:
                records = semantic_records(args.corpus, args.module)
                print(json.dumps([
                    {
                        "selector": record["selector"],
                        "stage": record["stage"],
                        "entry_point": record["entry_point"],
                        "defines": record["defines"],
                    }
                    for record in records
                ], indent=2, sort_keys=True))
                return 0
            if args.output is None:
                raise ToolchainError("materialize needs OUTPUT unless --list is used")
            result = materialize_semantic_variant(
                args.corpus,
                args.module,
                args.output,
                selector=args.selector,
                required_defines=args.defines,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
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
                pixel_selector=args.pixel_selector,
                cases=args.cases,
                seed=args.seed,
                width=args.width,
                height=args.height,
                absolute_tolerance=args.absolute_tolerance,
                relative_tolerance=args.relative_tolerance,
                ulp_tolerance=args.ulp_tolerance,
                failure_dir=args.failure_dir,
                harness=args.harness,
                warp=args.warp,
                verify_corpus=not args.skip_corpus_verification,
            )
            rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
            if args.report:
                if args.report.exists():
                    raise ToolchainError(f"report path already exists: {args.report}")
                args.report.parent.mkdir(parents=True, exist_ok=True)
                args.report.write_text(rendered, encoding="utf-8", newline="\n")
            print(rendered, end="")
            return 0 if report["comparison"]["passed"] else 2
        if args.command == "main-part-graph":
            report = build_main_part_permutation_graph(args.corpus)
            if args.summary_only:
                report = summarize_main_part_permutation_graph(report)
            rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(rendered, encoding="utf-8", newline="\n")
            print(rendered, end="")
            return 0
        if args.command == "main-part-families":
            report = mine_main_part_families(
                args.corpus, minimum_members=args.minimum_members
            )
            report = summarize_mined_families(report, limit=args.limit)
            rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(rendered, encoding="utf-8", newline="\n")
            print(rendered, end="")
            return 0
        if args.command == "main-part-synthesis":
            report = build_synthesis_readiness_report(
                args.corpus, minimum_members=args.minimum_members
            )
            if args.spec_dir:
                report["campaign"] = write_synthesis_specifications(
                    report, args.spec_dir
                )
            report = summarize_synthesis_readiness(
                report, limit=args.limit
            )
            rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(
                    rendered, encoding="utf-8", newline="\n"
                )
            print(rendered, end="")
            return 0
        if args.command == "main-part-synthesis-emit":
            emitted = emit_corpus_family(args.corpus, args.family)
            validated = validate_emitted_family(args.corpus, emitted)
            if args.apply:
                if args.gpu_cases < 1:
                    raise ValueError(
                        "--apply requires at least one GPU differential case"
                    )
                report = install_validated_family(
                    args.corpus, validated, gpu_cases=args.gpu_cases
                )
                report["applied"] = True
            else:
                report = {
                    "applied": False,
                    "family": emitted.family,
                    "asset": emitted.asset_filename,
                    "selector_count": len(validated.selectors),
                    "selectors": list(validated.selectors),
                    "common_token_ratio": emitted.common_token_ratio,
                    "common_region_count": emitted.common_region_count,
                    "policy_region_count": emitted.policy_region_count,
                    "assembly_exact_count": validated.assembly_exact_count,
                    "opcode_sequence_exact_count": (
                        validated.opcode_sequence_exact_count
                    ),
                }
            rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(
                    rendered, encoding="utf-8", newline="\n"
                )
            print(rendered, end="")
            return 0
    except (OSError, FormatError, RuntimeError, ToolchainError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
