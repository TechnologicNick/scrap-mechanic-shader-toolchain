#ifndef MAIN_PART_LASER_PACKED_TRANSFORM_HLSL
#define MAIN_PART_LASER_PACKED_TRANSFORM_HLSL
struct MainPartLaserTransformedVertex { float4 clipPosition; float2 uv; };
MainPartLaserTransformedVertex EvaluateMainPartLaserPackedTransform(
    float3 localPosition, float2 sourceUv, int4 v5, uint4 v6)
{
  const float4 icb[] = { { 0, 0, -0.250000, 0},
                        { 0, -0.250000, 0, 0},
                        { -0.250000, 0, 0, 0},
                        { 0.250000, 0, 0, 0},
                        { 0, 0.250000, 0, 0},
                        { 0, 0, 0.250000, 0} };
  float4 partPositionState = 0, animationTransformState = 0;
  float4 viewProjectionState = 0, normalAndTangentState = 0;
  float4 materialCoordinateState = 0;
  uint4 packedBitmask = 0;
  float2 v1 = sourceUv;
  partPositionState.xzw = localPosition;
  float4 o0 = 0; float2 o1 = 0;
animationTransformState.z = (uint)v5.w >> 4;
  animationTransformState.z = (int)animationTransformState.z & 15;
  animationTransformState.w = (int)v5.w & 15;
  viewProjectionState.xyz = icb[animationTransformState.z+0].zxy * icb[animationTransformState.w+0].yzx;
  viewProjectionState.xyz = icb[animationTransformState.z+0].yzx * icb[animationTransformState.w+0].zxy + -viewProjectionState.xyz;
  viewProjectionState.w = dot(viewProjectionState.xyz, viewProjectionState.xyz);
  viewProjectionState.w = rsqrt(viewProjectionState.w);
  viewProjectionState.xyz = viewProjectionState.xyz * viewProjectionState.www;
  viewProjectionState.xyz = float3(0.25,0.25,0.25) * viewProjectionState.xyz;
  packedBitmask.w = ((~(-1 << 10)) << 2) & 0xffffffff;  viewProjectionState.w = (((uint)v6.y << 2) & packedBitmask.w) | ((uint)0 & ~packedBitmask.w);
  normalAndTangentState.yzw = transformArray[viewProjectionState.w/4]._m01_m11_m21 * viewProjectionState.yyy;
  normalAndTangentState.yzw = transformArray[viewProjectionState.w/4]._m00_m10_m20 * viewProjectionState.xxx + normalAndTangentState.yzw;
  viewProjectionState.xyz = transformArray[viewProjectionState.w/4]._m02_m12_m22 * viewProjectionState.zzz + normalAndTangentState.yzw;
  viewProjectionState.xyz = viewProjectionState.xyz * partPositionState.zzz;
  normalAndTangentState.yzw = icb[animationTransformState.w+0].yyy * transformArray[viewProjectionState.w/4]._m01_m11_m21;
  normalAndTangentState.yzw = transformArray[viewProjectionState.w/4]._m00_m10_m20 * icb[animationTransformState.w+0].xxx + normalAndTangentState.yzw;
  normalAndTangentState.yzw = transformArray[viewProjectionState.w/4]._m02_m12_m22 * icb[animationTransformState.w+0].zzz + normalAndTangentState.yzw;
  viewProjectionState.xyz = normalAndTangentState.yzw * partPositionState.xxx + viewProjectionState.xyz;
  normalAndTangentState.yzw = icb[animationTransformState.z+0].yyy * transformArray[viewProjectionState.w/4]._m01_m11_m21;
  normalAndTangentState.yzw = transformArray[viewProjectionState.w/4]._m00_m10_m20 * icb[animationTransformState.z+0].xxx + normalAndTangentState.yzw;
  normalAndTangentState.yzw = transformArray[viewProjectionState.w/4]._m02_m12_m22 * icb[animationTransformState.z+0].zzz + normalAndTangentState.yzw;
  viewProjectionState.xyz = normalAndTangentState.yzw * partPositionState.www + viewProjectionState.xyz;
  normalAndTangentState.yzw = (int3)v5.xyz;
  normalAndTangentState.yzw = float3(0.125,0.125,0.125) * normalAndTangentState.yzw;
  materialCoordinateState.xyz = transformArray[viewProjectionState.w/4]._m01_m11_m21 * normalAndTangentState.zzz;
  materialCoordinateState.xyz = transformArray[viewProjectionState.w/4]._m00_m10_m20 * normalAndTangentState.yyy + materialCoordinateState.xyz;
  normalAndTangentState.yzw = transformArray[viewProjectionState.w/4]._m02_m12_m22 * normalAndTangentState.www + materialCoordinateState.xyz;
  normalAndTangentState.yzw = transformArray[viewProjectionState.w/4]._m03_m13_m23 + normalAndTangentState.yzw;
  viewProjectionState.xyz = normalAndTangentState.yzw + viewProjectionState.xyz;
  animationTransformState.z = (uint)v6.y >> 26;
  animationTransformState.z = (uint)animationTransformState.z;
  animationTransformState.z = 0.0158730168 * animationTransformState.z;
  viewProjectionState.xyz = cb_vShake.xyz * animationTransformState.zzz + viewProjectionState.xyz;
  materialCoordinateState.xyzw = worldToView._m01_m11_m21_m31 * viewProjectionState.yyyy;
  materialCoordinateState.xyzw = worldToView._m00_m10_m20_m30 * viewProjectionState.xxxx + materialCoordinateState.xyzw;
  viewProjectionState.xyzw = worldToView._m02_m12_m22_m32 * viewProjectionState.zzzz + materialCoordinateState.xyzw;
  viewProjectionState.xyzw = worldToView._m03_m13_m23_m33 + viewProjectionState.xyzw;
  materialCoordinateState.xyzw = cb_xViewToProjection._m01_m11_m21_m31 * viewProjectionState.yyyy;
  materialCoordinateState.xyzw = cb_xViewToProjection._m00_m10_m20_m30 * viewProjectionState.xxxx + materialCoordinateState.xyzw;
  materialCoordinateState.xyzw = cb_xViewToProjection._m02_m12_m22_m32 * viewProjectionState.zzzz + materialCoordinateState.xyzw;
  o0.xyzw = cb_xViewToProjection._m03_m13_m23_m33 * viewProjectionState.wwww + materialCoordinateState.xyzw;
  o1.xy = v1.xy;

  MainPartLaserTransformedVertex result;
  result.clipPosition = o0;
  result.uv = o1;
  return result;
}
#endif

