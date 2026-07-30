#ifndef MAIN_PART_LASER_DISPLACEMENT_ABI_HLSL
#define MAIN_PART_LASER_DISPLACEMENT_ABI_HLSL

// Procedural geometry/color controls shared by VS_LASER_DISPLACEMENT paths.
cbuffer CB_LASER_DISPLACEMENT
{
  struct
  {
    float4 vDisplacementColor;
    float fDisplacementSpeed;
    float fDisplacementStrength;
    float fDisplacementFadeValue;
    float fDisplacementFadeRange;
    float fFlickerFrequencyValue;
    float fFlickerFrequencyOffset;
    float fWaveNoiseIntensity;
    float fSliceSize;
    float3 vSliceDirection;
    float fGlitchSpeed;
  } cb_laser_displacement : packoffset(c0);
}

#endif // MAIN_PART_LASER_DISPLACEMENT_ABI_HLSL
