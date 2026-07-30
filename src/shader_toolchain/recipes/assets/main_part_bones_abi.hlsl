#ifndef MAIN_PART_BONES_ABI_HLSL
#define MAIN_PART_BONES_ABI_HLSL

// Exact skeletal palette declaration recovered from DXBC reflection.
cbuffer CB_BONES : register(b4)
{
  float4x4 xBones[1024] : packoffset(c0);
}

#endif // MAIN_PART_BONES_ABI_HLSL
