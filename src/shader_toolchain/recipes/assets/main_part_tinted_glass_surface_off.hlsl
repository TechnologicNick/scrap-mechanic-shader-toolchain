// Low-quality tinted glass without sampled reflections retains the fixed
// gloss response used by the reflection-off policy.
#define MAIN_PART_LEGACY_GLASS_SURFACE_OFF_AMBIENT
#include "main_part_legacy_glass_surface_basic.hlsl"
#undef MAIN_PART_LEGACY_GLASS_SURFACE_OFF_AMBIENT
