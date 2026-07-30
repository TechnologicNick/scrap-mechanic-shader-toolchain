// Packed-LTW scale-aware wave geometry shared by output-policy wrappers.

float3 MainPartApplyPackedScaledWave(
    float3 basePosition,
    float3 normalEncoded,
    int4 packedLocalToWorld,
    uint4 packedInstance)
{
  uint axisZIndex = ((uint)packedLocalToWorld.w >> 4u) & 15u;
  uint axisXIndex = (uint)packedLocalToWorld.w & 15u;
  float3 axisZ = MAIN_PART_PACKED_AXES[axisZIndex];
  float3 axisX = MAIN_PART_PACKED_AXES[axisXIndex];
  float3 axisY = cross(axisZ, axisX);
  axisY *= rsqrt(dot(axisY, axisY));
  axisY *= 0.25;
  uint transformIndex = packedInstance.y & 1023u;
  float4 worldAxisY = MainPartTransformPackedDirection(axisY, transformIndex);
  float4 worldAxisX = MainPartTransformPackedDirection(axisX, transformIndex);
  float4 worldAxisZ = MainPartTransformPackedDirection(axisZ, transformIndex);
  const float diagonalComponent = 0.577350259;
  float4 transformedDiagonal = worldAxisY * diagonalComponent;
  transformedDiagonal = worldAxisX * diagonalComponent
      + transformedDiagonal;
  transformedDiagonal = worldAxisZ * diagonalComponent
      + transformedDiagonal;
  float waveScale = sqrt(dot(transformedDiagonal, transformedDiagonal));
  return MainPartApplyScaledWaveWithScale(
      basePosition, normalEncoded, waveScale);
}

float4 EvaluateMainPartPackedScaledWaveClipPosition(
    float3 basePosition,
    float3 normalEncoded,
    int4 packedLocalToWorld,
    uint4 packedInstance)
{
  uint axisZIndex = ((uint)packedLocalToWorld.w >> 4u) & 15u;
  uint axisXIndex = (uint)packedLocalToWorld.w & 15u;
  float3 axisZ = MAIN_PART_PACKED_AXES[axisZIndex];
  float3 axisX = MAIN_PART_PACKED_AXES[axisXIndex];
  float3 axisY = cross(axisZ, axisX);
  axisY *= rsqrt(dot(axisY, axisY));
  axisY *= 0.25;

  uint transformIndex = packedInstance.y & 1023u;
  float4 worldAxisY = MainPartTransformPackedDirection(axisY, transformIndex);
  float4 worldAxisX = MainPartTransformPackedDirection(axisX, transformIndex);
  float4 worldAxisZ = MainPartTransformPackedDirection(axisZ, transformIndex);
  const float diagonalComponent = 0.577350259;
  float4 transformedDiagonal = worldAxisY * diagonalComponent;
  transformedDiagonal = worldAxisX * diagonalComponent
      + transformedDiagonal;
  transformedDiagonal = worldAxisZ * diagonalComponent
      + transformedDiagonal;
  float waveScale = sqrt(dot(transformedDiagonal, transformedDiagonal));

  float3 localPosition = MainPartApplyScaledWaveWithScale(
      basePosition, normalEncoded, waveScale);
  float3 worldPosition = worldAxisY.xyz * localPosition.y;
  worldPosition = worldAxisX.xyz * localPosition.x + worldPosition;
  worldPosition = worldAxisZ.xyz * localPosition.z + worldPosition;
  float3 quantizedTranslation = (float3)packedLocalToWorld.xyz * 0.125;
  worldPosition += MainPartTransformPackedPoint(
      quantizedTranslation, transformIndex);

  float shakeWeight = (float)(packedInstance.y >> 26u) * (1.0 / 63.0);
  worldPosition += cb_vShake * shakeWeight;
  float4 viewPosition = worldToView._m01_m11_m21_m31 * worldPosition.y;
  viewPosition = worldToView._m00_m10_m20_m30 * worldPosition.x
      + viewPosition;
  viewPosition = worldToView._m02_m12_m22_m32 * worldPosition.z
      + viewPosition;
  viewPosition = worldToView._m03_m13_m23_m33 + viewPosition;
  float4 clipPosition = cb_xViewToProjection._m01_m11_m21_m31
      * viewPosition.y;
  clipPosition = cb_xViewToProjection._m00_m10_m20_m30
      * viewPosition.x + clipPosition;
  clipPosition = cb_xViewToProjection._m02_m12_m22_m32
      * viewPosition.z + clipPosition;
  return cb_xViewToProjection._m03_m13_m23_m33
      * viewPosition.w + clipPosition;
}
