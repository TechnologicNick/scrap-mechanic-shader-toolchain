#ifndef MAIN_PART_RIGID_UV_STEP_VERTEX_HLSL
#define MAIN_PART_RIGID_UV_STEP_VERTEX_HLSL

// Rigid explicit-LTW vertex forwarding normal, color, stepped UV, and screen.
struct MainPartRigidUvStepVertex
{
  float4 clipPosition;
  float3 viewPosition;
  float2 uv0;
  float3 normalView;
  float4 color;
  uint accentColor;
  float3 objectTangent;
  float3 screenUv;
};

MainPartRigidUvStepVertex EvaluateMainPartRigidUvStepVertex(
    float3 localPosition,
    float2 baseUv,
    float3 normalEncoded,
    float4 localToWorldRow0,
    float4 localToWorldRow1,
    float4 localToWorldRow2,
    uint4 packedInstance)
{
  MainPartRigidUvStepVertex result;

  // Phase 1: explicit local-to-world transform and instance shake.
  MainPartInstanceParameters instance = DecodeMainPartInstance(packedInstance);
  float4 homogeneousPosition = float4(localPosition, 1.0);
  float3 worldPosition = float3(
      dot(localToWorldRow0, homogeneousPosition),
      dot(localToWorldRow1, homogeneousPosition),
      dot(localToWorldRow2, homogeneousPosition));
  worldPosition += cb_vShake * instance.shakeWeight;

  // Phase 2: preserve the recovered world -> view -> clip ordering.
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

  // Phase 3: animate UV0 and transform the encoded normal.
  float3 localNormal = normalEncoded * 2.0 - 1.0;
  float3 normalView = MainPartTransformLocalDirectionToView(
      localNormal, localToWorldRow0, localToWorldRow1, localToWorldRow2);
  normalView = NormalizeMainPartDirection(normalView);
  float3 projected = clipPosition.xyz / clipPosition.w;
  projected = projected * float3(0.5, -0.5, 1.0)
      + float3(0.5, 0.5, 0.0);

  result.clipPosition = clipPosition;
  result.viewPosition = viewPosition.xyz;
  result.uv0 = EvaluateMainPartSteppedUv(baseUv);
  result.normalView = normalView;
  result.color = instance.color;
  result.screenUv = float3(cb_vRenderScale * projected.xy, projected.z);
  return result;
}

#endif // MAIN_PART_RIGID_UV_STEP_VERTEX_HLSL
