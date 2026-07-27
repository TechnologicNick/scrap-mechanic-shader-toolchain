"""Command-line interface for the Scrap Mechanic shader toolchain."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .build import build_cache
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
        "--strict",
        action="store_true",
        help="fail instead of using exact recovered DXBC when a lift does not compile",
    )
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
                allow_dxbc_fallback=not args.strict,
                jobs=args.jobs,
                progress=lambda completed, total: print(
                    f"compiled {completed}/{total}", file=sys.stderr
                ),
            )
            print(json.dumps(summary, indent=2, sort_keys=True))
            return 0
    except (OSError, FormatError, RuntimeError, ToolchainError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
