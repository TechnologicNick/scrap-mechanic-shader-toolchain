#ifndef MAIN_PART_RIGID_NORMAL_VERTEX_HLSL
#define MAIN_PART_RIGID_NORMAL_VERTEX_HLSL

// Explicit-LTW rigid vertex for permutations that do not request tangents.
struct MainPartRigidNormalVertex
{
  float4 clipPosition;
  float3 viewPosition;
  float2 uv0;
  float occlusion;
  float3 normalView;
  float4 color;
  uint accentColor;
  float3 objectTangent;
  float3 screenUv;
  float3 worldPosition;
  float4 fogColor;
  float4 planeViewPosition;
  float cutoff;
};

MainPartRigidNormalVertex EvaluateMainPartRigidNormalVertex(
    float3 localPosition,
    float2 uv0,
    float3 normalEncoded,
    float4 localToWorldRow0,
    float4 localToWorldRow1,
    float4 localToWorldRow2,
    uint4 packedInstance)
{
  MainPartRigidNormalVertex result;
  MainPartInstanceParameters instance = DecodeMainPartInstance(packedInstance);
  float4 homogeneousPosition = float4(localPosition, 1.0);
  float3 worldPosition = float3(
      dot(localToWorldRow0, homogeneousPosition),
      dot(localToWorldRow1, homogeneousPosition),
      dot(localToWorldRow2, homogeneousPosition));
  worldPosition += cb_vShake * instance.shakeWeight;

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

  float3 localNormal = normalEncoded * 2.0 - 1.0;
  float3 projected = clipPosition.xyz / clipPosition.w;
  projected = projected * float3(0.5, -0.5, 1.0)
      + float3(0.5, 0.5, 0.0);
  float viewDistance = sqrt(dot(viewPosition.xyz, viewPosition.xyz));
  float3 planeWorldPosition = float3(
      localToWorldRow0.w, localToWorldRow1.w, localToWorldRow2.w);
  float3 planeViewPosition = worldToView._m01_m11_m21
      * planeWorldPosition.y;
  planeViewPosition = worldToView._m00_m10_m20
      * planeWorldPosition.x + planeViewPosition;
  planeViewPosition = worldToView._m02_m12_m22
      * planeWorldPosition.z + planeViewPosition;
  planeViewPosition += worldToView._m03_m13_m23;

  result.clipPosition = clipPosition;
  result.viewPosition = viewPosition.xyz;
  result.uv0 = uv0;
  result.normalView = NormalizeMainPartDirection(
      MainPartTransformLocalDirectionToView(
          localNormal, localToWorldRow0, localToWorldRow1, localToWorldRow2));
  result.color = instance.color;
  result.screenUv = float3(cb_vRenderScale * projected.xy, projected.z);
  result.worldPosition = worldPosition;
  result.fogColor = EvaluateMainPartVertexFog(viewDistance, worldPosition.z);
  result.planeViewPosition = float4(planeViewPosition, 0.0);
  result.cutoff = (float)(packedInstance.w & 65535u) / 65535.0;
  return result;
}

#endif // MAIN_PART_RIGID_NORMAL_VERTEX_HLSL
