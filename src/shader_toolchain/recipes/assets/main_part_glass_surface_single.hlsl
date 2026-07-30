// Shared instruction-ordered body for single-reflection tinted glass surfaces.
//
// Semantic phases:
// 1. Decode the two-sided tangent-space normal and tinted diffuse material.
// 2. Evaluate directional transmission and specular response.
// 3. Sample the single environment reflection with octahedral addressing.
// 4. Composite frame refraction, fog, opacity, and transparency metadata.
//
// This remains a body include so FXC preserves the original temporary
// lifetimes while related glass permutations are factored around it.

#define cmp -

  float4 partPositionState,animationTransformState,viewProjectionState,normalAndTangentState,materialCoordinateState,effectAnimationState,materialSampleState;
  // Skinning, effects, and material lighting retain DXBC order.
  uint4 packedBitmask, integerDestination;
  float4 floatDestination;

  partPositionState.x = dot(-v1.xyz, -v1.xyz);
  partPositionState.x = rsqrt(partPositionState.x);
  partPositionState.yzw = -v1.xyz * partPositionState.xxx;
  animationTransformState.xyz = tAsg.SampleBias(LinearWrapWrap_s, v2.xy, cb_fMipBias).yzw;
  animationTransformState.y = v6.w * animationTransformState.y;
  viewProjectionState.xy = tNor.SampleBias(LinearWrapWrap_s, v2.xy, cb_fMipBias).xy;
  viewProjectionState.xy = viewProjectionState.xy * float2(1.99215686,1.99215686) + float2(-1,-1);
  animationTransformState.w = dot(viewProjectionState.xy, viewProjectionState.xy);
  animationTransformState.w = 1 + -animationTransformState.w;
  animationTransformState.w = max(0, animationTransformState.w);
  animationTransformState.w = sqrt(animationTransformState.w);
  viewProjectionState.yzw = v5.xyz * viewProjectionState.yyy;
  viewProjectionState.xyz = v4.xyz * viewProjectionState.xxx + viewProjectionState.yzw;
  viewProjectionState.xyz = v3.xyz * animationTransformState.www + viewProjectionState.xyz;
  animationTransformState.w = dot(viewProjectionState.xyz, viewProjectionState.xyz);
  animationTransformState.w = rsqrt(animationTransformState.w);
  viewProjectionState.xyz = viewProjectionState.xyz * animationTransformState.www;
  viewProjectionState.xyz = v9.xxx ? viewProjectionState.xyz : -viewProjectionState.xyz;
  animationTransformState.w = dot(viewProjectionState.xyz, viewProjectionState.xyz);
  animationTransformState.w = rsqrt(animationTransformState.w);
  viewProjectionState.xyz = viewProjectionState.xyz * animationTransformState.www;
  normalAndTangentState.xyzw = tDif.SampleBias(LinearWrapWrap_s, v2.xy, cb_fMipBias).xyzw;
  normalAndTangentState.xyz = -v6.xyz + normalAndTangentState.xyz;
  normalAndTangentState.xyz = normalAndTangentState.www * normalAndTangentState.xyz + v6.xyz;
  animationTransformState.w = dot(v1.xyz, v1.xyz);
  animationTransformState.w = sqrt(animationTransformState.w);
  viewProjectionState.w = 1 + -animationTransformState.x;
  normalAndTangentState.w = cmp(0 != cb_fDirectionalLightIntensity);
  if (normalAndTangentState.w != 0) {
    normalAndTangentState.w = animationTransformState.x * animationTransformState.x;
    materialCoordinateState.x = dot(animationTransformState.zz, animationTransformState.xx);
    normalAndTangentState.w = normalAndTangentState.w * 750 + 35;
    materialCoordinateState.y = dot(viewProjectionState.xyz, -cb_vDirectionalLightDirectionView.xyz);
    materialCoordinateState.z = materialCoordinateState.y * 0.5 + 0.5;
    materialCoordinateState.y = max(0, materialCoordinateState.y);
    materialCoordinateState.y = materialCoordinateState.y * cb_glass.fTransmissionRange + cb_glass.fTransmissionBase;
    materialCoordinateState.w = 0.00400000019 * animationTransformState.w;
    materialCoordinateState.yw = min(float2(1,1), materialCoordinateState.yw);
    materialCoordinateState.w = 1 + -materialCoordinateState.w;
    materialCoordinateState.w = materialCoordinateState.w * materialCoordinateState.w;
    materialCoordinateState.w = materialCoordinateState.w * 0.200000018 + 0.400000006;
    effectAnimationState.xy = float2(1,1.20000005) + -materialCoordinateState.ww;
    effectAnimationState.z = saturate(materialCoordinateState.z + -materialCoordinateState.w);
    effectAnimationState.x = effectAnimationState.z / effectAnimationState.x;
    effectAnimationState.x = effectAnimationState.x * effectAnimationState.x;
    materialCoordinateState.w = effectAnimationState.x * effectAnimationState.y + materialCoordinateState.w;
    effectAnimationState.y = saturate(materialCoordinateState.z);
    effectAnimationState.x = cb_fTimeOfDay;
    effectAnimationState.xyz = tLightColorMap.SampleLevel(LinearWrapClamp_s, effectAnimationState.xy, 0).xyz;
    effectAnimationState.xyz = -cb_vDirectionalShadowColor.xyz + effectAnimationState.xyz;
    effectAnimationState.xyz = materialCoordinateState.zzz * effectAnimationState.xyz + cb_vDirectionalShadowColor.xyz;
    materialCoordinateState.z = cb_fDirectionalLightMapMul * materialCoordinateState.w;
    effectAnimationState.xyz = effectAnimationState.xyz * materialCoordinateState.zzz;
    effectAnimationState.xyz = cb_fDirectionalLightIntensity * effectAnimationState.xyz;
    materialSampleState.xyz = -v1.xyz * partPositionState.xxx + -cb_vDirectionalLightDirectionView.xyz;
    partPositionState.x = dot(materialSampleState.xyz, materialSampleState.xyz);
    partPositionState.x = rsqrt(partPositionState.x);
    materialSampleState.xyz = materialSampleState.xyz * partPositionState.xxx;
    partPositionState.x = dot(materialSampleState.xyz, viewProjectionState.xyz);
    partPositionState.x = partPositionState.x * 0.5 + 0.5;
    partPositionState.x = log2(abs(partPositionState.x));
    partPositionState.x = normalAndTangentState.w * partPositionState.x;
    partPositionState.x = exp2(partPositionState.x);
    partPositionState.x = partPositionState.x * materialCoordinateState.y;
    partPositionState.x = saturate(partPositionState.x * materialCoordinateState.x);
  } else {
    effectAnimationState.xyz = float3(0,0,0);
    partPositionState.x = 0;
  }
  normalAndTangentState.w = dot(-partPositionState.yzw, viewProjectionState.xyz);
  normalAndTangentState.w = normalAndTangentState.w + normalAndTangentState.w;
  materialCoordinateState.xyz = viewProjectionState.xyz * -normalAndTangentState.www + -partPositionState.yzw;
  materialSampleState.xyz = viewToWorld._m01_m11_m21 * materialCoordinateState.yyy;
  materialCoordinateState.xyw = viewToWorld._m00_m10_m20 * materialCoordinateState.xxx + materialSampleState.xyz;
  materialCoordinateState.xyz = viewToWorld._m02_m12_m22 * materialCoordinateState.zzz + materialCoordinateState.xyw;
  viewProjectionState.w = max(0.00999999978, viewProjectionState.w);
  viewProjectionState.w = rsqrt(viewProjectionState.w);
  viewProjectionState.w = 1 / viewProjectionState.w;
  viewProjectionState.w = 5 * viewProjectionState.w;
  normalAndTangentState.w = abs(materialCoordinateState.x) + abs(materialCoordinateState.y);
  normalAndTangentState.w = normalAndTangentState.w + abs(materialCoordinateState.z);
  normalAndTangentState.w = max(9.99999975e-05, normalAndTangentState.w);
  normalAndTangentState.w = rcp(normalAndTangentState.w);
  materialCoordinateState.xy = materialCoordinateState.xy * normalAndTangentState.ww;
  materialSampleState.xy = float2(1,1) + -abs(materialCoordinateState.yx);
  materialSampleState.zw = cmp(materialCoordinateState.xy < float2(0,0));
  materialSampleState.xy = materialSampleState.zw ? -materialSampleState.xy : materialSampleState.xy;
  normalAndTangentState.w = cmp(0 >= materialCoordinateState.z);
  materialCoordinateState.xy = normalAndTangentState.ww ? materialSampleState.xy : materialCoordinateState.xy;
  materialCoordinateState.xy = float2(-2,2) + materialCoordinateState.xy;
  normalAndTangentState.w = max(abs(materialCoordinateState.x), abs(materialCoordinateState.y));
  normalAndTangentState.w = cmp(normalAndTangentState.w >= 1);
  materialCoordinateState.xy = normalAndTangentState.ww ? -materialCoordinateState.xy : materialCoordinateState.xy;
  materialCoordinateState.xy = materialCoordinateState.xy * float2(0.5,0.5) + float2(0.5,0.5);
  materialCoordinateState.z = 0;
  materialCoordinateState.xyz = taReflection.SampleLevel(LinearMirrorMirror_s, materialCoordinateState.xyz, viewProjectionState.w).xyz;
  materialCoordinateState.xyz = materialCoordinateState.xyz * animationTransformState.zzz;
  materialSampleState.xyz = float3(1,1,1) + -effectAnimationState.xyz;
  effectAnimationState.xyz = animationTransformState.yyy * materialSampleState.xyz + effectAnimationState.xyz;
  animationTransformState.y = 0.5 * animationTransformState.y;
  animationTransformState.y = min(0.5, animationTransformState.y);
  partPositionState.y = dot(partPositionState.yzw, viewProjectionState.xyz);
  partPositionState.z = animationTransformState.x * 0.5 + 0.00999999978;
  partPositionState.yw = float2(1,1) + -partPositionState.yz;
  animationTransformState.z = partPositionState.y * partPositionState.y;
  animationTransformState.z = animationTransformState.z * animationTransformState.z;
  partPositionState.y = animationTransformState.z * partPositionState.y;
  partPositionState.y = partPositionState.w * partPositionState.y + partPositionState.z;
  partPositionState.z = v9.x ? cb_glass.fTransparencyFront : cb_glass.fTransparencyBack;
  partPositionState.z = partPositionState.z + partPositionState.x;
  partPositionState.z = saturate(partPositionState.z + partPositionState.y);
  partPositionState.x = partPositionState.x + partPositionState.y;
  partPositionState.yw = min(cb_vRenderScale.xy, v7.xy);
  viewProjectionState.xy = -cb_vUvLimit.xy + v7.xy;
  viewProjectionState.xy = max(float2(0,0), viewProjectionState.xy);
  partPositionState.yw = -viewProjectionState.xy + partPositionState.yw;
  viewProjectionState.xyzw = tFrame.SampleLevel(LinearMirrorMirror_s, partPositionState.yw, 0).xyzw;
  normalAndTangentState.xyz = normalAndTangentState.xyz * viewProjectionState.xyz + -viewProjectionState.xyz;
  viewProjectionState.xyz = partPositionState.zzz * normalAndTangentState.xyz + viewProjectionState.xyz;
  partPositionState.xyw = effectAnimationState.xyz * partPositionState.xxx + viewProjectionState.xyz;
  partPositionState.xyw = materialCoordinateState.xyz * animationTransformState.xxx + partPositionState.xyw;
  normalAndTangentState.xy = float2(0.349999994,0.5) * animationTransformState.yy;
  animationTransformState.x = 0.00999999978 * animationTransformState.w;
  animationTransformState.x = min(1, animationTransformState.x);
  animationTransformState.x = 1 + -animationTransformState.x;
  animationTransformState.x = normalAndTangentState.x * animationTransformState.x;
  animationTransformState.y = max(abs(partPositionState.x), abs(partPositionState.y));
  animationTransformState.y = max(animationTransformState.y, abs(partPositionState.w));
  animationTransformState.x = -animationTransformState.x * animationTransformState.y + 1;
  animationTransformState.x = v8.w * animationTransformState.x;
  animationTransformState.yzw = v8.xyz + -partPositionState.xyw;
  o0.xyz = animationTransformState.xxx * animationTransformState.yzw + partPositionState.xyw;
  normalAndTangentState.w = max(viewProjectionState.w, partPositionState.z);
  o0.w = normalAndTangentState.w;
  normalAndTangentState.z = 0;
  o1.xyzw = normalAndTangentState.yzzw;
  return;
