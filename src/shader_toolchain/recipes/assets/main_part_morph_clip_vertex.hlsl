// Minimal explicit-LTW one-pose morph vertex.
// Rich surface variants build on the same position/instance decoding but add
// tangent frames and material channels; this core preserves the lean ABI.

float4 EvaluateMainPartMorphClipVertex(
    float3 basePosition,
    float3 morphPosition,
    float4 localToWorldRow0,
    float4 localToWorldRow1,
    float4 localToWorldRow2,
    uint4 packedInstance)
{
  // Phase 1: decode pose and shake weights.
  float shakeWeight = (float)(packedInstance.y >> 26u) * (1.0 / 63.0);
  float morphWeight = (float)(packedInstance.z & 65535u)
      * (1.0 / 65535.0);

  // Phase 2: morph in object space and apply the explicit LTW rows.
  float3 localPosition = (morphPosition - basePosition) * morphWeight
      + basePosition;
  float4 homogeneousPosition = float4(localPosition, 1.0);
  float3 worldPosition = float3(
      dot(localToWorldRow0, homogeneousPosition),
      dot(localToWorldRow1, homogeneousPosition),
      dot(localToWorldRow2, homogeneousPosition));
  worldPosition += cb_vShake * shakeWeight;

  // Phase 3: preserve the recovered world -> view -> clip ordering.
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
  clipPosition = cb_xViewToProjection._m03_m13_m23_m33
      * viewPosition.w + clipPosition;
  return clipPosition;
}

