"""Command-line interface for the Scrap Mechanic shader toolchain."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

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
    except (OSError, FormatError, ToolchainError, ValueError) as error:
        print(f"error: {error}")
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
