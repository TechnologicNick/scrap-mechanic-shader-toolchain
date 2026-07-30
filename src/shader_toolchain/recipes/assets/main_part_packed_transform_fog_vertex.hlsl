// Packed-transform extension for unposed fogged surface vertices.

struct MainPartPackedTransformFogSurfaceVertex
{
  float4 clipPosition;
  float3 viewPosition;
  float2 uv0;
  float3 normalView;
  float3 tangentView;
  float3 bitangentView;
  float4 color;
  float3 screenUv;
  float4 fogColor;
};

MainPartPackedTransformFogSurfaceVertex
EvaluateMainPartPackedTransformFogSurfaceVertex(
    float3 localPosition,
    float2 uv0,
    float3 normalEncoded,
    float4 tangentEncoded,
    int4 packedLocalToWorld,
    uint4 packedInstance)
{
  MainPartPackedTransformFogSurfaceVertex result;

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

  float3 worldPosition = worldAxisY.xyz * localPosition.y;
  worldPosition = worldAxisX.xyz * localPosition.x + worldPosition;
  worldPosition = worldAxisZ.xyz * localPosition.z + worldPosition;
  float3 quantizedTranslation = (float3)packedLocalToWorld.xyz * 0.125;
  worldPosition += MainPartTransformPackedPoint(
      quantizedTranslation, transformIndex);

  float shakeWeight = (float)(packedInstance.y >> 26u) / 63.0;
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
  clipPosition = cb_xViewToProjection._m03_m13_m23_m33
      * viewPosition.w + clipPosition;

  float3 axisZView = MainPartPackedHomogeneousToView(worldAxisZ);
  float3 axisXView = MainPartPackedHomogeneousToView(worldAxisX);
  float3 axisYView = MainPartPackedHomogeneousToView(worldAxisY);

  float3 localNormal = normalEncoded * 2.0 - 1.0;
  float3 normalView = axisYView * localNormal.y;
  normalView = axisXView * localNormal.x + normalView;
  normalView = axisZView * localNormal.z + normalView;
  normalView *= rsqrt(dot(normalView, normalView));

  float3 localTangent = tangentEncoded.xyz * 2.0 - 1.0;
  float3 tangentView = axisYView * localTangent.y;
  tangentView = axisXView * localTangent.x + tangentView;
  tangentView = axisZView * localTangent.z + tangentView;
  tangentView *= rsqrt(dot(tangentView, tangentView));

  float tangentSign = tangentEncoded.w != 0.0 ? 1.0 : -1.0;
  float3 localBitangent = cross(localNormal, localTangent) * tangentSign;
  float3 bitangentView = axisYView * localBitangent.y;
  bitangentView = axisXView * localBitangent.x + bitangentView;
  bitangentView = axisZView * localBitangent.z + bitangentView;
  bitangentView *= rsqrt(dot(bitangentView, bitangentView));

  float3 projected = clipPosition.xyz / clipPosition.w;
  projected = projected * float3(0.5, -0.5, 1.0)
      + float3(0.5, 0.5, 0.0);
  float viewDistance = sqrt(dot(viewPosition.xyz, viewPosition.xyz));

  result.clipPosition = clipPosition;
  result.viewPosition = viewPosition.xyz;
  result.uv0 = uv0;
  result.normalView = normalView;
  result.tangentView = tangentView;
  result.bitangentView = bitangentView;
  result.color = float4(
      (packedInstance.x >> 24u) & 255u,
      (packedInstance.x >> 16u) & 255u,
      (packedInstance.x >> 8u) & 255u,
      packedInstance.x & 255u) / 255.0;
  result.screenUv = float3(cb_vRenderScale * projected.xy, projected.z);
  result.fogColor = EvaluateMainPartVertexFog(viewDistance, worldPosition.z);
  return result;
}

