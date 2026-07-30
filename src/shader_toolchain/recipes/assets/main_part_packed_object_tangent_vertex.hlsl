#ifndef MAIN_PART_PACKED_OBJECT_TANGENT_VERTEX_HLSL
#define MAIN_PART_PACKED_OBJECT_TANGENT_VERTEX_HLSL

#include "main_part_object_tangent_vertex.hlsl"

float3 EvaluateMainPartPackedObjectTangent(
    float3 normalView,
    int4 packedLocalToWorld,
    uint4 packedInstance)
{
  static const float3 objectAxes[6] =
  {
    float3( 0.00,  0.00, -0.25),
    float3( 0.00, -0.25,  0.00),
    float3(-0.25,  0.00,  0.00),
    float3( 0.25,  0.00,  0.00),
    float3( 0.00,  0.25,  0.00),
    float3( 0.00,  0.00,  0.25),
  };
  uint axisZIndex = ((uint)packedLocalToWorld.w >> 4u) & 15u;
  uint axisXIndex = (uint)packedLocalToWorld.w & 15u;
  float3 axisZ = objectAxes[axisZIndex];
  float3 axisX = objectAxes[axisXIndex];
  float3 axisY = cross(axisZ, axisX);
  axisY *= rsqrt(dot(axisY, axisY));
  axisY *= 0.25;
  uint transformIndex = packedInstance.y & 1023u;
  float4 axisXWorld = transformArray[transformIndex]._m01_m11_m21_m31
      * axisX.y;
  axisXWorld = transformArray[transformIndex]._m00_m10_m20_m30
      * axisX.x + axisXWorld;
  axisXWorld = transformArray[transformIndex]._m02_m12_m22_m32
      * axisX.z + axisXWorld;
  float4 axisYWorld = transformArray[transformIndex]._m01_m11_m21_m31
      * axisY.y;
  axisYWorld = transformArray[transformIndex]._m00_m10_m20_m30
      * axisY.x + axisYWorld;
  axisYWorld = transformArray[transformIndex]._m02_m12_m22_m32
      * axisY.z + axisYWorld;
  float3 axisXView = worldToView._m01_m11_m21 * axisXWorld.y;
  axisXView = worldToView._m00_m10_m20 * axisXWorld.x + axisXView;
  axisXView = worldToView._m02_m12_m22 * axisXWorld.z + axisXView;
  axisXView = worldToView._m03_m13_m23 * axisXWorld.w + axisXView;
  float3 axisYView = worldToView._m01_m11_m21 * axisYWorld.y;
  axisYView = worldToView._m00_m10_m20 * axisYWorld.x + axisYView;
  axisYView = worldToView._m02_m12_m22 * axisYWorld.z + axisYView;
  axisYView = worldToView._m03_m13_m23 * axisYWorld.w + axisYView;
  return MainPartFinalizeObjectTangent(normalView, axisXView, axisYView);
}

#endif // MAIN_PART_PACKED_OBJECT_TANGENT_VERTEX_HLSL
