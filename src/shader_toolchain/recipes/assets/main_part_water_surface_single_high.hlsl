#ifndef MAIN_PART_WATER_SURFACE_SINGLE_HIGH_HLSL
#define MAIN_PART_WATER_SURFACE_SINGLE_HIGH_HLSL

// High-quality FBDRF water frontend with the shared clustered backend.
// Register-state operations remain ordered to preserve DXBC contraction.

struct MainPartWaterForwardOutput
{
  float4 color;
  float4 gForward;
};

MainPartWaterForwardOutput EvaluateMainPartWaterSurfaceSingleHigh(
    float3 v1, float2 v2, float3 v3, float3 v4, float3 v5,
    float4 v6, float3 v7, float4 v8, uint v9)
{
  float4 partPositionState,animationTransformState,viewProjectionState,normalAndTangentState,materialCoordinateState,effectAnimationState,materialSampleState,profileMaterialState,clusterMaskState,lightIteratorState,lightGeometryState,attenuationAndCookieState,shadowState,reflectionAndRefractionState,directLightAccumulator;
  // Skinning, effects, and material lighting retain DXBC order.
  uint4 packedBitmask, integerDestination;
  float4 floatDestination;

  partPositionState.x = dot(-v1.xyz, -v1.xyz);
  partPositionState.x = rsqrt(partPositionState.x);
  partPositionState.xyz = -v1.xyz * partPositionState.xxx;
  animationTransformState.xy = tAsg.SampleBias(LinearWrapWrap_s, v2.xy, cb_fMipBias).yw;
  partPositionState.w = dot(v3.xyz, v3.xyz);
  partPositionState.w = rsqrt(partPositionState.w);
  viewProjectionState.xyz = v3.xyz * partPositionState.www;
  partPositionState.w = dot(viewProjectionState.xyz, cb_vDirectionalLightDirectionView.xyz);
  normalAndTangentState.x = partPositionState.w * -0.5 + 0.5;
  normalAndTangentState.y = dot(viewProjectionState.xyz, partPositionState.xyz);
  animationTransformState.zw = max(float2(0.00999999978,0.00999999978), normalAndTangentState.xy);
  normalAndTangentState.xz = min(float2(0.99000001,0.99000001), animationTransformState.zw);
  materialCoordinateState.xyzw = tDif.SampleBias(LinearWrapWrap_s, normalAndTangentState.xz, cb_fMipBias).xyzw;
  normalAndTangentState.xzw = -v6.xyz + materialCoordinateState.xyz;
  normalAndTangentState.xzw = materialCoordinateState.www * normalAndTangentState.xzw + v6.xyz;
  partPositionState.w = dot(-cb_vDirectionalLightDirectionView.xyz, -cb_vDirectionalLightDirectionView.xyz);
  partPositionState.w = rsqrt(partPositionState.w);
  materialCoordinateState.xy = float2(1,1) + -animationTransformState.xy;
  animationTransformState.z = -materialCoordinateState.x * materialCoordinateState.x + 1;
  effectAnimationState.xyz = -cb_vDirectionalLightDirectionView.xyz * partPositionState.www + partPositionState.xyz;
  partPositionState.w = dot(effectAnimationState.xyz, effectAnimationState.xyz);
  partPositionState.w = rsqrt(partPositionState.w);
  effectAnimationState.xyz = effectAnimationState.xyz * partPositionState.www;
  partPositionState.w = dot(effectAnimationState.xyz, viewProjectionState.xyz);
  partPositionState.w = partPositionState.w * 0.5 + 0.5;
  animationTransformState.x = 4 * animationTransformState.x;
  animationTransformState.x = max(0.100000001, animationTransformState.x);
  animationTransformState.w = log2(animationTransformState.w);
  animationTransformState.x = animationTransformState.x * animationTransformState.w;
  animationTransformState.x = exp2(animationTransformState.x);
  animationTransformState.x = min(1, animationTransformState.x);
  animationTransformState.x = 1 + -animationTransformState.x;
  animationTransformState.x = max(0.25, animationTransformState.x);
  animationTransformState.x = min(0.800000012, animationTransformState.x);
  animationTransformState.w = 0.995000005 * animationTransformState.z;
  viewProjectionState.w = -animationTransformState.z * 0.995000005 + 1;
  partPositionState.w = abs(partPositionState.w) * abs(partPositionState.w) + -animationTransformState.w;
  animationTransformState.w = 1 / viewProjectionState.w;
  partPositionState.w = saturate(animationTransformState.w * partPositionState.w);
  animationTransformState.w = partPositionState.w * -2 + 3;
  partPositionState.w = partPositionState.w * partPositionState.w;
  partPositionState.w = animationTransformState.w * partPositionState.w;
  partPositionState.w = saturate(partPositionState.w * animationTransformState.z);
  animationTransformState.x = animationTransformState.x * animationTransformState.y + partPositionState.w;
  animationTransformState.x = saturate(materialCoordinateState.y * 0.25 + animationTransformState.x);
  animationTransformState.z = dot(-partPositionState.xyz, viewProjectionState.xyz);
  animationTransformState.z = animationTransformState.z + animationTransformState.z;
  materialCoordinateState.yzw = viewProjectionState.xyz * -animationTransformState.zzz + -partPositionState.xyz;
  effectAnimationState.xyz = viewToWorld._m01_m11_m21 * materialCoordinateState.zzz;
  effectAnimationState.xyz = viewToWorld._m00_m10_m20 * materialCoordinateState.yyy + effectAnimationState.xyz;
  materialCoordinateState.yzw = viewToWorld._m02_m12_m22 * materialCoordinateState.www + effectAnimationState.xyz;
  partPositionState.z = max(0.00999999978, materialCoordinateState.x);
  partPositionState.z = rsqrt(partPositionState.z);
  partPositionState.z = 1 / partPositionState.z;
  partPositionState.z = 5 * partPositionState.z;
  animationTransformState.z = abs(materialCoordinateState.y) + abs(materialCoordinateState.z);
  animationTransformState.z = animationTransformState.z + abs(materialCoordinateState.w);
  animationTransformState.z = max(9.99999975e-05, animationTransformState.z);
  animationTransformState.z = rcp(animationTransformState.z);
  animationTransformState.zw = materialCoordinateState.yz * animationTransformState.zz;
  materialCoordinateState.xy = float2(1,1) + -abs(animationTransformState.wz);
  effectAnimationState.xy = cmp(animationTransformState.zw < float2(0,0));
  materialCoordinateState.xy = effectAnimationState.xy ? -materialCoordinateState.xy : materialCoordinateState.xy;
  viewProjectionState.w = cmp(0 >= materialCoordinateState.w);
  MainPartWaterHighLightingInput lightingInput;
  lightingInput.viewPosition = v1;
  lightingInput.screenUv = v7.xy;
  lightingInput.normalView = viewProjectionState.xyz;
  lightingInput.foldedReflectionUv = materialCoordinateState.xy;
  lightingInput.unfoldedReflectionUv = animationTransformState.zw;
  lightingInput.reflectionHemisphere = viewProjectionState.w;
  lightingInput.reflectionMip = partPositionState.z;
  lightingInput.reflectionStrength = animationTransformState.y;
  MainPartWaterHighLighting lighting =
      EvaluateMainPartWaterHighLighting(lightingInput);
  effectAnimationState.xyz = lighting.directLight;
  materialCoordinateState.xyz = lighting.reflection;
  materialSampleState.xyz = lighting.indirectLight;
  profileMaterialState.xyz = lighting.weightedIndirectLight;
  partPositionState.z = lighting.indirectDistanceWeight;
  clusterMaskState.xyz = effectAnimationState.xyz * normalAndTangentState.xzw;
  normalAndTangentState.xzw = -normalAndTangentState.xzw * effectAnimationState.xyz + materialCoordinateState.xyz;
  animationTransformState.yzw = animationTransformState.yyy * normalAndTangentState.xzw + clusterMaskState.xyz;
  animationTransformState.yzw = effectAnimationState.xyz * partPositionState.www + animationTransformState.yzw;
  partPositionState.w = cmp(0.00100000005 < animationTransformState.x);
  if (partPositionState.w != 0) {
    partPositionState.w = -normalAndTangentState.y * normalAndTangentState.y + 1;
    partPositionState.w = -partPositionState.w * 0.565323055 + 1;
    partPositionState.w = sqrt(partPositionState.w);
    partPositionState.w = normalAndTangentState.y * -0.751879692 + -partPositionState.w;
    viewProjectionState.xy = partPositionState.ww * viewProjectionState.xy;
    partPositionState.xy = partPositionState.xy * float2(0.751879692,0.751879692) + viewProjectionState.xy;
    partPositionState.w = 0.100000001 * cb_fProjectionScale;
    viewProjectionState.x = max(9.99999997e-07, -v1.z);
    partPositionState.w = partPositionState.w / viewProjectionState.x;
    partPositionState.xy = partPositionState.xy * partPositionState.ww;
    partPositionState.xy = cb_vContainerPixelSize.xy * partPositionState.xy;
    partPositionState.xy = partPositionState.xy * cb_vRenderScale.xy + v7.xy;
    partPositionState.xyw = tFrame.Sample(LinearClampClamp_s, partPositionState.xy).xyz;
    viewProjectionState.xyz = animationTransformState.yzw + -partPositionState.xyw;
    animationTransformState.yzw = animationTransformState.xxx * viewProjectionState.xyz + partPositionState.xyw;
  }
  partPositionState.x = dot(profileMaterialState.xyz, float3(0.333333343,0.333333343,0.333333343));
  partPositionState.x = 3 * partPositionState.x;
  partPositionState.y = max(0.125, animationTransformState.x);
  partPositionState.x = partPositionState.x * partPositionState.y;
  partPositionState.yzw = materialSampleState.xyz * partPositionState.zzz + -animationTransformState.yzw;
  partPositionState.xyz = partPositionState.xxx * partPositionState.yzw + animationTransformState.yzw;
  animationTransformState.xyz = v8.xyz + -partPositionState.xyz;
  MainPartWaterForwardOutput result;
  result.color.xyz = v8.www * animationTransformState.xyz + partPositionState.xyz;
  result.color.w = 1;
  result.gForward = float4(0,0,0,1);
  return result;
}

#endif // MAIN_PART_WATER_SURFACE_SINGLE_HIGH_HLSL
