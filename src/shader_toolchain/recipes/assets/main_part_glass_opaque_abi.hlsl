#ifndef MAIN_PART_GLASS_OPAQUE_ABI_HLSL
#define MAIN_PART_GLASS_OPAQUE_ABI_HLSL

// Compact glass parameters used by PS_GLASS_OPAQUE forward permutations.
cbuffer CB_GLASS
{
  struct
  {
    float fTransmissionBase;
    float fTransmissionRange;
    float fResponsiveGlowBase;
    float fResponsiveGlowRange;
    float fAoMultiplier;
    float3 __padd0;
  } cb_glass : packoffset(c0);
}

#endif // MAIN_PART_GLASS_OPAQUE_ABI_HLSL
