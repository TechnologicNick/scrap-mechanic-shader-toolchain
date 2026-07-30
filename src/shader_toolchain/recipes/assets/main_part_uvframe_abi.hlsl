#ifndef MAIN_PART_UVFRAME_ABI_HLSL
#define MAIN_PART_UVFRAME_ABI_HLSL

// Atlas cell scale used by all VS_UV_ANIM vertex permutations.
cbuffer CB_UVFRAME
{
  float4 uvAnimationFrame : packoffset(c0);
}

#endif // MAIN_PART_UVFRAME_ABI_HLSL
