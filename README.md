# Scrap Mechanic Shader Toolchain

Reproducible extraction and reconstruction tools for Scrap Mechanic 1.0.x
`shaders.sbc` files.

The toolchain separates the cache into its metadata and 4,141 Shader Model 5
DXBC programs, lifts the programs to HLSL-like source with pinned third-party
decompilers, and consolidates the permutations into exactly 80 source-module
files.

The exact original HLSL is not present in the cache. Generated modules preserve
the recoverable source names, entry points, define sets, reflection declarations,
and a deterministic lifted implementation for every cached permutation.

Development is currently in progress. See [the format specification](docs/SHADERS-SBC-FORMAT.md).

