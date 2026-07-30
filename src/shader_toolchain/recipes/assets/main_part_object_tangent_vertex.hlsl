#ifndef MAIN_PART_OBJECT_TANGENT_VERTEX_HLSL
#define MAIN_PART_OBJECT_TANGENT_VERTEX_HLSL

float3 MainPartFinalizeObjectTangent(
    float3 normalView, float3 axisXView, float3 axisYView)
{
  axisXView *= rsqrt(dot(axisXView, axisXView));
  axisYView *= rsqrt(dot(axisYView, axisYView));
  float alignment = dot(normalView, axisYView);
  float3 objectTangent = axisYView
      + abs(alignment) * (axisXView - axisYView);
  return objectTangent * rsqrt(dot(objectTangent, objectTangent));
}

float3 EvaluateMainPartExplicitObjectTangent(
    float3 normalView,
    float4 localToWorldRow0,
    float4 localToWorldRow1,
    float4 localToWorldRow2)
{
  float3 axisXWorld = float3(
      localToWorldRow0.x, localToWorldRow1.x, localToWorldRow2.x);
  float3 axisYWorld = float3(
      localToWorldRow0.y, localToWorldRow1.y, localToWorldRow2.y);
  float3 axisXView = worldToView._m01_m11_m21 * axisXWorld.y;
  axisXView = worldToView._m00_m10_m20 * axisXWorld.x + axisXView;
  axisXView = worldToView._m02_m12_m22 * axisXWorld.z + axisXView;
  float3 axisYView = worldToView._m01_m11_m21 * axisYWorld.y;
  axisYView = worldToView._m00_m10_m20 * axisYWorld.x + axisYView;
  axisYView = worldToView._m02_m12_m22 * axisYWorld.z + axisYView;
  return MainPartFinalizeObjectTangent(normalView, axisXView, axisYView);
}

#endif // MAIN_PART_OBJECT_TANGENT_VERTEX_HLSL
