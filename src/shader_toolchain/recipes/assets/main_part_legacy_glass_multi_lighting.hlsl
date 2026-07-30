#ifndef MAIN_PART_LEGACY_GLASS_MULTI_LIGHTING_HLSL
#define MAIN_PART_LEGACY_GLASS_MULTI_LIGHTING_HLSL

struct MainPartLegacyGlassLightingInput
{
  float3 viewPosition;
  float2 screenUv;
  float3 normalView;
  float3 viewDirection;
  float gloss;
  float coverage;
  float reflectionStrength;
  float glossExponent;
  float specularScale;
  float3 directionalColor;
  float directionalSpecular;
};

struct MainPartLegacyGlassLighting
{
  float3 directColor;
  float3 reflection;
  float maximumSpecular;
};

MainPartLegacyGlassLighting EvaluateMainPartLegacyGlassMultiLighting(
    MainPartLegacyGlassLightingInput input)
{
  float4 partPositionState = 0;
  float4 animationTransformState = 0;
  float4 viewProjectionState = 0;
  float4 normalAndTangentState = 0;
  float4 materialCoordinateState = 0;
  float4 effectAnimationState = 0;
  float4 materialSampleState = 0;
  float4 profileMaterialState = 0;
  float4 clusterMaskState = 0;
  float4 lightIteratorState = 0;
  float4 lightGeometryState = 0;
  float4 attenuationAndCookieState = 0;
  float4 shadowState = 0;
  float4 reflectionAndRefractionState = 0;
  float4 directLightAccumulator = 0;
  float4 transmissionState = 0;
  float4 forwardAndBehindState = 0;
  float4 gbufferAndPreviewState = 0;
  float4 partScratch = 0;
  float3 v1 = input.viewPosition;
  float3 v7 = float3(input.screenUv, 0.0);
  partPositionState.x = rsqrt(dot(-v1, -v1));
  partPositionState.yzw = input.viewDirection;
  animationTransformState.xyz = float3(
      input.gloss, input.coverage, input.reflectionStrength);
  viewProjectionState.xyz = input.normalView;
  viewProjectionState.w = input.glossExponent;
  normalAndTangentState.w = input.specularScale;
  materialCoordinateState.yzw = input.directionalColor;
  materialCoordinateState.x = input.directionalSpecular;

  effectAnimationState.x = cmp(-v1.z < cb_cluster.fClusterMaxFarTotal);
  if (effectAnimationState.x != 0) {
    effectAnimationState.xyz = viewToWorld._m01_m11_m21 * v1.yyy;
    effectAnimationState.xyz = viewToWorld._m00_m10_m20 * v1.xxx + effectAnimationState.xyz;
    effectAnimationState.xyz = viewToWorld._m02_m12_m22 * v1.zzz + effectAnimationState.xyz;
    effectAnimationState.xyz = viewToWorld._m03_m13_m23 + effectAnimationState.xyz;
    effectAnimationState.w = 1 + -animationTransformState.x;
    materialSampleState.xyz = ddx_coarse(effectAnimationState.xyz);
    materialSampleState.xyz = materialSampleState.xyz + effectAnimationState.xyz;
    profileMaterialState.xyz = ddy_coarse(effectAnimationState.xyz);
    materialSampleState.xyz = profileMaterialState.xyz + materialSampleState.xyz;
    profileMaterialState.xy = cb_vInvRenderScale.xy * v7.xy;
    materialSampleState.w = -v1.z * cb_cluster.fRcpClusterRange + cb_cluster.fClusterNearBias;
    materialSampleState.w = rsqrt(materialSampleState.w);
    materialSampleState.w = 1 / materialSampleState.w;
    materialSampleState.w = cb_cluster.vVoxelDims.z * materialSampleState.w;
    materialSampleState.w = floor(materialSampleState.w);
    materialSampleState.w = (uint)materialSampleState.w;
    profileMaterialState.xy = cb_cluster.vVoxelDims.xy * profileMaterialState.xy;
    profileMaterialState.xy = (uint2)profileMaterialState.xy;
    profileMaterialState.x = mad((int)profileMaterialState.y, asint(cb_cluster.uClusterWidth), (int)profileMaterialState.x);
    materialSampleState.w = mad((int)materialSampleState.w, asint(cb_cluster.uClusterSliceSize), (int)profileMaterialState.x);
    profileMaterialState.x = (int)materialSampleState.w * 33;
    profileMaterialState.x = sbVoxelLightIds[profileMaterialState.x].x;
    materialSampleState.w = mad((int)materialSampleState.w, 33, 1);
    profileMaterialState.xyz = (int3)profileMaterialState.xxx & int3(0xff00,0xff0000,0xff000000);
    clusterMaskState.xyz = materialCoordinateState.yzw;
    lightIteratorState.xyz = float3(0,0,0);
    profileMaterialState.w = materialCoordinateState.x;
    clusterMaskState.w = profileMaterialState.x;
    while (true) {
      if (clusterMaskState.w == 0) break;
      lightIteratorState.w = firstbitlow((uint)clusterMaskState.w);
      lightGeometryState.x = (int)materialSampleState.w + (int)lightIteratorState.w;
      lightGeometryState.y = 1 << (int)lightIteratorState.w;
      clusterMaskState.w = (int)clusterMaskState.w ^ (int)lightGeometryState.y;
      lightGeometryState.x = sbVoxelLightIds[lightGeometryState.x].x;
      lightIteratorState.w = (uint)lightIteratorState.w << 5;
      lightGeometryState.yzw = clusterMaskState.xyz;
      attenuationAndCookieState.xyz = lightIteratorState.xyz;
      attenuationAndCookieState.w = profileMaterialState.w;
      shadowState.x = lightGeometryState.x;
      while (true) {
        if (shadowState.x == 0) break;
        shadowState.y = firstbitlow((uint)shadowState.x);
        shadowState.z = (int)lightIteratorState.w + (int)shadowState.y;
        shadowState.y = 1 << (int)shadowState.y;
        shadowState.x = (int)shadowState.y ^ (int)shadowState.x;
        shadowState.y = (uint)shadowState.z << 1;
        shadowState.y = (int)shadowState.y + -512;
        reflectionAndRefractionState.xyz = cb_arrPoint[shadowState.y].vPosition.xyz + -v1.xyz;
        shadowState.z = dot(reflectionAndRefractionState.xyz, reflectionAndRefractionState.xyz);
        shadowState.z = sqrt(shadowState.z);
        shadowState.w = max(0.00100000005, shadowState.z);
        reflectionAndRefractionState.xyz = reflectionAndRefractionState.xyz / shadowState.www;
        shadowState.w = dot(reflectionAndRefractionState.xyz, viewProjectionState.xyz);
        shadowState.z = saturate(cb_arrPoint[shadowState.y].fRcpRadius * shadowState.z);
        shadowState.z = max(0.00999999978, shadowState.z);
        shadowState.z = log2(shadowState.z);
        shadowState.z = cb_arrPoint[shadowState.y].fFalloffFactor * shadowState.z;
        shadowState.z = exp2(shadowState.z);
        shadowState.z = 1 + -shadowState.z;
        shadowState.z = cb_arrPoint[shadowState.y].fIntensity * shadowState.z;
        shadowState.z = min(cb_arrPoint[shadowState.y].fMaxIntensity, shadowState.z);
        reflectionAndRefractionState.w = asuint(cb_arrPoint[shadowState.y].uColor) >> 24;
        reflectionAndRefractionState.w = (uint)reflectionAndRefractionState.w;
        directLightAccumulator.x = reflectionAndRefractionState.w * abs(shadowState.w);
        if (8 == 0) transmissionState.x = 0; else if (8+16 < 32) {         transmissionState.x = (uint)cb_arrPoint[shadowState.y].uColor << (32-(8 + 16)); transmissionState.x = (uint)transmissionState.x >> (32-8);        } else transmissionState.x = (uint)cb_arrPoint[shadowState.y].uColor >> 16;
        if (8 == 0) transmissionState.y = 0; else if (8+8 < 32) {         transmissionState.y = (uint)cb_arrPoint[shadowState.y].uColor << (32-(8 + 8)); transmissionState.y = (uint)transmissionState.y >> (32-8);        } else transmissionState.y = (uint)cb_arrPoint[shadowState.y].uColor >> 8;
        transmissionState.xy = (uint2)transmissionState.xy;
        directLightAccumulator.yz = transmissionState.xy * abs(shadowState.ww);
        reflectionAndRefractionState.xyz = -v1.xyz * partPositionState.xxx + reflectionAndRefractionState.xyz;
        shadowState.w = dot(reflectionAndRefractionState.xyz, reflectionAndRefractionState.xyz);
        shadowState.w = rsqrt(shadowState.w);
        reflectionAndRefractionState.xyz = reflectionAndRefractionState.xyz * shadowState.www;
        shadowState.w = dot(reflectionAndRefractionState.xyz, viewProjectionState.xyz);
        shadowState.w = shadowState.w * 0.5 + 0.5;
        shadowState.w = log2(abs(shadowState.w));
        shadowState.w = shadowState.w * viewProjectionState.w;
        shadowState.w = exp2(shadowState.w);
        shadowState.w = shadowState.w * shadowState.z;
        shadowState.w = saturate(shadowState.w * normalAndTangentState.w);
        attenuationAndCookieState.w = max(shadowState.w, attenuationAndCookieState.w);
        reflectionAndRefractionState.xyz = directLightAccumulator.xyz * shadowState.zzz;
        reflectionAndRefractionState.xyz = float3(0.00392156886,0.00392156886,0.00392156886) * reflectionAndRefractionState.xyz;
        shadowState.y = 1 & asint(cb_arrPoint[shadowState.y].uColor);
        directLightAccumulator.xyz = max(float3(0,0,0), reflectionAndRefractionState.xyz);
        directLightAccumulator.xyz = directLightAccumulator.xyz + attenuationAndCookieState.xyz;
        reflectionAndRefractionState.xyz = max(reflectionAndRefractionState.xyz, lightGeometryState.yzw);
        lightGeometryState.yzw = shadowState.yyy ? lightGeometryState.yzw : reflectionAndRefractionState.xyz;
        attenuationAndCookieState.xyz = shadowState.yyy ? directLightAccumulator.xyz : attenuationAndCookieState.xyz;
      }
      clusterMaskState.xyz = lightGeometryState.yzw;
      lightIteratorState.xyz = attenuationAndCookieState.xyz;
      profileMaterialState.w = attenuationAndCookieState.w;
    }
    materialCoordinateState.yzw = clusterMaskState.xyz;
    lightGeometryState.xyz = lightIteratorState.xyz;
    materialCoordinateState.x = profileMaterialState.w;
    profileMaterialState.x = profileMaterialState.y;
    while (true) {
      if (profileMaterialState.x == 0) break;
      clusterMaskState.w = firstbitlow((uint)profileMaterialState.x);
      lightIteratorState.w = (int)materialSampleState.w + (int)clusterMaskState.w;
      lightGeometryState.w = 1 << (int)clusterMaskState.w;
      profileMaterialState.x = (int)profileMaterialState.x ^ (int)lightGeometryState.w;
      lightIteratorState.w = sbVoxelLightIds[lightIteratorState.w].x;
      clusterMaskState.w = (uint)clusterMaskState.w << 5;
      attenuationAndCookieState.xyz = materialCoordinateState.yzw;
      shadowState.xyz = lightGeometryState.xyz;
      lightGeometryState.w = materialCoordinateState.x;
      attenuationAndCookieState.w = lightIteratorState.w;
      while (true) {
        if (attenuationAndCookieState.w == 0) break;
        shadowState.w = firstbitlow((uint)attenuationAndCookieState.w);
        reflectionAndRefractionState.x = (int)clusterMaskState.w + (int)shadowState.w;
        shadowState.w = 1 << (int)shadowState.w;
        attenuationAndCookieState.w = (int)attenuationAndCookieState.w ^ (int)shadowState.w;
        shadowState.w = mad((int)reflectionAndRefractionState.x, 9, -4608);
        reflectionAndRefractionState.xyz = cb_arrSpot[shadowState.w].vPosition.xyz + -v1.xyz;
        reflectionAndRefractionState.w = dot(reflectionAndRefractionState.xyz, reflectionAndRefractionState.xyz);
        reflectionAndRefractionState.w = sqrt(reflectionAndRefractionState.w);
        directLightAccumulator.x = cb_arrSpot[shadowState.w].fRcpRange * reflectionAndRefractionState.w;
        directLightAccumulator.y = cmp(1 >= directLightAccumulator.x);
        if (directLightAccumulator.y != 0) {
          reflectionAndRefractionState.w = max(0.00100000005, reflectionAndRefractionState.w);
          reflectionAndRefractionState.xyz = reflectionAndRefractionState.xyz / reflectionAndRefractionState.www;
          reflectionAndRefractionState.w = dot(-reflectionAndRefractionState.xyz, cb_arrSpot[shadowState.w].vForward.xyz);
          directLightAccumulator.y = cmp(0 < reflectionAndRefractionState.w);
          if (directLightAccumulator.y != 0) {
            reflectionAndRefractionState.w = saturate(reflectionAndRefractionState.w * cb_arrSpot[shadowState.w].fCutoffScale + cb_arrSpot[shadowState.w].fCutoffOffset);
            directLightAccumulator.y = 240 & asint(cb_arrSpot[shadowState.w].uColor);
            if (directLightAccumulator.y != 0) {
              directLightAccumulator.yzw = cb_arrSpot[shadowState.w].xClip._m01_m11_m31 * effectAnimationState.yyy;
              directLightAccumulator.yzw = cb_arrSpot[shadowState.w].xClip._m00_m10_m30 * effectAnimationState.xxx + directLightAccumulator.yzw;
              directLightAccumulator.yzw = cb_arrSpot[shadowState.w].xClip._m02_m12_m32 * effectAnimationState.zzz + directLightAccumulator.yzw;
              directLightAccumulator.yzw = cb_arrSpot[shadowState.w].xClip._m03_m13_m33 + directLightAccumulator.yzw;
              directLightAccumulator.yz = directLightAccumulator.yz / directLightAccumulator.ww;
              transmissionState.xy = directLightAccumulator.yz * float2(0.5,0.5) + float2(0.5,0.5);
              directLightAccumulator.yzw = cb_arrSpot[shadowState.w].xClip._m01_m11_m31 * materialSampleState.yyy;
              directLightAccumulator.yzw = cb_arrSpot[shadowState.w].xClip._m00_m10_m30 * materialSampleState.xxx + directLightAccumulator.yzw;
              directLightAccumulator.yzw = cb_arrSpot[shadowState.w].xClip._m02_m12_m32 * materialSampleState.zzz + directLightAccumulator.yzw;
              directLightAccumulator.yzw = cb_arrSpot[shadowState.w].xClip._m03_m13_m33 + directLightAccumulator.yzw;
              directLightAccumulator.yz = directLightAccumulator.yz / directLightAccumulator.ww;
              directLightAccumulator.yz = directLightAccumulator.yz * float2(0.5,0.5) + float2(0.5,0.5);
              directLightAccumulator.yz = transmissionState.xy + -directLightAccumulator.yz;
              if (4 == 0) directLightAccumulator.w = 0; else if (4+4 < 32) {               directLightAccumulator.w = (uint)cb_arrSpot[shadowState.w].uColor << (32-(4 + 4)); directLightAccumulator.w = (uint)directLightAccumulator.w >> (32-4);              } else directLightAccumulator.w = (uint)cb_arrSpot[shadowState.w].uColor >> 4;
              directLightAccumulator.w = (int)directLightAccumulator.w + -1;
              transmissionState.z = (uint)directLightAccumulator.w;
              directLightAccumulator.y = taCookies.SampleGrad(LinearClampClamp_s, transmissionState.xyz, directLightAccumulator.y, directLightAccumulator.z).x;
              reflectionAndRefractionState.w = directLightAccumulator.y * reflectionAndRefractionState.w;
            }
            directLightAccumulator.y = cmp(0 < reflectionAndRefractionState.w);
            if (directLightAccumulator.y != 0) {
              directLightAccumulator.x = max(0.00999999978, directLightAccumulator.x);
              directLightAccumulator.x = log2(directLightAccumulator.x);
              directLightAccumulator.x = cb_arrSpot[shadowState.w].fFalloffFactor * directLightAccumulator.x;
              directLightAccumulator.x = exp2(directLightAccumulator.x);
              directLightAccumulator.x = 1 + -directLightAccumulator.x;
              directLightAccumulator.x = cb_arrSpot[shadowState.w].fIntensity * directLightAccumulator.x;
              reflectionAndRefractionState.w = directLightAccumulator.x * reflectionAndRefractionState.w;
              reflectionAndRefractionState.w = min(cb_arrSpot[shadowState.w].fMaxIntensity, reflectionAndRefractionState.w);
              directLightAccumulator.x = dot(reflectionAndRefractionState.xyz, viewProjectionState.xyz);
              directLightAccumulator.y = asuint(cb_arrSpot[shadowState.w].uColor) >> 24;
              directLightAccumulator.y = (uint)directLightAccumulator.y;
              transmissionState.x = directLightAccumulator.y * abs(directLightAccumulator.x);
              if (8 == 0) directLightAccumulator.y = 0; else if (8+16 < 32) {               directLightAccumulator.y = (uint)cb_arrSpot[shadowState.w].uColor << (32-(8 + 16)); directLightAccumulator.y = (uint)directLightAccumulator.y >> (32-8);              } else directLightAccumulator.y = (uint)cb_arrSpot[shadowState.w].uColor >> 16;
              if (8 == 0) directLightAccumulator.z = 0; else if (8+8 < 32) {               directLightAccumulator.z = (uint)cb_arrSpot[shadowState.w].uColor << (32-(8 + 8)); directLightAccumulator.z = (uint)directLightAccumulator.z >> (32-8);              } else directLightAccumulator.z = (uint)cb_arrSpot[shadowState.w].uColor >> 8;
              directLightAccumulator.yz = (uint2)directLightAccumulator.yz;
              transmissionState.yz = directLightAccumulator.yz * abs(directLightAccumulator.xx);
              reflectionAndRefractionState.xyz = -v1.xyz * partPositionState.xxx + reflectionAndRefractionState.xyz;
              directLightAccumulator.x = dot(reflectionAndRefractionState.xyz, reflectionAndRefractionState.xyz);
              directLightAccumulator.x = rsqrt(directLightAccumulator.x);
              reflectionAndRefractionState.xyz = directLightAccumulator.xxx * reflectionAndRefractionState.xyz;
              reflectionAndRefractionState.x = dot(reflectionAndRefractionState.xyz, viewProjectionState.xyz);
              reflectionAndRefractionState.x = reflectionAndRefractionState.x * 0.5 + 0.5;
              reflectionAndRefractionState.x = log2(abs(reflectionAndRefractionState.x));
              reflectionAndRefractionState.x = reflectionAndRefractionState.x * viewProjectionState.w;
              reflectionAndRefractionState.x = exp2(reflectionAndRefractionState.x);
              reflectionAndRefractionState.x = reflectionAndRefractionState.x * reflectionAndRefractionState.w;
              reflectionAndRefractionState.x = saturate(reflectionAndRefractionState.x * normalAndTangentState.w);
              lightGeometryState.w = max(reflectionAndRefractionState.x, lightGeometryState.w);
              reflectionAndRefractionState.xyz = transmissionState.xyz * reflectionAndRefractionState.www;
              reflectionAndRefractionState.xyz = float3(0.00392156886,0.00392156886,0.00392156886) * reflectionAndRefractionState.xyz;
              shadowState.w = 1 & asint(cb_arrSpot[shadowState.w].uColor);
              directLightAccumulator.xyz = max(float3(0,0,0), reflectionAndRefractionState.xyz);
              directLightAccumulator.xyz = directLightAccumulator.xyz + shadowState.xyz;
              reflectionAndRefractionState.xyz = max(reflectionAndRefractionState.xyz, attenuationAndCookieState.xyz);
              attenuationAndCookieState.xyz = shadowState.www ? attenuationAndCookieState.xyz : reflectionAndRefractionState.xyz;
              shadowState.xyz = shadowState.www ? directLightAccumulator.xyz : shadowState.xyz;
            }
          }
        }
      }
      materialCoordinateState.yzw = attenuationAndCookieState.xyz;
      lightGeometryState.xyz = shadowState.xyz;
      materialCoordinateState.x = lightGeometryState.w;
    }
    partPositionState.x = dot(-partPositionState.yzw, viewProjectionState.xyz);
    partPositionState.x = partPositionState.x + partPositionState.x;
    materialSampleState.xyz = viewProjectionState.xyz * -partPositionState.xxx + -partPositionState.yzw;
    profileMaterialState.xyw = viewToWorld._m01_m11_m21 * materialSampleState.yyy;
    profileMaterialState.xyw = viewToWorld._m00_m10_m20 * materialSampleState.xxx + profileMaterialState.xyw;
    materialSampleState.xyz = viewToWorld._m02_m12_m22 * materialSampleState.zzz + profileMaterialState.xyw;
    partPositionState.x = log2(abs(effectAnimationState.w));
    partPositionState.x = 0.75 * partPositionState.x;
    partPositionState.x = exp2(partPositionState.x);
    profileMaterialState.xy = float2(5,0.5) * partPositionState.xx;
    viewProjectionState.w = min(1, profileMaterialState.y);
    viewProjectionState.w = 1 + -viewProjectionState.w;
    partPositionState.x = partPositionState.x * 5 + -3;
    partPositionState.x = saturate(partPositionState.x + partPositionState.x);
    partPositionState.x = 1 + -partPositionState.x;
    clusterMaskState.xyz = rcp(materialSampleState.xyz);
    lightIteratorState.xyz = float3(0,0,0);
    attenuationAndCookieState.xyz = float3(0,0,0);
    normalAndTangentState.w = 0;
    effectAnimationState.w = 0;
    profileMaterialState.y = 0;
    profileMaterialState.w = profileMaterialState.z;
    while (true) {
      if (profileMaterialState.w == 0) break;
      clusterMaskState.w = firstbitlow((uint)profileMaterialState.w);
      lightIteratorState.w = (int)materialSampleState.w + (int)clusterMaskState.w;
      lightGeometryState.w = 1 << (int)clusterMaskState.w;
      profileMaterialState.w = (int)profileMaterialState.w ^ (int)lightGeometryState.w;
      lightIteratorState.w = sbVoxelLightIds[lightIteratorState.w].x;
      clusterMaskState.w = (uint)clusterMaskState.w << 5;
      shadowState.xyz = lightIteratorState.xyz;
      reflectionAndRefractionState.xyz = attenuationAndCookieState.xyz;
      lightGeometryState.w = normalAndTangentState.w;
      attenuationAndCookieState.w = effectAnimationState.w;
      shadowState.w = profileMaterialState.y;
      reflectionAndRefractionState.w = lightIteratorState.w;
      while (true) {
        if (reflectionAndRefractionState.w == 0) break;
        directLightAccumulator.x = firstbitlow((uint)reflectionAndRefractionState.w);
        directLightAccumulator.y = (int)clusterMaskState.w + (int)directLightAccumulator.x;
        directLightAccumulator.x = 1 << (int)directLightAccumulator.x;
        reflectionAndRefractionState.w = (int)reflectionAndRefractionState.w ^ (int)directLightAccumulator.x;
        directLightAccumulator.x = mad((int)directLightAccumulator.y, 10, -7680);
        directLightAccumulator.yzw = cb_reflections.vecProbes[directLightAccumulator.x].vPosition.xyz + -effectAnimationState.xyz;
        directLightAccumulator.yzw = -cb_reflections.vecProbes[directLightAccumulator.x].vExtents.xyz + abs(directLightAccumulator.yzw);
        transmissionState.xyz = max(float3(0,0,0), directLightAccumulator.yzw);
        transmissionState.x = dot(transmissionState.xyz, transmissionState.xyz);
        transmissionState.x = sqrt(transmissionState.x);
        directLightAccumulator.y = max(directLightAccumulator.y, directLightAccumulator.z);
        directLightAccumulator.y = max(directLightAccumulator.y, directLightAccumulator.w);
        directLightAccumulator.y = min(0, directLightAccumulator.y);
        directLightAccumulator.y = transmissionState.x + directLightAccumulator.y;
        directLightAccumulator.y = -cb_reflections.vecProbes[directLightAccumulator.x].fMargin + directLightAccumulator.y;
        directLightAccumulator.y = cb_reflections.vecProbes[directLightAccumulator.x].fGpuEnable * directLightAccumulator.y;
        directLightAccumulator.z = cmp(directLightAccumulator.y < 0);
        if (directLightAccumulator.z != 0) {
          directLightAccumulator.y = saturate(cb_reflections.vecProbes[directLightAccumulator.x].fMarginRcp * -directLightAccumulator.y);
          directLightAccumulator.z = cmp(0 != cb_reflections.vecProbes[directLightAccumulator.x].fIsFallback);
          directLightAccumulator.z = directLightAccumulator.z ? 1 : directLightAccumulator.y;
          directLightAccumulator.w = cb_reflections.vecProbes[directLightAccumulator.x].fBlend * directLightAccumulator.z;
          transmissionState.x = cmp(1.000000 == cb_reflections.vecProbes[directLightAccumulator.x].fIsFallback);
          if (transmissionState.x != 0) {
            transmissionState.x = cmp(1.000000 == cb_reflections.vecProbes[directLightAccumulator.x].fParallax);
            transmissionState.yzw = cb_reflections.vecProbes[directLightAccumulator.x].vMax.xyz + -effectAnimationState.xyz;
            transmissionState.yzw = transmissionState.yzw * clusterMaskState.xyz;
            forwardAndBehindState.xyz = cb_reflections.vecProbes[directLightAccumulator.x].vMin.xyz + -effectAnimationState.xyz;
            forwardAndBehindState.xyz = forwardAndBehindState.xyz * clusterMaskState.xyz;
            transmissionState.yzw = max(forwardAndBehindState.xyz, transmissionState.yzw);
            transmissionState.y = min(transmissionState.y, transmissionState.z);
            transmissionState.y = min(transmissionState.y, transmissionState.w);
            transmissionState.yzw = materialSampleState.xyz * transmissionState.yyy + effectAnimationState.xyz;
            transmissionState.yzw = -cb_reflections.vecProbes[directLightAccumulator.x].vPosition.xyz + transmissionState.yzw;
            transmissionState.xyz = transmissionState.xxx ? transmissionState.yzw : materialSampleState.xyz;
            transmissionState.w = abs(transmissionState.x) + abs(transmissionState.y);
            transmissionState.w = transmissionState.w + abs(transmissionState.z);
            transmissionState.w = max(9.99999975e-05, transmissionState.w);
            transmissionState.w = rcp(transmissionState.w);
            transmissionState.xy = transmissionState.xy * transmissionState.ww;
            forwardAndBehindState.xy = float2(1,1) + -abs(transmissionState.yx);
            forwardAndBehindState.zw = cmp(transmissionState.xy < float2(0,0));
            forwardAndBehindState.xy = forwardAndBehindState.zw ? -forwardAndBehindState.xy : forwardAndBehindState.xy;
            transmissionState.z = cmp(0 >= transmissionState.z);
            transmissionState.xy = transmissionState.zz ? forwardAndBehindState.xy : transmissionState.xy;
            transmissionState.xy = float2(-2,2) + transmissionState.xy;
            transmissionState.z = max(abs(transmissionState.x), abs(transmissionState.y));
            transmissionState.z = cmp(transmissionState.z >= 1);
            transmissionState.xy = transmissionState.zz ? -transmissionState.xy : transmissionState.xy;
            transmissionState.xy = transmissionState.xy * float2(0.5,0.5) + float2(0.5,0.5);
            transmissionState.z = cb_reflections.vecProbes[directLightAccumulator.x].fSlotIndex;
            transmissionState.xyz = taReflection.SampleLevel(LinearMirrorMirror_s, transmissionState.xyz, profileMaterialState.x).xyz;
            lightGeometryState.w = directLightAccumulator.z * cb_reflections.vecProbes[directLightAccumulator.x].fBlend + lightGeometryState.w;
            reflectionAndRefractionState.xyz = transmissionState.xyz * directLightAccumulator.www + reflectionAndRefractionState.xyz;
          } else {
            directLightAccumulator.z = cb_reflections.vecProbes[directLightAccumulator.x].fParallax * partPositionState.x;
            transmissionState.xyz = cb_reflections.vecProbes[directLightAccumulator.x].vMax.xyz + -effectAnimationState.xyz;
            transmissionState.xyz = transmissionState.xyz * clusterMaskState.xyz;
            forwardAndBehindState.xyz = cb_reflections.vecProbes[directLightAccumulator.x].vMin.xyz + -effectAnimationState.xyz;
            forwardAndBehindState.xyz = forwardAndBehindState.xyz * clusterMaskState.xyz;
            transmissionState.xyz = max(forwardAndBehindState.xyz, transmissionState.xyz);
            transmissionState.x = min(transmissionState.x, transmissionState.y);
            transmissionState.x = min(transmissionState.x, transmissionState.z);
            transmissionState.xyz = materialSampleState.xyz * transmissionState.xxx + effectAnimationState.xyz;
            transmissionState.xyz = -cb_reflections.vecProbes[directLightAccumulator.x].vPosition.xyz + transmissionState.xyz;
            transmissionState.w = dot(transmissionState.xyz, transmissionState.xyz);
            transmissionState.w = rsqrt(transmissionState.w);
            transmissionState.xyz = transmissionState.xyz * transmissionState.www + -materialSampleState.xyz;
            transmissionState.xyz = directLightAccumulator.zzz * transmissionState.xyz + materialSampleState.xyz;
            directLightAccumulator.z = dot(transmissionState.xyz, transmissionState.xyz);
            directLightAccumulator.z = rsqrt(directLightAccumulator.z);
            transmissionState.xyz = transmissionState.xyz * directLightAccumulator.zzz;
            directLightAccumulator.z = abs(transmissionState.x) + abs(transmissionState.y);
            directLightAccumulator.z = directLightAccumulator.z + abs(transmissionState.z);
            directLightAccumulator.z = max(9.99999975e-05, directLightAccumulator.z);
            directLightAccumulator.z = rcp(directLightAccumulator.z);
            forwardAndBehindState.xy = transmissionState.xy * directLightAccumulator.zz;
            forwardAndBehindState.zw = float2(1,1) + -abs(forwardAndBehindState.yx);
            gbufferAndPreviewState.xy = cmp(forwardAndBehindState.xy < float2(0,0));
            forwardAndBehindState.zw = gbufferAndPreviewState.xy ? -forwardAndBehindState.zw : forwardAndBehindState.zw;
            directLightAccumulator.z = cmp(0 >= transmissionState.z);
            forwardAndBehindState.xy = directLightAccumulator.zz ? forwardAndBehindState.zw : forwardAndBehindState.xy;
            forwardAndBehindState.xy = float2(-2,2) + forwardAndBehindState.xy;
            directLightAccumulator.z = max(abs(forwardAndBehindState.x), abs(forwardAndBehindState.y));
            directLightAccumulator.z = cmp(directLightAccumulator.z >= 1);
            forwardAndBehindState.xy = directLightAccumulator.zz ? -forwardAndBehindState.xy : forwardAndBehindState.xy;
            forwardAndBehindState.xy = forwardAndBehindState.xy * float2(0.5,0.5) + float2(0.5,0.5);
            forwardAndBehindState.z = cb_reflections.vecProbes[directLightAccumulator.x].fSlotIndex;
            forwardAndBehindState.xyzw = taReflection.SampleLevel(LinearMirrorMirror_s, forwardAndBehindState.xyz, profileMaterialState.x).xyzw;
            directLightAccumulator.z = forwardAndBehindState.w * forwardAndBehindState.w;
            directLightAccumulator.z = directLightAccumulator.z * 127.5 + 0.5;
            gbufferAndPreviewState.xyz = transmissionState.xyz * directLightAccumulator.zzz + cb_reflections.vecProbes[directLightAccumulator.x].vPosition.xyz;
            partScratch.xyz = -gbufferAndPreviewState.xyz + effectAnimationState.xyz;
            directLightAccumulator.z = dot(partScratch.xyz, partScratch.xyz);
            gbufferAndPreviewState.xyz = cb_reflections.vecProbes[directLightAccumulator.x].vGpuPosition.xyz + -gbufferAndPreviewState.xyz;
            gbufferAndPreviewState.xyz = -cb_reflections.vecProbes[directLightAccumulator.x].vGpuExtents.xyz + abs(gbufferAndPreviewState.xyz);
            partScratch.xyz = max(float3(0,0,0), gbufferAndPreviewState.xyz);
            transmissionState.w = dot(partScratch.xyz, partScratch.xyz);
            transmissionState.w = sqrt(transmissionState.w);
            forwardAndBehindState.w = max(gbufferAndPreviewState.x, gbufferAndPreviewState.y);
            forwardAndBehindState.w = max(forwardAndBehindState.w, gbufferAndPreviewState.z);
            forwardAndBehindState.w = min(0, forwardAndBehindState.w);
            transmissionState.w = forwardAndBehindState.w + transmissionState.w;
            transmissionState.w = -cb_reflections.vecProbes[directLightAccumulator.x].fGpuMargin + transmissionState.w;
            directLightAccumulator.x = saturate(cb_reflections.vecProbes[directLightAccumulator.x].fGpuMarginRcp * -transmissionState.w);
            transmissionState.x = dot(materialSampleState.xyz, transmissionState.xyz);
            transmissionState.x = transmissionState.x * 0.5 + 0.5;
            transmissionState.x = transmissionState.x * transmissionState.x;
            directLightAccumulator.z = 0.000244140625 * directLightAccumulator.z;
            directLightAccumulator.z = min(1, directLightAccumulator.z);
            directLightAccumulator.z = 1 + -directLightAccumulator.z;
            directLightAccumulator.z = directLightAccumulator.z * directLightAccumulator.z;
            directLightAccumulator.z = directLightAccumulator.z * directLightAccumulator.x;
            directLightAccumulator.z = directLightAccumulator.z * transmissionState.x;
            directLightAccumulator.z = directLightAccumulator.z * directLightAccumulator.y;
            directLightAccumulator.z = directLightAccumulator.z * 10 + 1;
            directLightAccumulator.x = max(directLightAccumulator.x, viewProjectionState.w);
            directLightAccumulator.x = directLightAccumulator.x * directLightAccumulator.y;
            directLightAccumulator.x = directLightAccumulator.x * transmissionState.x;
            directLightAccumulator.x = directLightAccumulator.z * directLightAccumulator.x;
            directLightAccumulator.y = directLightAccumulator.x * directLightAccumulator.w;
            attenuationAndCookieState.w = directLightAccumulator.x * directLightAccumulator.w + attenuationAndCookieState.w;
            directLightAccumulator.x = cmp(0 < directLightAccumulator.x);
            directLightAccumulator.x = directLightAccumulator.x ? 1.000000 : 0;
            shadowState.w = directLightAccumulator.w * directLightAccumulator.x + shadowState.w;
            directLightAccumulator.yzw = forwardAndBehindState.xyz * directLightAccumulator.yyy;
            shadowState.xyz = directLightAccumulator.yzw * directLightAccumulator.xxx + shadowState.xyz;
          }
        }
      }
      lightIteratorState.xyz = shadowState.xyz;
      attenuationAndCookieState.xyz = reflectionAndRefractionState.xyz;
      normalAndTangentState.w = lightGeometryState.w;
      effectAnimationState.w = attenuationAndCookieState.w;
      profileMaterialState.y = shadowState.w;
    }
    partPositionState.x = max(0.125, effectAnimationState.w);
    effectAnimationState.xyz = lightIteratorState.xyz / partPositionState.xxx;
    partPositionState.x = max(0.00100000005, normalAndTangentState.w);
    materialSampleState.xyz = attenuationAndCookieState.xyz / partPositionState.xxx;
    profileMaterialState.y = saturate(profileMaterialState.y);
    partPositionState.x = profileMaterialState.y * profileMaterialState.y;
    effectAnimationState.xyz = -materialSampleState.xyz + effectAnimationState.xyz;
    effectAnimationState.xyz = partPositionState.xxx * effectAnimationState.xyz + materialSampleState.xyz;
  } else {
    lightGeometryState.xyz = float3(0,0,0);
    effectAnimationState.xyz = float3(0,0,0);
  }
  effectAnimationState.xyz = effectAnimationState.xyz * animationTransformState.zzz;
  materialCoordinateState.yzw = materialCoordinateState.yzw + lightGeometryState.xyz;

  MainPartLegacyGlassLighting result;
  result.directColor = materialCoordinateState.yzw;
  result.reflection = effectAnimationState.xyz;
  result.maximumSpecular = materialCoordinateState.x;
  return result;
}

#endif
