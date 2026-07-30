// Low-quality legacy-glass policy using the global single reflection layer.
// Material, directional lighting, and composition remain shared with the
// reflection-off/no-sampled-reflection policy.
#define MAIN_PART_GLASS_SURFACE_ENABLE_SINGLE_PROBE
#define MAIN_PART_LEGACY_GLASS_SURFACE_SINGLE_PROBE
#include "main_part_legacy_glass_surface_basic.hlsl"
#undef MAIN_PART_LEGACY_GLASS_SURFACE_SINGLE_PROBE
#undef MAIN_PART_GLASS_SURFACE_ENABLE_SINGLE_PROBE
