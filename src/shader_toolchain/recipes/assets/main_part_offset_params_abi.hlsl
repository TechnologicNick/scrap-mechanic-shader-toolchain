#ifndef MAIN_PART_OFFSET_PARAMS_ABI_HLSL
#define MAIN_PART_OFFSET_PARAMS_ABI_HLSL

// Per-draw material overrides shared by the PS_SET_PARAMS permutations.
cbuffer CB_OFFSET_PARAMS
{
  struct
  {
    float3 vDiffuse;
    float _padd0;
    float fGlow;
    float fGloss;
    float fSpecular;
    float fAlpha;
    float fThickness;
    float fAo;
    float fBlend;
    float _padd1;
  } cb_offset : packoffset(c0);
}

#endif // MAIN_PART_OFFSET_PARAMS_ABI_HLSL
