#ifndef MAIN_PART_UV_STEP_HLSL
#define MAIN_PART_UV_STEP_HLSL

// Advance UV0 in discrete time steps on each axis independently.
float2 EvaluateMainPartSteppedUv(float2 baseUv)
{
  float2 stepIndex = round(cb_uvStep.vInvDuration * cb_fTime);
  return baseUv + stepIndex * cb_uvStep.vStep;
}

#endif // MAIN_PART_UV_STEP_HLSL

