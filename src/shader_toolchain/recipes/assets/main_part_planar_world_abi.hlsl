#ifndef MAIN_PART_PLANAR_WORLD_ABI_HLSL
#define MAIN_PART_PLANAR_WORLD_ABI_HLSL

cbuffer CB_UV_PLANAR_WORLD_SPACE
{
  struct
  {
    float2 vScale;
    float2 _padd0;
  } cb_planarWorldSpace : packoffset(c0);
}

#endif // MAIN_PART_PLANAR_WORLD_ABI_HLSL
