#ifndef MAIN_PART_LASER_PICKING_COLOR_HLSL
#define MAIN_PART_LASER_PICKING_COLOR_HLSL
float4 EvaluateMainPartLaserPickingColor(
    uint instanceWord, float pickingLane, float3 displacementColor)
{
  float4 partPositionState = float4(displacementColor, 0);
  float4 animationTransformState = 0, viewProjectionState = 0;
  float4 normalAndTangentState = 0;
  normalAndTangentState.x = pickingLane;
  uint4 v6 = uint4(0, instanceWord, 0, 0);
  float4 o2 = 0;
if (8 == 0) partPositionState.w = 0; else if (8+2 < 32) {   partPositionState.w = (uint)v6.y << (32-(8 + 2)); partPositionState.w = (uint)partPositionState.w >> (32-8);  } else partPositionState.w = (uint)v6.y >> 2;
  animationTransformState.x = (uint)partPositionState.w << 2;
  animationTransformState.x = (int)-animationTransformState.x + (int)normalAndTangentState.x;
  animationTransformState.y = -(int)animationTransformState.x;
  viewProjectionState.xyz = cmp((uint3)animationTransformState.xxx < int3(1,2,3));
  animationTransformState.x = (int)animationTransformState.x + -3;
  normalAndTangentState.z = viewProjectionState.y ? 0 : animationTransformState.x;
  normalAndTangentState.y = viewProjectionState.y ? animationTransformState.y : 0;
  normalAndTangentState.w = cmp((int)viewProjectionState.z == 0);
  normalAndTangentState.x = viewProjectionState.x;
  animationTransformState.xyzw = normalAndTangentState.xyzw ? cb_arrPickingId[partPositionState.w].xyzw : 0;
  animationTransformState.xy = (int2)animationTransformState.yw | (int2)animationTransformState.xz;
  partPositionState.w = (int)animationTransformState.y | (int)animationTransformState.x;
  animationTransformState.x = (uint)partPositionState.w >> 24;
  animationTransformState.x = (uint)animationTransformState.x;
  animationTransformState.x = 0.00392156886 * animationTransformState.x;
  if (8 == 0) viewProjectionState.x = 0; else if (8+16 < 32) {   viewProjectionState.x = (uint)partPositionState.w << (32-(8 + 16)); viewProjectionState.x = (uint)viewProjectionState.x >> (32-8);  } else viewProjectionState.x = (uint)partPositionState.w >> 16;
  if (8 == 0) viewProjectionState.y = 0; else if (8+8 < 32) {   viewProjectionState.y = (uint)partPositionState.w << (32-(8 + 8)); viewProjectionState.y = (uint)viewProjectionState.y >> (32-8);  } else viewProjectionState.y = (uint)partPositionState.w >> 8;
  partPositionState.w = (int)partPositionState.w & 255;
  partPositionState.w = (uint)partPositionState.w;
  o2.w = 0.00392156886 * partPositionState.w;
  viewProjectionState.xy = (uint2)viewProjectionState.xy;
  animationTransformState.yz = float2(0.00392156886,0.00392156886) * viewProjectionState.xy;
  o2.xyz = animationTransformState.xyz + partPositionState.xyz;

  return o2;
}
#endif

