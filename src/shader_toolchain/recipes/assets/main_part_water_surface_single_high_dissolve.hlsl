#ifndef MAIN_PART_WATER_SURFACE_SINGLE_HIGH_DISSOLVE_HLSL
#define MAIN_PART_WATER_SURFACE_SINGLE_HIGH_DISSOLVE_HLSL

// High-quality normal-mapped dissolve water with the shared clustered backend.
// Register-state operations remain ordered to preserve DXBC contraction.

struct MainPartDissolveWaterForwardOutput
{
  float4 color;
  float4 gForward;
};

struct MainPartWaterDissolveBand
{
  float distance;
  float fade;
};

float3 SampleMainPartDissolveWaterAsg(float2 uv)
{
  return tAsg.SampleBias(LinearWrapWrap_s, uv, cb_fMipBias).ywx;
}

MainPartWaterDissolveBand EvaluateMainPartWaterDissolveBand(
    float2 uv, float cutoffOffset)
{
  float2 dissolveUv = uv * cb_dissolve.fScale
      + cb_dissolve.vScrollSpeed.xy * cb_fTime;
  float4 samples = tCutoff.Gather(LinearWrapWrap_s, dissolveUv);
  float2 pairMaximum = max(samples.xz, samples.yw);
  float threshold = max(pairMaximum.x, pairMaximum.y) - 0.125;
  float4 selected = samples > threshold;
  float selectedCount = dot(selected, float4(1,1,1,1));
  float selectedMean = dot(selected * samples, float4(1,1,1,1));
  selectedMean /= selectedCount;
  selectedMean = selectedCount != 0.0 ? selectedMean : 0.0;
  float phase = frac(cb_fTime * cb_dissolve.fLoopSpeed + cutoffOffset);
  phase = phase * cb_dissolve.fLoopLength - cb_dissolve.fLoopOffset;
  MainPartWaterDissolveBand result;
  result.distance = phase - selectedMean;
  result.fade = saturate(cb_dissolve.fRcpFade
      * (cb_dissolve.fLength - abs(result.distance)));
  result.fade = exp2(cb_dissolve.fFadePower * log2(result.fade));
  return result;
}

MainPartDissolveWaterForwardOutput EvaluateMainPartWaterSurfaceSingleHighDissolve(
    float3 v1, float2 v2, float2 w2, float3 v3, float3 v4, float3 v5,
    float4 v6, float3 v7, float4 v8, float v9, uint v10,
    float3 waterAsg, float dissolveFade)
{
  float4 partPositionState,animationTransformState,viewProjectionState,normalAndTangentState,materialCoordinateState,effectAnimationState,materialSampleState,profileMaterialState,clusterMaskState,lightIteratorState,lightGeometryState,attenuationAndCookieState,shadowState,reflectionAndRefractionState,directLightAccumulator;
  // Skinning, effects, and material lighting retain DXBC order.
  uint4 packedBitmask, integerDestination;
  float4 floatDestination;

  partPositionState.x = dot(-v1.xyz, -v1.xyz);
  partPositionState.x = rsqrt(partPositionState.x);
  partPositionState.xyz = -v1.xyz * partPositionState.xxx;
  animationTransformState.xyz = waterAsg;
  partPositionState.w = dissolveFade;
  animationTransformState.zw = tNor.SampleBias(LinearWrapWrap_s, v2.xy, cb_fMipBias).xy;
  animationTransformState.zw = animationTransformState.zw * float2(1.99215686,1.99215686) + float2(-1,-1);
  viewProjectionState.x = dot(animationTransformState.zw, animationTransformState.zw);
  viewProjectionState.x = 1 + -viewProjectionState.x;
  viewProjectionState.x = max(0, viewProjectionState.x);
  viewProjectionState.x = sqrt(viewProjectionState.x);
  viewProjectionState.yzw = v5.xyz * animationTransformState.www;
  viewProjectionState.yzw = v4.xyz * animationTransformState.zzz + viewProjectionState.yzw;
  viewProjectionState.xyz = v3.xyz * viewProjectionState.xxx + viewProjectionState.yzw;
  animationTransformState.z = dot(viewProjectionState.xyz, viewProjectionState.xyz);
  animationTransformState.z = rsqrt(animationTransformState.z);
  viewProjectionState.xyz = viewProjectionState.xyz * animationTransformState.zzz;
  viewProjectionState.xyz = v10.xxx ? viewProjectionState.xyz : -viewProjectionState.xyz;
  animationTransformState.z = dot(viewProjectionState.xyz, viewProjectionState.xyz);
  animationTransformState.z = rsqrt(animationTransformState.z);
  viewProjectionState.xyz = viewProjectionState.xyz * animationTransformState.zzz;
  animationTransformState.z = dot(viewProjectionState.xyz, cb_vDirectionalLightDirectionView.xyz);
  normalAndTangentState.x = animationTransformState.z * -0.5 + 0.5;
  normalAndTangentState.y = dot(viewProjectionState.xyz, partPositionState.xyz);
  animationTransformState.zw = max(float2(0.00999999978,0.00999999978), normalAndTangentState.xy);
  animationTransformState.zw = min(float2(0.99000001,0.99000001), animationTransformState.zw);
  normalAndTangentState.xyzw = tDif.SampleBias(LinearWrapWrap_s, animationTransformState.zw, cb_fMipBias).xyzw;
  normalAndTangentState.xyz = -v6.xyz + normalAndTangentState.xyz;
  normalAndTangentState.xyz = normalAndTangentState.www * normalAndTangentState.xyz + v6.xyz;
  materialCoordinateState.xyz = cb_dissolve.vEndColor.xyz + -cb_dissolve.vStartColor.xyz;
  materialCoordinateState.xyz = partPositionState.www * materialCoordinateState.xyz + cb_dissolve.vStartColor.xyz;
  normalAndTangentState.xyz = -materialCoordinateState.xyz + normalAndTangentState.xyz;
  normalAndTangentState.xyz = partPositionState.www * normalAndTangentState.xyz + materialCoordinateState.xyz;
  partPositionState.w = dot(-cb_vDirectionalLightDirectionView.xyz, -cb_vDirectionalLightDirectionView.xyz);
  partPositionState.w = rsqrt(partPositionState.w);
  animationTransformState.zw = float2(1,1) + -animationTransformState.xy;
  viewProjectionState.w = -animationTransformState.z * animationTransformState.z + 1;
  materialCoordinateState.xyz = -cb_vDirectionalLightDirectionView.xyz * partPositionState.www + partPositionState.xyz;
  partPositionState.w = dot(materialCoordinateState.xyz, materialCoordinateState.xyz);
  partPositionState.w = rsqrt(partPositionState.w);
  materialCoordinateState.xyz = materialCoordinateState.xyz * partPositionState.www;
  partPositionState.w = dot(materialCoordinateState.xyz, viewProjectionState.xyz);
  partPositionState.w = partPositionState.w * 0.5 + 0.5;
  normalAndTangentState.w = dot(viewProjectionState.xyz, partPositionState.xyz);
  materialCoordinateState.x = max(0.00999999978, normalAndTangentState.w);
  animationTransformState.x = 4 * animationTransformState.x;
  animationTransformState.x = max(0.100000001, animationTransformState.x);
  materialCoordinateState.x = log2(materialCoordinateState.x);
  animationTransformState.x = materialCoordinateState.x * animationTransformState.x;
  animationTransformState.x = exp2(animationTransformState.x);
  animationTransformState.x = min(1, animationTransformState.x);
  animationTransformState.x = 1 + -animationTransformState.x;
  animationTransformState.x = max(0.25, animationTransformState.x);
  animationTransformState.x = min(0.800000012, animationTransformState.x);
  materialCoordinateState.x = 0.995000005 * viewProjectionState.w;
  materialCoordinateState.y = -viewProjectionState.w * 0.995000005 + 1;
  partPositionState.w = abs(partPositionState.w) * abs(partPositionState.w) + -materialCoordinateState.x;
  materialCoordinateState.x = 1 / materialCoordinateState.y;
  partPositionState.w = saturate(materialCoordinateState.x * partPositionState.w);
  materialCoordinateState.x = partPositionState.w * -2 + 3;
  partPositionState.w = partPositionState.w * partPositionState.w;
  partPositionState.w = materialCoordinateState.x * partPositionState.w;
  partPositionState.w = saturate(partPositionState.w * viewProjectionState.w);
  animationTransformState.x = animationTransformState.x * animationTransformState.y + partPositionState.w;
  animationTransformState.x = saturate(animationTransformState.w * 0.25 + animationTransformState.x);
  animationTransformState.w = dot(-partPositionState.xyz, viewProjectionState.xyz);
  animationTransformState.w = animationTransformState.w + animationTransformState.w;
  materialCoordinateState.xyz = viewProjectionState.xyz * -animationTransformState.www + -partPositionState.xyz;
  effectAnimationState.xyz = viewToWorld._m01_m11_m21 * materialCoordinateState.yyy;
  materialCoordinateState.xyw = viewToWorld._m00_m10_m20 * materialCoordinateState.xxx + effectAnimationState.xyz;
  materialCoordinateState.xyz = viewToWorld._m02_m12_m22 * materialCoordinateState.zzz + materialCoordinateState.xyw;
  partPositionState.z = max(0.00999999978, animationTransformState.z);
  partPositionState.z = rsqrt(partPositionState.z);
  partPositionState.z = 1 / partPositionState.z;
  partPositionState.z = 5 * partPositionState.z;
  animationTransformState.z = abs(materialCoordinateState.x) + abs(materialCoordinateState.y);
  animationTransformState.z = animationTransformState.z + abs(materialCoordinateState.z);
  animationTransformState.z = max(9.99999975e-05, animationTransformState.z);
  animationTransformState.z = rcp(animationTransformState.z);
  animationTransformState.zw = materialCoordinateState.xy * animationTransformState.zz;
  materialCoordinateState.xy = float2(1,1) + -abs(animationTransformState.wz);
  effectAnimationState.xy = cmp(animationTransformState.zw < float2(0,0));
  materialCoordinateState.xy = effectAnimationState.xy ? -materialCoordinateState.xy : materialCoordinateState.xy;
  viewProjectionState.w = cmp(0 >= materialCoordinateState.z);
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
  clusterMaskState.xyz = effectAnimationState.xyz * normalAndTangentState.xyz;
  normalAndTangentState.xyz = -normalAndTangentState.xyz * effectAnimationState.xyz + materialCoordinateState.xyz;
  animationTransformState.yzw = animationTransformState.yyy * normalAndTangentState.xyz + clusterMaskState.xyz;
  animationTransformState.yzw = effectAnimationState.xyz * partPositionState.www + animationTransformState.yzw;
  partPositionState.w = cmp(0.00100000005 < animationTransformState.x);
  if (partPositionState.w != 0) {
    partPositionState.w = -normalAndTangentState.w * normalAndTangentState.w + 1;
    partPositionState.w = -partPositionState.w * 0.565323055 + 1;
    partPositionState.w = sqrt(partPositionState.w);
    partPositionState.w = normalAndTangentState.w * -0.751879692 + -partPositionState.w;
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
  MainPartDissolveWaterForwardOutput result;
  result.color.xyz = v8.www * animationTransformState.xyz + partPositionState.xyz;
  result.color.w = 1;
  result.gForward = float4(0,0,0,1);
  return result;
}

#endif // MAIN_PART_WATER_SURFACE_SINGLE_HIGH_DISSOLVE_HLSL
