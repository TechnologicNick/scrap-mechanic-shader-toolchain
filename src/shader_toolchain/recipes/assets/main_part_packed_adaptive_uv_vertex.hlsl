#ifndef MAIN_PART_PACKED_ADAPTIVE_UV_VERTEX_HLSL
#define MAIN_PART_PACKED_ADAPTIVE_UV_VERTEX_HLSL

float2 EvaluateMainPartPackedAdaptiveScrolledUv(
    float2 baseUv, int4 packedLocalToWorld, uint4 packedInstance)
{
  uint axisZIndex = ((uint)packedLocalToWorld.w >> 4u) & 15u;
  uint axisXIndex = (uint)packedLocalToWorld.w & 15u;
  float3 axisZ = MAIN_PART_PACKED_AXES[axisZIndex];
  float3 axisX = MAIN_PART_PACKED_AXES[axisXIndex];
  float3 axisY = cross(axisZ, axisX);
  axisY *= rsqrt(dot(axisY, axisY));
  axisY *= 0.25;
  uint transformIndex = packedInstance.y & 1023u;
  float3 diagonalDirection = axisX + axisY + axisZ;
  float3 transformed = MainPartTransformPackedDirection(
      diagonalDirection, transformIndex).xyz;
  float adaptiveScale = 4.0 * sqrt(dot(transformed, transformed));
  return baseUv * adaptiveScale + frac(cb_uvScroll.vSpeed * cb_fTime);
}

#endif // MAIN_PART_PACKED_ADAPTIVE_UV_VERTEX_HLSL
