// Shared instruction-ordered evaluator for legacy tinted glass behind passes.
//
// Semantic phases inside the recovered program:
// 1. Reject fragments in front of the opaque depth buffer.
// 2. Decode ASG, normal-map, vertex tint, and view direction.
// 3. Evaluate cascaded directional/cloud visibility and specular response.
// 4. Build legacy glass Fresnel/transparency and weighted OIT outputs.
//
// The cascade comparison gathers remain ordered until their common filter is
// validated independently across the high-quality glass permutation family.

#define cmp -

#ifndef MAIN_PART_GLASS_BEHIND_TRANSMISSION_RANGE
#define MAIN_PART_GLASS_BEHIND_TRANSMISSION_RANGE 0
#endif

#ifndef MAIN_PART_GLASS_BEHIND_EDGE_SCALE
#define MAIN_PART_GLASS_BEHIND_EDGE_SCALE 0.119999997
#endif

void EvaluateMainPartLegacyGlassBehind(
  float4 v0 : SV_Position0,
  float3 v1 : VIEW_POSITION0,
  float2 v2 : UV0,
  float3 v3 : NORMAL0,
  float3 v4 : TANGENT0,
  float3 v5 : BITANGENT0,
  float4 v6 : VERTEXCOLOR0,
  linear noperspective centroid float3 v7 : SCREEN_UV0,
  float4 v8 : FOG_COLOR0,
  uint v9 : SV_IsFrontFace0,
  out float3 o0 : SV_Target0,
  out float2 o1 : SV_Target1)
{
  const float4 icb[] = { { 1.000000, 0, 0, 0},
                              { 0, 1.000000, 0, 0},
                              { 0, 0, 1.000000, 0},
                              { 0, 0, 0, 1.000000} };
  float4 partPositionState,animationTransformState,viewProjectionState,normalAndTangentState,materialCoordinateState,effectAnimationState,materialSampleState,profileMaterialState,clusterMaskState,lightIteratorState,lightGeometryState,attenuationAndCookieState,shadowState,reflectionAndRefractionState;
  // Skinning, effects, and material lighting retain DXBC order.
  uint4 packedBitmask, integerDestination;
  float4 floatDestination;

  partPositionState.x = tDepth.SampleLevel(PointClampClamp_s, v7.xy, 0).x;
  partPositionState.x = cmp(v7.z < partPositionState.x);
  if (partPositionState.x != 0) discard;
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
  animationTransformState.w = cmp(0 != cb_fDirectionalLightIntensity);
  if (animationTransformState.w != 0) {
    materialCoordinateState.xyz = viewToWorld._m01_m11_m21 * v1.yyy;
    materialCoordinateState.xyz = viewToWorld._m00_m10_m20 * v1.xxx + materialCoordinateState.xyz;
    materialCoordinateState.xyz = viewToWorld._m02_m12_m22 * v1.zzz + materialCoordinateState.xyz;
    materialCoordinateState.xyz = viewToWorld._m03_m13_m23 + materialCoordinateState.xyz;
    animationTransformState.w = dot(v1.xyz, v1.xyz);
    animationTransformState.w = sqrt(animationTransformState.w);
    viewProjectionState.w = animationTransformState.x * animationTransformState.x;
    animationTransformState.z = dot(animationTransformState.zz, animationTransformState.xx);
    viewProjectionState.w = viewProjectionState.w * 750 + 35;
    normalAndTangentState.w = dot(viewProjectionState.xyz, -cb_vDirectionalLightDirectionView.xyz);
    materialCoordinateState.w = cmp(cb_fTransparentUseCascade != 0.000000);
    if (materialCoordinateState.w != 0) {
      effectAnimationState.xyz = cb_arrCascades[0]._m01_m11_m21 * materialCoordinateState.yyy;
      effectAnimationState.xyz = cb_arrCascades[0]._m00_m10_m20 * materialCoordinateState.xxx + effectAnimationState.xyz;
      effectAnimationState.xyz = cb_arrCascades[0]._m02_m12_m22 * materialCoordinateState.zzz + effectAnimationState.xyz;
      effectAnimationState.xyz = cb_arrCascades[0]._m03_m13_m23 + effectAnimationState.xyz;
      materialSampleState.xyz = float3(-0.5,-0.5,-0.5) + effectAnimationState.xyz;
      profileMaterialState.xyz = cmp(float3(0.5,0.5,0.5) >= abs(materialSampleState.xyz));
      materialCoordinateState.w = profileMaterialState.y ? profileMaterialState.x : 0;
      materialCoordinateState.w = profileMaterialState.z ? materialCoordinateState.w : 0;
      materialSampleState.z = materialCoordinateState.w ? 0 : 4;
      if (materialCoordinateState.w == 0) {
        profileMaterialState.xyz = cb_arrCascades[1]._m01_m11_m21 * materialCoordinateState.yyy;
        profileMaterialState.xyz = cb_arrCascades[1]._m00_m10_m20 * materialCoordinateState.xxx + profileMaterialState.xyz;
        profileMaterialState.xyz = cb_arrCascades[1]._m02_m12_m22 * materialCoordinateState.zzz + profileMaterialState.xyz;
        profileMaterialState.xyz = cb_arrCascades[1]._m03_m13_m23 + profileMaterialState.xyz;
        clusterMaskState.xyz = float3(-0.5,-0.5,-0.5) + profileMaterialState.xyz;
        clusterMaskState.xyz = abs(clusterMaskState.xyz);
        lightIteratorState.xyz = cmp(float3(0.5,0.5,0.5) >= clusterMaskState.xyz);
        materialCoordinateState.w = lightIteratorState.y ? lightIteratorState.x : 0;
        materialCoordinateState.w = lightIteratorState.z ? materialCoordinateState.w : 0;
        clusterMaskState.w = materialCoordinateState.w ? 1 : materialSampleState.z;
        lightIteratorState.xyz = cb_arrCascades[2]._m01_m11_m21 * materialCoordinateState.yyy;
        lightIteratorState.xyz = cb_arrCascades[2]._m00_m10_m20 * materialCoordinateState.xxx + lightIteratorState.xyz;
        lightIteratorState.xyz = cb_arrCascades[2]._m02_m12_m22 * materialCoordinateState.zzz + lightIteratorState.xyz;
        lightIteratorState.xyz = cb_arrCascades[2]._m03_m13_m23 + lightIteratorState.xyz;
        lightGeometryState.xyz = float3(-0.5,-0.5,-0.5) + lightIteratorState.xyz;
        lightGeometryState.xyz = abs(lightGeometryState.xyz);
        attenuationAndCookieState.xyz = cmp(float3(0.5,0.5,0.5) >= lightGeometryState.xyz);
        effectAnimationState.w = attenuationAndCookieState.y ? attenuationAndCookieState.x : 0;
        effectAnimationState.w = attenuationAndCookieState.z ? effectAnimationState.w : 0;
        lightGeometryState.w = effectAnimationState.w ? 2 : clusterMaskState.w;
        attenuationAndCookieState.xyz = cb_arrCascades[3]._m01_m11_m21 * materialCoordinateState.yyy;
        attenuationAndCookieState.xyz = cb_arrCascades[3]._m00_m10_m20 * materialCoordinateState.xxx + attenuationAndCookieState.xyz;
        attenuationAndCookieState.xyz = cb_arrCascades[3]._m02_m12_m22 * materialCoordinateState.zzz + attenuationAndCookieState.xyz;
        attenuationAndCookieState.xyz = cb_arrCascades[3]._m03_m13_m23 + attenuationAndCookieState.xyz;
        shadowState.xyz = float3(-0.5,-0.5,-0.5) + attenuationAndCookieState.xyz;
        shadowState.xyz = abs(shadowState.xyz);
        reflectionAndRefractionState.xyz = cmp(float3(1,1,1) >= shadowState.xyz);
        materialSampleState.w = reflectionAndRefractionState.y ? reflectionAndRefractionState.x : 0;
        materialSampleState.w = reflectionAndRefractionState.z ? materialSampleState.w : 0;
        shadowState.w = materialSampleState.w ? 3 : lightGeometryState.w;
        lightIteratorState.xyz = effectAnimationState.www ? lightIteratorState.xyz : attenuationAndCookieState.xyz;
        lightGeometryState.xyz = effectAnimationState.www ? lightGeometryState.xyw : shadowState.xyw;
        effectAnimationState.xyz = materialCoordinateState.www ? profileMaterialState.xyz : lightIteratorState.xyz;
        materialSampleState.xyz = materialCoordinateState.www ? clusterMaskState.xyw : lightGeometryState.xyz;
      } else {
        materialSampleState.xy = abs(materialSampleState.xy);
      }
      materialCoordinateState.w = cmp(3 >= (uint)materialSampleState.z);
      if (materialCoordinateState.w != 0) {
        materialCoordinateState.w = v1.z * cb_vInverseCameraRange.x + 1;
        profileMaterialState.z = (uint)materialSampleState.z;
        effectAnimationState.w = 1 + profileMaterialState.z;
        materialSampleState.x = max(materialSampleState.x, materialSampleState.y);
        materialSampleState.x = materialSampleState.x + materialSampleState.x;
        materialSampleState.y = dot(cb_vCascadeSplits.xyzw, icb[materialSampleState.z+0].xyzw);
        materialSampleState.y = -effectAnimationState.z * materialSampleState.y + 1;
        materialSampleState.x = max(materialSampleState.x, materialSampleState.y);
        materialSampleState.x = 1 + -materialSampleState.x;
        materialSampleState.y = profileMaterialState.z * 2 + 1;
        materialSampleState.y = materialSampleState.y * materialCoordinateState.w;
        effectAnimationState.z = materialSampleState.y * 5.99999985e-05 + effectAnimationState.z;
        effectAnimationState.xy = cb_vCascadeSize.yx * effectAnimationState.yx + float2(0.5,0.5);
        materialSampleState.yw = floor(effectAnimationState.yx);
        effectAnimationState.xy = -materialSampleState.wy + effectAnimationState.xy;
        profileMaterialState.xy = cb_vCascadePixelSize.xy * materialSampleState.yw;
        clusterMaskState.xyz = taCascades.GatherCmp(sShadowSamplerLinear_s, profileMaterialState.xyz, effectAnimationState.z, int2(-2,-2)).xyz;
        materialSampleState.yw = float2(1,1) + -effectAnimationState.xy;
        profileMaterialState.w = 0.5 * effectAnimationState.y;
        lightIteratorState.xyz = effectAnimationState.yyy * float3(-0.5,-0.5,0.5) + float3(0.5,1,0.5);
        clusterMaskState.yzw = lightIteratorState.xxy * clusterMaskState.zyy;
        lightGeometryState.xyzw = taCascades.GatherCmp(sShadowSamplerLinear_s, profileMaterialState.xyz, effectAnimationState.z, int2(0,-2)).xyzw;
        attenuationAndCookieState.xyzw = lightGeometryState.wzxy * lightIteratorState.yzyz;
        lightGeometryState.zw = attenuationAndCookieState.xz + attenuationAndCookieState.yw;
        lightIteratorState.w = lightGeometryState.z * materialSampleState.y;
        clusterMaskState.y = materialSampleState.y * clusterMaskState.y + lightIteratorState.w;
        lightIteratorState.w = lightGeometryState.w * effectAnimationState.x;
        clusterMaskState.z = effectAnimationState.x * clusterMaskState.z + lightIteratorState.w;
        attenuationAndCookieState.xyz = taCascades.GatherCmp(sShadowSamplerLinear_s, profileMaterialState.xyz, effectAnimationState.z, int2(2,-2)).xyw;
        lightGeometryState.zw = attenuationAndCookieState.zx * profileMaterialState.ww;
        clusterMaskState.y = materialSampleState.y * lightGeometryState.z + clusterMaskState.y;
        clusterMaskState.z = effectAnimationState.x * lightGeometryState.w + clusterMaskState.z;
        shadowState.xyzw = taCascades.GatherCmp(sShadowSamplerLinear_s, profileMaterialState.xyz, effectAnimationState.z, int2(-2,0)).xyzw;
        lightGeometryState.zw = shadowState.wx * materialSampleState.ww + shadowState.zy;
        materialSampleState.w = materialSampleState.y * lightGeometryState.z + clusterMaskState.y;
        clusterMaskState.y = effectAnimationState.x * lightGeometryState.w + clusterMaskState.z;
        clusterMaskState.z = -effectAnimationState.y * 0.5 + 0.5;
        clusterMaskState.x = clusterMaskState.x * clusterMaskState.z + clusterMaskState.w;
        lightGeometryState.zw = shadowState.zy * lightIteratorState.yy;
        lightGeometryState.zw = shadowState.wx * clusterMaskState.zz + lightGeometryState.zw;
        shadowState.xyzw = taCascades.GatherCmp(sShadowSamplerLinear_s, profileMaterialState.xyz, effectAnimationState.z).xyzw;
        attenuationAndCookieState.zw = shadowState.xw + shadowState.yz;
        materialSampleState.w = materialSampleState.y * attenuationAndCookieState.w + materialSampleState.w;
        clusterMaskState.w = attenuationAndCookieState.w * effectAnimationState.x;
        clusterMaskState.y = effectAnimationState.x * attenuationAndCookieState.z + clusterMaskState.y;
        lightIteratorState.w = lightGeometryState.x + lightGeometryState.y;
        lightIteratorState.w = lightIteratorState.w * materialSampleState.y;
        clusterMaskState.x = materialSampleState.y * clusterMaskState.x + lightIteratorState.w;
        clusterMaskState.w = effectAnimationState.x * lightGeometryState.z + clusterMaskState.w;
        shadowState.xyzw = taCascades.GatherCmp(sShadowSamplerLinear_s, profileMaterialState.xyz, effectAnimationState.z, int2(2,0)).xyzw;
        lightGeometryState.xy = shadowState.zy * effectAnimationState.yy;
        shadowState.yz = shadowState.zy * effectAnimationState.yy + shadowState.wx;
        materialSampleState.w = materialSampleState.y * shadowState.y + materialSampleState.w;
        clusterMaskState.y = effectAnimationState.x * shadowState.z + clusterMaskState.y;
        lightIteratorState.w = attenuationAndCookieState.y * effectAnimationState.y;
        lightIteratorState.w = 0.5 * lightIteratorState.w;
        lightIteratorState.w = attenuationAndCookieState.x * lightIteratorState.z + lightIteratorState.w;
        clusterMaskState.x = materialSampleState.y * lightIteratorState.w + clusterMaskState.x;
        lightGeometryState.xy = float2(0.5,0.5) * lightGeometryState.xy;
        lightGeometryState.xy = shadowState.wx * lightIteratorState.zz + lightGeometryState.xy;
        clusterMaskState.w = effectAnimationState.x * lightGeometryState.x + clusterMaskState.w;
        attenuationAndCookieState.xyw = taCascades.GatherCmp(sShadowSamplerLinear_s, profileMaterialState.xyz, effectAnimationState.z, int2(-2,2)).yzw;
        shadowState.xyz = attenuationAndCookieState.yxy * lightIteratorState.xxy;
        materialSampleState.w = materialSampleState.y * shadowState.x + materialSampleState.w;
        clusterMaskState.y = effectAnimationState.x * shadowState.y + clusterMaskState.y;
        clusterMaskState.x = materialSampleState.y * lightGeometryState.w + clusterMaskState.x;
        clusterMaskState.z = attenuationAndCookieState.w * clusterMaskState.z + shadowState.z;
        clusterMaskState.z = effectAnimationState.x * clusterMaskState.z + clusterMaskState.w;
        shadowState.xyzw = taCascades.GatherCmp(sShadowSamplerLinear_s, profileMaterialState.xyz, effectAnimationState.z, int2(0,2)).xyzw;
        reflectionAndRefractionState.xyzw = shadowState.wzxy * lightIteratorState.yzyz;
        lightIteratorState.xy = reflectionAndRefractionState.xz + reflectionAndRefractionState.yw;
        materialSampleState.w = materialSampleState.y * lightIteratorState.x + materialSampleState.w;
        clusterMaskState.y = effectAnimationState.x * lightIteratorState.y + clusterMaskState.y;
        clusterMaskState.x = materialSampleState.y * attenuationAndCookieState.z + clusterMaskState.x;
        clusterMaskState.w = shadowState.w + shadowState.z;
        clusterMaskState.z = effectAnimationState.x * clusterMaskState.w + clusterMaskState.z;
        profileMaterialState.xyz = taCascades.GatherCmp(sShadowSamplerLinear_s, profileMaterialState.xyz, effectAnimationState.z, int2(2,2)).xzw;
        profileMaterialState.xw = profileMaterialState.zx * profileMaterialState.ww;
        attenuationAndCookieState.x = materialSampleState.y * profileMaterialState.x + materialSampleState.w;
        attenuationAndCookieState.y = effectAnimationState.x * profileMaterialState.w + clusterMaskState.y;
        attenuationAndCookieState.z = materialSampleState.y * lightGeometryState.y + clusterMaskState.x;
        effectAnimationState.y = profileMaterialState.y * effectAnimationState.y;
        effectAnimationState.yw = float2(0.5,0.109999999) * effectAnimationState.yw;
        effectAnimationState.y = profileMaterialState.z * lightIteratorState.z + effectAnimationState.y;
        attenuationAndCookieState.w = effectAnimationState.x * effectAnimationState.y + clusterMaskState.z;
        effectAnimationState.x = dot(attenuationAndCookieState.xyzw, float4(1,1,1,1));
        effectAnimationState.y = 0.0588235296 * effectAnimationState.x;
        effectAnimationState.z = cmp(materialSampleState.x < effectAnimationState.w);
        if (effectAnimationState.z != 0) {
          effectAnimationState.z = saturate(materialSampleState.x / effectAnimationState.w);
          effectAnimationState.w = cmp((int)materialSampleState.z == 3);
          if (effectAnimationState.w != 0) {
            effectAnimationState.w = effectAnimationState.x * 0.0588235296 + -1;
            effectAnimationState.y = effectAnimationState.z * effectAnimationState.w + 1;
          } else {
            effectAnimationState.w = (uint)materialSampleState.z << 2;
            materialSampleState.xyw = cb_arrCascades[effectAnimationState.w]._m01_m11_m21 * materialCoordinateState.yyy;
            materialSampleState.xyw = cb_arrCascades[effectAnimationState.w]._m00_m10_m20 * materialCoordinateState.xxx + materialSampleState.xyw;
            materialSampleState.xyw = cb_arrCascades[effectAnimationState.w]._m02_m12_m22 * materialCoordinateState.zzz + materialSampleState.xyw;
            materialSampleState.xyw = cb_arrCascades[effectAnimationState.w]._m03_m13_m23 + materialSampleState.xyw;
            effectAnimationState.w = (int)materialSampleState.z + 1;
            profileMaterialState.z = (uint)effectAnimationState.w;
            effectAnimationState.w = profileMaterialState.z * 2 + 1;
            materialCoordinateState.w = effectAnimationState.w * materialCoordinateState.w;
            materialCoordinateState.w = materialCoordinateState.w * 5.99999985e-05 + materialSampleState.w;
            materialSampleState.xy = cb_vCascadeSize.yx * materialSampleState.yx + float2(0.5,0.5);
            materialSampleState.zw = floor(materialSampleState.yx);
            materialSampleState.xy = materialSampleState.xy + -materialSampleState.wz;
            profileMaterialState.xy = cb_vCascadePixelSize.xy * materialSampleState.zw;
            clusterMaskState.xyz = taCascades.GatherCmp(sShadowSamplerLinear_s, profileMaterialState.xyz, materialCoordinateState.w, int2(-2,-2)).xyz;
            materialSampleState.zw = float2(1,1) + -materialSampleState.xy;
            effectAnimationState.w = 0.5 * materialSampleState.y;
            lightIteratorState.xyz = materialSampleState.yyy * float3(-0.5,-0.5,0.5) + float3(0.5,1,0.5);
            clusterMaskState.yzw = lightIteratorState.xxy * clusterMaskState.zyy;
            lightGeometryState.xyzw = taCascades.GatherCmp(sShadowSamplerLinear_s, profileMaterialState.xyz, materialCoordinateState.w, int2(0,-2)).xyzw;
            attenuationAndCookieState.xyzw = lightGeometryState.wzxy * lightIteratorState.yzyz;
            lightGeometryState.zw = attenuationAndCookieState.xz + attenuationAndCookieState.yw;
            profileMaterialState.w = lightGeometryState.z * materialSampleState.z;
            profileMaterialState.w = materialSampleState.z * clusterMaskState.y + profileMaterialState.w;
            clusterMaskState.y = lightGeometryState.w * materialSampleState.x;
            clusterMaskState.y = materialSampleState.x * clusterMaskState.z + clusterMaskState.y;
            attenuationAndCookieState.xyz = taCascades.GatherCmp(sShadowSamplerLinear_s, profileMaterialState.xyz, materialCoordinateState.w, int2(2,-2)).xyw;
            lightGeometryState.zw = attenuationAndCookieState.zx * effectAnimationState.ww;
            profileMaterialState.w = materialSampleState.z * lightGeometryState.z + profileMaterialState.w;
            clusterMaskState.y = materialSampleState.x * lightGeometryState.w + clusterMaskState.y;
            shadowState.xyzw = taCascades.GatherCmp(sShadowSamplerLinear_s, profileMaterialState.xyz, materialCoordinateState.w, int2(-2,0)).xyzw;
            lightGeometryState.zw = shadowState.wx * materialSampleState.ww + shadowState.zy;
            materialSampleState.w = materialSampleState.z * lightGeometryState.z + profileMaterialState.w;
            profileMaterialState.w = materialSampleState.x * lightGeometryState.w + clusterMaskState.y;
            clusterMaskState.y = -materialSampleState.y * 0.5 + 0.5;
            clusterMaskState.x = clusterMaskState.x * clusterMaskState.y + clusterMaskState.w;
            clusterMaskState.zw = shadowState.zy * lightIteratorState.yy;
            clusterMaskState.zw = shadowState.wx * clusterMaskState.yy + clusterMaskState.zw;
            shadowState.xyzw = taCascades.GatherCmp(sShadowSamplerLinear_s, profileMaterialState.xyz, materialCoordinateState.w).xyzw;
            lightGeometryState.zw = shadowState.xw + shadowState.yz;
            materialSampleState.w = materialSampleState.z * lightGeometryState.w + materialSampleState.w;
            lightIteratorState.w = lightGeometryState.w * materialSampleState.x;
            profileMaterialState.w = materialSampleState.x * lightGeometryState.z + profileMaterialState.w;
            lightGeometryState.x = lightGeometryState.x + lightGeometryState.y;
            lightGeometryState.x = lightGeometryState.x * materialSampleState.z;
            clusterMaskState.x = materialSampleState.z * clusterMaskState.x + lightGeometryState.x;
            clusterMaskState.z = materialSampleState.x * clusterMaskState.z + lightIteratorState.w;
            shadowState.xyzw = taCascades.GatherCmp(sShadowSamplerLinear_s, profileMaterialState.xyz, materialCoordinateState.w, int2(2,0)).xyzw;
            lightGeometryState.xy = shadowState.zy * materialSampleState.yy;
            attenuationAndCookieState.zw = shadowState.zy * materialSampleState.yy + shadowState.wx;
            materialSampleState.w = materialSampleState.z * attenuationAndCookieState.z + materialSampleState.w;
            profileMaterialState.w = materialSampleState.x * attenuationAndCookieState.w + profileMaterialState.w;
            lightIteratorState.w = attenuationAndCookieState.y * materialSampleState.y;
            lightIteratorState.w = 0.5 * lightIteratorState.w;
            lightIteratorState.w = attenuationAndCookieState.x * lightIteratorState.z + lightIteratorState.w;
            clusterMaskState.x = materialSampleState.z * lightIteratorState.w + clusterMaskState.x;
            lightGeometryState.xy = float2(0.5,0.5) * lightGeometryState.xy;
            lightGeometryState.xy = shadowState.wx * lightIteratorState.zz + lightGeometryState.xy;
            clusterMaskState.z = materialSampleState.x * lightGeometryState.x + clusterMaskState.z;
            attenuationAndCookieState.xyz = taCascades.GatherCmp(sShadowSamplerLinear_s, profileMaterialState.xyz, materialCoordinateState.w, int2(-2,2)).yzw;
            attenuationAndCookieState.xyw = attenuationAndCookieState.yxy * lightIteratorState.xxy;
            materialSampleState.w = materialSampleState.z * attenuationAndCookieState.x + materialSampleState.w;
            profileMaterialState.w = materialSampleState.x * attenuationAndCookieState.y + profileMaterialState.w;
            clusterMaskState.x = materialSampleState.z * clusterMaskState.w + clusterMaskState.x;
            clusterMaskState.y = attenuationAndCookieState.z * clusterMaskState.y + attenuationAndCookieState.w;
            clusterMaskState.y = materialSampleState.x * clusterMaskState.y + clusterMaskState.z;
            attenuationAndCookieState.xyzw = taCascades.GatherCmp(sShadowSamplerLinear_s, profileMaterialState.xyz, materialCoordinateState.w, int2(0,2)).xyzw;
            shadowState.xyzw = attenuationAndCookieState.wzxy * lightIteratorState.yzyz;
            clusterMaskState.zw = shadowState.xz + shadowState.yw;
            materialSampleState.w = materialSampleState.z * clusterMaskState.z + materialSampleState.w;
            profileMaterialState.w = materialSampleState.x * clusterMaskState.w + profileMaterialState.w;
            clusterMaskState.x = materialSampleState.z * lightGeometryState.z + clusterMaskState.x;
            clusterMaskState.z = attenuationAndCookieState.w + attenuationAndCookieState.z;
            clusterMaskState.y = materialSampleState.x * clusterMaskState.z + clusterMaskState.y;
            profileMaterialState.xyz = taCascades.GatherCmp(sShadowSamplerLinear_s, profileMaterialState.xyz, materialCoordinateState.w, int2(2,2)).xzw;
            clusterMaskState.zw = profileMaterialState.zx * effectAnimationState.ww;
            attenuationAndCookieState.x = materialSampleState.z * clusterMaskState.z + materialSampleState.w;
            attenuationAndCookieState.y = materialSampleState.x * clusterMaskState.w + profileMaterialState.w;
            attenuationAndCookieState.z = materialSampleState.z * lightGeometryState.y + clusterMaskState.x;
            materialCoordinateState.w = profileMaterialState.y * materialSampleState.y;
            materialCoordinateState.w = 0.5 * materialCoordinateState.w;
            materialCoordinateState.w = profileMaterialState.z * lightIteratorState.z + materialCoordinateState.w;
            attenuationAndCookieState.w = materialSampleState.x * materialCoordinateState.w + clusterMaskState.y;
            materialCoordinateState.w = dot(attenuationAndCookieState.xyzw, float4(1,1,1,1));
            materialCoordinateState.w = 0.0588235296 * materialCoordinateState.w;
            effectAnimationState.x = effectAnimationState.x * 0.0588235296 + -materialCoordinateState.w;
            effectAnimationState.y = effectAnimationState.z * effectAnimationState.x + materialCoordinateState.w;
          }
        }
      } else {
        effectAnimationState.y = 1;
      }
      materialCoordinateState.w = 0.400000006 + abs(normalAndTangentState.w);
      materialCoordinateState.w = 1.66666663 * materialCoordinateState.w;
      materialCoordinateState.w = min(1, materialCoordinateState.w);
      effectAnimationState.x = materialCoordinateState.w * -2 + 3;
      materialCoordinateState.w = materialCoordinateState.w * materialCoordinateState.w;
      materialCoordinateState.w = effectAnimationState.x * materialCoordinateState.w;
      materialCoordinateState.w = effectAnimationState.y * materialCoordinateState.w;
    } else {
      materialCoordinateState.w = 1;
    }
    effectAnimationState.x = cmp(cb_clouds.fCloudShadowCoveragesInv < 1);
    if (effectAnimationState.x != 0) {
      effectAnimationState.xyz = -cb_clouds.vPlanetCenter.xyz + materialCoordinateState.xyz;
      materialCoordinateState.z = dot(effectAnimationState.xyz, -cb_vDirectionalLightDirectionWorld.xyz);
      effectAnimationState.x = dot(effectAnimationState.xyz, effectAnimationState.xyz);
      effectAnimationState.x = -cb_clouds.fAtmosphereRadiusSqr + effectAnimationState.x;
      effectAnimationState.x = materialCoordinateState.z * materialCoordinateState.z + -effectAnimationState.x;
      effectAnimationState.x = max(0, effectAnimationState.x);
      effectAnimationState.x = sqrt(effectAnimationState.x);
      effectAnimationState.y = effectAnimationState.x + -materialCoordinateState.z;
      materialCoordinateState.z = -effectAnimationState.x + -materialCoordinateState.z;
      materialCoordinateState.z = max(effectAnimationState.y, materialCoordinateState.z);
      effectAnimationState.xy = -cb_vDirectionalLightDirectionWorld.xy * materialCoordinateState.zz + cb_clouds.vRawScroll.xy;
      materialCoordinateState.xy = effectAnimationState.xy + materialCoordinateState.xy;
      materialCoordinateState.xy = float2(9.2307695e-05,9.2307695e-05) * materialCoordinateState.xy;
      materialCoordinateState.x = tCloudMap.SampleLevel(LinearWrapWrap_s, materialCoordinateState.xy, 0).x;
      materialCoordinateState.x = -cb_clouds.fCloudShadowCoveragesInv + materialCoordinateState.x;
      materialCoordinateState.x = 5.88235283 * materialCoordinateState.x;
      materialCoordinateState.x = min(1, materialCoordinateState.x);
      materialCoordinateState.x = 1 + -materialCoordinateState.x;
      materialCoordinateState.y = cmp(materialCoordinateState.x < 0.300000012);
      materialCoordinateState.z = -cb_clouds.fCloudCoveragesInv * cb_clouds.fCloudCoveragesInv + 1;
      effectAnimationState.x = 0.300000012 + -materialCoordinateState.x;
      materialCoordinateState.x = 1 / materialCoordinateState.x;
      materialCoordinateState.x = saturate(effectAnimationState.x * materialCoordinateState.x);
      materialCoordinateState.x = 1 + -materialCoordinateState.x;
      materialCoordinateState.x = materialCoordinateState.x * materialCoordinateState.x;
      materialCoordinateState.x = -materialCoordinateState.x * materialCoordinateState.x + 1;
      materialCoordinateState.x = min(materialCoordinateState.z, materialCoordinateState.x);
      materialCoordinateState.x = materialCoordinateState.y ? materialCoordinateState.x : 0;
    } else {
      materialCoordinateState.x = 0;
    }
    materialCoordinateState.x = saturate(materialCoordinateState.w + -materialCoordinateState.x);
    materialCoordinateState.y = normalAndTangentState.w * 0.5 + 0.5;
#if MAIN_PART_GLASS_BEHIND_TRANSMISSION_RANGE
    normalAndTangentState.w = max(0, normalAndTangentState.w);
    normalAndTangentState.w = normalAndTangentState.w * cb_glass.fTransmissionRange + cb_glass.fTransmissionBase;
    normalAndTangentState.w = min(normalAndTangentState.w, materialCoordinateState.x);
#else
    normalAndTangentState.w = min(materialCoordinateState.x, abs(normalAndTangentState.w));
#endif
    animationTransformState.w = 0.00400000019 * animationTransformState.w;
    animationTransformState.w = min(1, animationTransformState.w);
    animationTransformState.w = 1 + -animationTransformState.w;
    animationTransformState.w = animationTransformState.w * animationTransformState.w;
    animationTransformState.w = animationTransformState.w * 0.200000018 + 0.400000006;
    materialCoordinateState.zw = float2(1,1.20000005) + -animationTransformState.ww;
    effectAnimationState.x = saturate(materialCoordinateState.y + -animationTransformState.w);
    materialCoordinateState.z = effectAnimationState.x / materialCoordinateState.z;
    materialCoordinateState.z = materialCoordinateState.z * materialCoordinateState.z;
    animationTransformState.w = materialCoordinateState.z * materialCoordinateState.w + animationTransformState.w;
    effectAnimationState.y = saturate(materialCoordinateState.y);
    effectAnimationState.x = cb_fTimeOfDay;
    effectAnimationState.xyz = tLightColorMap.SampleLevel(LinearWrapClamp_s, effectAnimationState.xy, 0).xyz;
    materialCoordinateState.x = materialCoordinateState.x * materialCoordinateState.y;
    materialCoordinateState.yzw = -cb_vDirectionalShadowColor.xyz + effectAnimationState.xyz;
    materialCoordinateState.xyz = materialCoordinateState.xxx * materialCoordinateState.yzw + cb_vDirectionalShadowColor.xyz;
    animationTransformState.w = cb_fDirectionalLightMapMul * animationTransformState.w;
    materialCoordinateState.xyz = materialCoordinateState.xyz * animationTransformState.www;
    materialCoordinateState.xyz = cb_fDirectionalLightIntensity * materialCoordinateState.xyz;
    effectAnimationState.xyz = -v1.xyz * partPositionState.xxx + -cb_vDirectionalLightDirectionView.xyz;
    partPositionState.x = dot(effectAnimationState.xyz, effectAnimationState.xyz);
    partPositionState.x = rsqrt(partPositionState.x);
    effectAnimationState.xyz = effectAnimationState.xyz * partPositionState.xxx;
    partPositionState.x = dot(effectAnimationState.xyz, viewProjectionState.xyz);
    partPositionState.x = partPositionState.x * 0.5 + 0.5;
    partPositionState.x = log2(abs(partPositionState.x));
    partPositionState.x = viewProjectionState.w * partPositionState.x;
    partPositionState.x = exp2(partPositionState.x);
    partPositionState.x = partPositionState.x * normalAndTangentState.w;
    partPositionState.x = saturate(partPositionState.x * animationTransformState.z);
  } else {
    materialCoordinateState.xyz = float3(0,0,0);
    partPositionState.x = 0;
  }
  effectAnimationState.xyz = float3(1,1,1) + -materialCoordinateState.xyz;
  animationTransformState.yzw = animationTransformState.yyy * effectAnimationState.xyz + materialCoordinateState.xyz;
  partPositionState.y = dot(partPositionState.yzw, viewProjectionState.xyz);
  partPositionState.z = 0.119999997 * animationTransformState.x;
  partPositionState.w = animationTransformState.x * MAIN_PART_GLASS_BEHIND_EDGE_SCALE + 0.00999999978;
  animationTransformState.x = 1 + -partPositionState.w;
  partPositionState.y = 1 + -partPositionState.y;
  viewProjectionState.x = partPositionState.y * partPositionState.y;
  viewProjectionState.x = viewProjectionState.x * viewProjectionState.x;
  partPositionState.y = viewProjectionState.x * partPositionState.y;
  partPositionState.y = animationTransformState.x * partPositionState.y + partPositionState.w;
  partPositionState.w = v9.x ? cb_glass.fTransparencyFront : cb_glass.fTransparencyBack;
  partPositionState.w = partPositionState.w + partPositionState.x;
  partPositionState.w = saturate(partPositionState.w + partPositionState.y);
  partPositionState.x = partPositionState.x + partPositionState.y;
  viewProjectionState.xyz = normalAndTangentState.xyz * animationTransformState.yzw + partPositionState.zzz;
  partPositionState.xyz = animationTransformState.yzw * partPositionState.xxx + viewProjectionState.xyz;
  animationTransformState.xyz = normalAndTangentState.xxy + -normalAndTangentState.zyz;
  animationTransformState.x = abs(animationTransformState.x) + abs(animationTransformState.y);
  animationTransformState.x = animationTransformState.x + abs(animationTransformState.z);
  animationTransformState.x = v7.z + animationTransformState.x;
  animationTransformState.x = animationTransformState.x * partPositionState.w;
  o0.xyz = animationTransformState.xxx * partPositionState.xyz;
  o1.x = animationTransformState.x * partPositionState.w;
  o1.y = animationTransformState.x;
  return;
}

#undef MAIN_PART_GLASS_BEHIND_EDGE_SCALE
#undef MAIN_PART_GLASS_BEHIND_TRANSMISSION_RANGE
