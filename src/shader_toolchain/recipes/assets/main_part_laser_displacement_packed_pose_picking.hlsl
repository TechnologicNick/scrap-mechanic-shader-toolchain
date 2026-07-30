#ifndef MAIN_PART_LASER_DISPLACEMENT_PACKED_POSE_PICKING_HLSL
#define MAIN_PART_LASER_DISPLACEMENT_PACKED_POSE_PICKING_HLSL

#include "main_part_laser_deformation_policy.hlsl"
#include "main_part_laser_packed_transform.hlsl"
#include "main_part_laser_displacement_color_policy.hlsl"
#include "main_part_laser_picking_color.hlsl"

struct MainPartPackedLaserVertex
{
  float4 clipPosition;
  float2 uv;
  float4 color;
};

MainPartPackedLaserVertex EvaluateMainPartPackedLaserVertex(
    float3 position, float2 uv, float3 normal,
    float3 morphPosition, float3 morphNormal,
    int4 packedTransform, uint4 instanceData)
{
  MainPartLaserDeformation deformation = EvaluateMainPartLaserDeformation(
      position, uv, normal, morphPosition, morphNormal, instanceData);
  MainPartLaserTransformedVertex transformed =
      EvaluateMainPartLaserPackedTransform(
          deformation.localPosition, uv, packedTransform, instanceData);
  float3 displacementColor = EvaluateMainPartLaserDisplacementColor(
      deformation.localPosition, deformation.proceduralPhase,
      deformation.animationPhase);
  MainPartPackedLaserVertex result;
  result.clipPosition = transformed.clipPosition;
  result.uv = transformed.uv;
  result.color = EvaluateMainPartLaserPickingColor(
      instanceData.y, deformation.pickingLane, displacementColor);
  return result;
}

#endif
