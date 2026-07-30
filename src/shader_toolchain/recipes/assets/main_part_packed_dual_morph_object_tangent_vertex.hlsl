// Packed-LTW vertex with two morph poses and a triplanar/object tangent.
//
// Reuses the canonical packed-axis and transform helpers.  The emitted
// OBJECT_TANGENT is the packed X/Y frame direction selected by the absolute
// projection of the morphed normal onto the packed Y axis.

struct MainPartPackedDualMorphObjectTangentVertex
{
  float4 clipPosition;
  float3 objectTangentView;
};

MainPartPackedDualMorphObjectTangentVertex
EvaluateMainPartPackedDualMorphObjectTangentVertex(
    float3 basePosition,
    float3 baseNormalEncoded,
    float3 pose0Position,
    float3 pose0NormalEncoded,
    float3 pose1Position,
    float3 pose1NormalEncoded,
    int4 packedLocalToWorld,
    uint4 packedInstance)
{
  MainPartPackedDualMorphObjectTangentVertex result;

  // Phase 1: decode the two independent 16-bit morph weights.
  float pose0Weight = (float)(packedInstance.z & 65535u)
      * (1.0 / 65535.0);
  float pose1Weight = (float)(packedInstance.z >> 16u)
      * (1.0 / 65535.0);
  float3 localPosition = basePosition
      + (pose0Position - basePosition) * pose0Weight
      + (pose1Position - basePosition) * pose1Weight;

  // Phase 2: reconstruct the quantized local frame and instance transform.
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
  float shakeWeight = (float)(packedInstance.y >> 26u) * (1.0 / 63.0);
  worldPosition += cb_vShake * shakeWeight;

  // Phase 3: world -> view -> clip projection.
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

  // Phase 4: morph the normal and select a stable packed object axis.
  float3 baseNormal = baseNormalEncoded * 2.0 - 1.0;
  float3 pose0Normal = pose0NormalEncoded * 2.0 - 1.0;
  float3 pose1Normal = pose1NormalEncoded * 2.0 - 1.0;
  float3 localNormal = baseNormal
      + (pose0Normal - baseNormal) * pose0Weight
      + (pose1Normal - baseNormal) * pose1Weight;
  float3 worldNormal = worldAxisY.xyz * localNormal.y;
  worldNormal = worldAxisX.xyz * localNormal.x + worldNormal;
  worldNormal = worldAxisZ.xyz * localNormal.z + worldNormal;

  float3 unitAxisY = worldAxisY.xyz
      * rsqrt(dot(worldAxisY.xyz, worldAxisY.xyz));
  float normalOnY = dot(worldNormal, unitAxisY);
  float3 unitAxisX = worldAxisX.xyz
      * rsqrt(dot(worldAxisX.xyz, worldAxisX.xyz));
  float3 objectTangentWorld = unitAxisY
      + abs(normalOnY) * (unitAxisX - unitAxisY);

  float3 objectTangentView = worldToView._m01_m11_m21
      * objectTangentWorld.y;
  objectTangentView = worldToView._m00_m10_m20
      * objectTangentWorld.x + objectTangentView;
  objectTangentView = worldToView._m02_m12_m22
      * objectTangentWorld.z + objectTangentView;
  objectTangentView *= rsqrt(dot(objectTangentView, objectTangentView));

  result.clipPosition = clipPosition;
  result.objectTangentView = objectTangentView;
  return result;
}

