#ifndef MAIN_PART_WATER_MULTI_HIGH_LIGHTING_HLSL
#define MAIN_PART_WATER_MULTI_HIGH_LIGHTING_HLSL

struct MainPartMultiWaterLightingInput
{
  float3 viewPosition;
  float2 screenUv;
  float3 normalView;
  float3 viewDirection;
  float roughnessComplement;
  float reflectionStrength;
};

struct MainPartMultiWaterLighting
{
  float3 directLight;
  float3 reflection;
  float viewDistance;
};

MainPartMultiWaterLighting EvaluateMainPartMultiWaterLighting(
    MainPartMultiWaterLightingInput input)
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

  float3 v1 = input.viewPosition;
  float3 v7 = float3(input.screenUv, 0.0);
  animationTransformState.xyz = input.normalView;
  normalAndTangentState.xyz = input.viewDirection;
  materialCoordinateState.x = input.roughnessComplement;
  partPositionState.z = input.reflectionStrength;

// Resolve the clustered voxel and accumulate ambient, point, and spot lights.
// Packed masks and nested light-bit traversal remain in DXBC order.
  partPositionState.w = cmp(-v1.z < cb_cluster.fClusterMaxFarTotal);
  if (partPositionState.w != 0) {
    partPositionState.w = cb_vInverseCameraRange.x * -v1.z;
    viewProjectionState.w = dot(-normalAndTangentState.xyz, animationTransformState.xyz);
    viewProjectionState.w = viewProjectionState.w + viewProjectionState.w;
    materialCoordinateState.yzw = animationTransformState.xyz * -viewProjectionState.www + -normalAndTangentState.xyz;
    effectAnimationState.xyz = viewToWorld._m01_m11_m21 * materialCoordinateState.zzz;
    effectAnimationState.xyz = viewToWorld._m00_m10_m20 * materialCoordinateState.yyy + effectAnimationState.xyz;
    materialCoordinateState.yzw = viewToWorld._m02_m12_m22 * materialCoordinateState.www + effectAnimationState.xyz;
    viewProjectionState.w = log2(abs(materialCoordinateState.x));
    viewProjectionState.w = 0.75 * viewProjectionState.w;
    viewProjectionState.w = exp2(viewProjectionState.w);
    effectAnimationState.xyz = viewToWorld._m01_m11_m21 * v1.yyy;
    effectAnimationState.xyz = viewToWorld._m00_m10_m20 * v1.xxx + effectAnimationState.xyz;
    effectAnimationState.xyz = viewToWorld._m02_m12_m22 * v1.zzz + effectAnimationState.xyz;
    effectAnimationState.xyz = viewToWorld._m03_m13_m23 + effectAnimationState.xyz;
    materialSampleState.xyz = ddx_coarse(effectAnimationState.xyz);
    materialSampleState.xyz = materialSampleState.xyz + effectAnimationState.xyz;
    profileMaterialState.xyz = ddy_coarse(effectAnimationState.xyz);
    materialSampleState.xyz = profileMaterialState.xyz + materialSampleState.xyz;
    partPositionState.w = saturate(6.66666651 * partPositionState.w);
    partPositionState.w = 1 + -partPositionState.w;
    normalAndTangentState.zw = cb_vInvRenderScale.xy * v7.xy;
    materialCoordinateState.x = -v1.z * cb_cluster.fRcpClusterRange + cb_cluster.fClusterNearBias;
    materialCoordinateState.x = rsqrt(materialCoordinateState.x);
    materialCoordinateState.x = 1 / materialCoordinateState.x;
    materialCoordinateState.x = cb_cluster.vVoxelDims.z * materialCoordinateState.x;
    materialCoordinateState.x = floor(materialCoordinateState.x);
    materialCoordinateState.x = (uint)materialCoordinateState.x;
    normalAndTangentState.zw = cb_cluster.vVoxelDims.xy * normalAndTangentState.zw;
    normalAndTangentState.zw = (uint2)normalAndTangentState.zw;
    normalAndTangentState.z = mad((int)normalAndTangentState.w, asint(cb_cluster.uClusterWidth), (int)normalAndTangentState.z);
    normalAndTangentState.z = mad((int)materialCoordinateState.x, asint(cb_cluster.uClusterSliceSize), (int)normalAndTangentState.z);
    normalAndTangentState.w = (int)normalAndTangentState.z * 33;
    normalAndTangentState.w = sbVoxelLightIds[normalAndTangentState.w].x;
    normalAndTangentState.z = mad((int)normalAndTangentState.z, 33, 1);
    profileMaterialState.xyzw = (int4)normalAndTangentState.wwww & int4(255,0xff00,0xff0000,0xff000000);
    clusterMaskState.xyz = cb_vDirectionalLightColor.xyz;
    normalAndTangentState.w = profileMaterialState.x;
    while (true) {
      if (normalAndTangentState.w == 0) break;
      materialCoordinateState.x = firstbitlow((uint)normalAndTangentState.w);
      effectAnimationState.w = (int)normalAndTangentState.z + (int)materialCoordinateState.x;
      materialSampleState.w = 1 << (int)materialCoordinateState.x;
      normalAndTangentState.w = (int)normalAndTangentState.w ^ (int)materialSampleState.w;
      effectAnimationState.w = sbVoxelLightIds[effectAnimationState.w].x;
      materialCoordinateState.x = (uint)materialCoordinateState.x << 5;
      lightIteratorState.xyz = clusterMaskState.xyz;
      materialSampleState.w = effectAnimationState.w;
      while (true) {
        if (materialSampleState.w == 0) break;
        clusterMaskState.w = firstbitlow((uint)materialSampleState.w);
        lightIteratorState.w = (int)materialCoordinateState.x + (int)clusterMaskState.w;
        clusterMaskState.w = 1 << (int)clusterMaskState.w;
        materialSampleState.w = (int)materialSampleState.w ^ (int)clusterMaskState.w;
        clusterMaskState.w = (uint)lightIteratorState.w << 1;
        lightGeometryState.xyz = cb_arrAmbient[clusterMaskState.w].vPosition.xyz + -v1.xyz;
        lightIteratorState.w = dot(lightGeometryState.xyz, lightGeometryState.xyz);
        lightGeometryState.w = sqrt(lightIteratorState.w);
        lightGeometryState.w = saturate(cb_arrAmbient[clusterMaskState.w].fRcpRadius * lightGeometryState.w);
        lightIteratorState.w = rsqrt(lightIteratorState.w);
        lightGeometryState.xyz = lightGeometryState.xyz * lightIteratorState.www;
        lightIteratorState.w = dot(lightGeometryState.xyz, animationTransformState.xyz);
        lightIteratorState.w = abs(lightIteratorState.w) * 0.5 + 0.5;
        lightGeometryState.x = lightGeometryState.w * lightGeometryState.w;
        lightGeometryState.x = -lightGeometryState.x * lightGeometryState.x + 1;
        lightGeometryState.x = cb_arrAmbient[clusterMaskState.w].fIntensity * lightGeometryState.x;
        lightGeometryState.x = lightGeometryState.x * partPositionState.w;
        lightIteratorState.w = lightGeometryState.x * lightIteratorState.w;
        lightGeometryState.xyz = cb_arrAmbient[clusterMaskState.w].vColor.xyz * lightIteratorState.www;
        lightIteratorState.xyz = max(lightGeometryState.xyz, lightIteratorState.xyz);
      }
      clusterMaskState.xyz = lightIteratorState.xyz;
    }
    lightIteratorState.xyz = clusterMaskState.xyz;
    lightGeometryState.xyz = float3(0,0,0);
    partPositionState.w = profileMaterialState.y;
    while (true) {
      if (partPositionState.w == 0) break;
      normalAndTangentState.w = firstbitlow((uint)partPositionState.w);
      materialCoordinateState.x = (int)normalAndTangentState.w + (int)normalAndTangentState.z;
      effectAnimationState.w = 1 << (int)normalAndTangentState.w;
      partPositionState.w = (int)partPositionState.w ^ (int)effectAnimationState.w;
      materialCoordinateState.x = sbVoxelLightIds[materialCoordinateState.x].x;
      normalAndTangentState.w = (uint)normalAndTangentState.w << 5;
      attenuationAndCookieState.xyz = lightIteratorState.xyz;
      shadowState.xyz = lightGeometryState.xyz;
      effectAnimationState.w = materialCoordinateState.x;
      while (true) {
        if (effectAnimationState.w == 0) break;
        materialSampleState.w = firstbitlow((uint)effectAnimationState.w);
        profileMaterialState.x = (int)normalAndTangentState.w + (int)materialSampleState.w;
        materialSampleState.w = 1 << (int)materialSampleState.w;
        effectAnimationState.w = (int)effectAnimationState.w ^ (int)materialSampleState.w;
        materialSampleState.w = (uint)profileMaterialState.x << 1;
        materialSampleState.w = (int)materialSampleState.w + -512;
        reflectionAndRefractionState.xyz = cb_arrPoint[materialSampleState.w].vPosition.xyz + -v1.xyz;
        profileMaterialState.x = dot(reflectionAndRefractionState.xyz, reflectionAndRefractionState.xyz);
        profileMaterialState.x = sqrt(profileMaterialState.x);
        clusterMaskState.w = saturate(cb_arrPoint[materialSampleState.w].fRcpRadius * profileMaterialState.x);
        profileMaterialState.x = max(0.00100000005, profileMaterialState.x);
        reflectionAndRefractionState.xyz = reflectionAndRefractionState.xyz / profileMaterialState.xxx;
        profileMaterialState.x = dot(reflectionAndRefractionState.xyz, animationTransformState.xyz);
        profileMaterialState.x = abs(profileMaterialState.x) * 0.75 + 0.25;
        clusterMaskState.w = max(0.00999999978, clusterMaskState.w);
        clusterMaskState.w = log2(clusterMaskState.w);
        clusterMaskState.w = cb_arrPoint[materialSampleState.w].fFalloffFactor * clusterMaskState.w;
        clusterMaskState.w = exp2(clusterMaskState.w);
        clusterMaskState.w = 1 + -clusterMaskState.w;
        clusterMaskState.w = cb_arrPoint[materialSampleState.w].fIntensity * clusterMaskState.w;
        clusterMaskState.w = min(cb_arrPoint[materialSampleState.w].fMaxIntensity, clusterMaskState.w);
        lightIteratorState.w = asuint(cb_arrPoint[materialSampleState.w].uColor) >> 24;
        lightIteratorState.w = (uint)lightIteratorState.w;
        reflectionAndRefractionState.x = lightIteratorState.w * profileMaterialState.x;
        if (8 == 0) directLightAccumulator.x = 0; else if (8+16 < 32) {         directLightAccumulator.x = (uint)cb_arrPoint[materialSampleState.w].uColor << (32-(8 + 16)); directLightAccumulator.x = (uint)directLightAccumulator.x >> (32-8);        } else directLightAccumulator.x = (uint)cb_arrPoint[materialSampleState.w].uColor >> 16;
        if (8 == 0) directLightAccumulator.y = 0; else if (8+8 < 32) {         directLightAccumulator.y = (uint)cb_arrPoint[materialSampleState.w].uColor << (32-(8 + 8)); directLightAccumulator.y = (uint)directLightAccumulator.y >> (32-8);        } else directLightAccumulator.y = (uint)cb_arrPoint[materialSampleState.w].uColor >> 8;
        directLightAccumulator.xy = (uint2)directLightAccumulator.xy;
        reflectionAndRefractionState.yz = directLightAccumulator.xy * profileMaterialState.xx;
        reflectionAndRefractionState.xyz = reflectionAndRefractionState.xyz * clusterMaskState.www;
        reflectionAndRefractionState.xyz = float3(0.00392156886,0.00392156886,0.00392156886) * reflectionAndRefractionState.xyz;
        materialSampleState.w = 1 & asint(cb_arrPoint[materialSampleState.w].uColor);
        directLightAccumulator.xyz = max(float3(0,0,0), reflectionAndRefractionState.xyz);
        directLightAccumulator.xyz = directLightAccumulator.xyz + shadowState.xyz;
        reflectionAndRefractionState.xyz = max(reflectionAndRefractionState.xyz, attenuationAndCookieState.xyz);
        attenuationAndCookieState.xyz = materialSampleState.www ? attenuationAndCookieState.xyz : reflectionAndRefractionState.xyz;
        shadowState.xyz = materialSampleState.www ? directLightAccumulator.xyz : shadowState.xyz;
      }
      lightIteratorState.xyz = attenuationAndCookieState.xyz;
      lightGeometryState.xyz = shadowState.xyz;
    }
    clusterMaskState.xyz = lightIteratorState.xyz;
    attenuationAndCookieState.xyz = lightGeometryState.xyz;
    partPositionState.w = profileMaterialState.z;
    while (true) {
      if (partPositionState.w == 0) break;
      normalAndTangentState.w = firstbitlow((uint)partPositionState.w);
      materialCoordinateState.x = (int)normalAndTangentState.w + (int)normalAndTangentState.z;
      effectAnimationState.w = 1 << (int)normalAndTangentState.w;
      partPositionState.w = (int)partPositionState.w ^ (int)effectAnimationState.w;
      materialCoordinateState.x = sbVoxelLightIds[materialCoordinateState.x].x;
      normalAndTangentState.w = (uint)normalAndTangentState.w << 5;
      shadowState.xyz = clusterMaskState.xyz;
      reflectionAndRefractionState.xyz = attenuationAndCookieState.xyz;
      effectAnimationState.w = materialCoordinateState.x;
      while (true) {
        if (effectAnimationState.w == 0) break;
        materialSampleState.w = firstbitlow((uint)effectAnimationState.w);
        profileMaterialState.x = (int)normalAndTangentState.w + (int)materialSampleState.w;
        materialSampleState.w = 1 << (int)materialSampleState.w;
        effectAnimationState.w = (int)effectAnimationState.w ^ (int)materialSampleState.w;
        materialSampleState.w = mad((int)profileMaterialState.x, 9, -4608);
        directLightAccumulator.xyz = cb_arrSpot[materialSampleState.w].vPosition.xyz + -v1.xyz;
        profileMaterialState.x = dot(directLightAccumulator.xyz, directLightAccumulator.xyz);
        profileMaterialState.x = sqrt(profileMaterialState.x);
        profileMaterialState.y = cb_arrSpot[materialSampleState.w].fRcpRange * profileMaterialState.x;
        clusterMaskState.w = cmp(1 >= profileMaterialState.y);
        if (clusterMaskState.w != 0) {
          profileMaterialState.x = max(0.00100000005, profileMaterialState.x);
          directLightAccumulator.xyz = directLightAccumulator.xyz / profileMaterialState.xxx;
          profileMaterialState.x = dot(-directLightAccumulator.xyz, cb_arrSpot[materialSampleState.w].vForward.xyz);
          clusterMaskState.w = cmp(0 < profileMaterialState.x);
          if (clusterMaskState.w != 0) {
            clusterMaskState.w = dot(directLightAccumulator.xyz, animationTransformState.xyz);
            profileMaterialState.x = saturate(profileMaterialState.x * cb_arrSpot[materialSampleState.w].fCutoffScale + cb_arrSpot[materialSampleState.w].fCutoffOffset);
            directLightAccumulator.xy = int2(240,1) & asint(cb_arrSpot[materialSampleState.w].uColor);
            if (directLightAccumulator.x != 0) {
              directLightAccumulator.xzw = cb_arrSpot[materialSampleState.w].xClip._m01_m11_m31 * effectAnimationState.yyy;
              directLightAccumulator.xzw = cb_arrSpot[materialSampleState.w].xClip._m00_m10_m30 * effectAnimationState.xxx + directLightAccumulator.xzw;
              directLightAccumulator.xzw = cb_arrSpot[materialSampleState.w].xClip._m02_m12_m32 * effectAnimationState.zzz + directLightAccumulator.xzw;
              directLightAccumulator.xzw = cb_arrSpot[materialSampleState.w].xClip._m03_m13_m33 + directLightAccumulator.xzw;
              directLightAccumulator.xz = directLightAccumulator.xz / directLightAccumulator.ww;
              transmissionState.xy = directLightAccumulator.xz * float2(0.5,0.5) + float2(0.5,0.5);
              directLightAccumulator.xzw = cb_arrSpot[materialSampleState.w].xClip._m01_m11_m31 * materialSampleState.yyy;
              directLightAccumulator.xzw = cb_arrSpot[materialSampleState.w].xClip._m00_m10_m30 * materialSampleState.xxx + directLightAccumulator.xzw;
              directLightAccumulator.xzw = cb_arrSpot[materialSampleState.w].xClip._m02_m12_m32 * materialSampleState.zzz + directLightAccumulator.xzw;
              directLightAccumulator.xzw = cb_arrSpot[materialSampleState.w].xClip._m03_m13_m33 + directLightAccumulator.xzw;
              directLightAccumulator.xz = directLightAccumulator.xz / directLightAccumulator.ww;
              directLightAccumulator.xz = directLightAccumulator.xz * float2(0.5,0.5) + float2(0.5,0.5);
              directLightAccumulator.xz = transmissionState.xy + -directLightAccumulator.xz;
              if (4 == 0) lightIteratorState.w = 0; else if (4+4 < 32) {               lightIteratorState.w = (uint)cb_arrSpot[materialSampleState.w].uColor << (32-(4 + 4)); lightIteratorState.w = (uint)lightIteratorState.w >> (32-4);              } else lightIteratorState.w = (uint)cb_arrSpot[materialSampleState.w].uColor >> 4;
              lightIteratorState.w = (int)lightIteratorState.w + -1;
              transmissionState.z = (uint)lightIteratorState.w;
              lightIteratorState.w = taCookies.SampleGrad(LinearClampClamp_s, transmissionState.xyz, directLightAccumulator.x, directLightAccumulator.z).x;
              profileMaterialState.x = lightIteratorState.w * profileMaterialState.x;
            }
            lightIteratorState.w = cmp(0 < profileMaterialState.x);
            profileMaterialState.y = max(0.00999999978, profileMaterialState.y);
            profileMaterialState.y = log2(profileMaterialState.y);
            profileMaterialState.y = cb_arrSpot[materialSampleState.w].fFalloffFactor * profileMaterialState.y;
            profileMaterialState.y = exp2(profileMaterialState.y);
            profileMaterialState.y = 1 + -profileMaterialState.y;
            profileMaterialState.y = cb_arrSpot[materialSampleState.w].fIntensity * profileMaterialState.y;
            profileMaterialState.x = profileMaterialState.y * profileMaterialState.x;
            profileMaterialState.x = min(cb_arrSpot[materialSampleState.w].fMaxIntensity, profileMaterialState.x);
            profileMaterialState.y = abs(clusterMaskState.w) * 0.75 + 0.25;
            clusterMaskState.w = asuint(cb_arrSpot[materialSampleState.w].uColor) >> 24;
            clusterMaskState.w = (uint)clusterMaskState.w;
            transmissionState.x = clusterMaskState.w * profileMaterialState.y;
            if (8 == 0) directLightAccumulator.x = 0; else if (8+16 < 32) {             directLightAccumulator.x = (uint)cb_arrSpot[materialSampleState.w].uColor << (32-(8 + 16)); directLightAccumulator.x = (uint)directLightAccumulator.x >> (32-8);            } else directLightAccumulator.x = (uint)cb_arrSpot[materialSampleState.w].uColor >> 16;
            if (8 == 0) directLightAccumulator.z = 0; else if (8+8 < 32) {             directLightAccumulator.z = (uint)cb_arrSpot[materialSampleState.w].uColor << (32-(8 + 8)); directLightAccumulator.z = (uint)directLightAccumulator.z >> (32-8);            } else directLightAccumulator.z = (uint)cb_arrSpot[materialSampleState.w].uColor >> 8;
            directLightAccumulator.xz = (uint2)directLightAccumulator.xz;
            transmissionState.yz = directLightAccumulator.xz * profileMaterialState.yy;
            directLightAccumulator.xzw = transmissionState.xyz * profileMaterialState.xxx;
            directLightAccumulator.xzw = float3(0.00392156886,0.00392156886,0.00392156886) * directLightAccumulator.xzw;
            transmissionState.xyz = max(float3(0,0,0), directLightAccumulator.xzw);
            transmissionState.xyz = transmissionState.xyz + reflectionAndRefractionState.xyz;
            directLightAccumulator.xzw = max(directLightAccumulator.xzw, shadowState.xyz);
            directLightAccumulator.xzw = directLightAccumulator.yyy ? shadowState.xyz : directLightAccumulator.xzw;
            transmissionState.xyz = directLightAccumulator.yyy ? transmissionState.xyz : reflectionAndRefractionState.xyz;
            shadowState.xyz = lightIteratorState.www ? directLightAccumulator.xzw : shadowState.xyz;
            reflectionAndRefractionState.xyz = lightIteratorState.www ? transmissionState.xyz : reflectionAndRefractionState.xyz;
          }
        }
      }
      clusterMaskState.xyz = shadowState.xyz;
      attenuationAndCookieState.xyz = reflectionAndRefractionState.xyz;
    }
// Build the world reflection ray and traverse the clustered multi-probe mask.
// Box intersections, octahedral encoding, and confidence weights stay ordered.
    materialSampleState.xy = float2(5,0.5) * viewProjectionState.ww;
    partPositionState.w = min(1, materialSampleState.y);
    partPositionState.w = 1 + -partPositionState.w;
    animationTransformState.z = viewProjectionState.w * 5 + -3;
    animationTransformState.z = saturate(animationTransformState.z + animationTransformState.z);
    animationTransformState.z = 1 + -animationTransformState.z;
    materialSampleState.yzw = rcp(materialCoordinateState.yzw);
    profileMaterialState.xyz = float3(0,0,0);
    lightIteratorState.xyz = float3(0,0,0);
    viewProjectionState.w = 0;
    normalAndTangentState.w = 0;
    materialCoordinateState.x = 0;
    effectAnimationState.w = profileMaterialState.w;
    while (true) {
      if (effectAnimationState.w == 0) break;
      clusterMaskState.w = firstbitlow((uint)effectAnimationState.w);
      lightIteratorState.w = (int)normalAndTangentState.z + (int)clusterMaskState.w;
      lightGeometryState.x = 1 << (int)clusterMaskState.w;
      effectAnimationState.w = (int)effectAnimationState.w ^ (int)lightGeometryState.x;
      lightIteratorState.w = sbVoxelLightIds[lightIteratorState.w].x;
      clusterMaskState.w = (uint)clusterMaskState.w << 5;
      lightGeometryState.xyz = profileMaterialState.xyz;
      shadowState.xyz = lightIteratorState.xyz;
      lightGeometryState.w = viewProjectionState.w;
      attenuationAndCookieState.w = normalAndTangentState.w;
      shadowState.w = materialCoordinateState.x;
      reflectionAndRefractionState.x = lightIteratorState.w;
      while (true) {
        if (reflectionAndRefractionState.x == 0) break;
        reflectionAndRefractionState.y = firstbitlow((uint)reflectionAndRefractionState.x);
        reflectionAndRefractionState.z = (int)clusterMaskState.w + (int)reflectionAndRefractionState.y;
        reflectionAndRefractionState.y = 1 << (int)reflectionAndRefractionState.y;
        reflectionAndRefractionState.x = (int)reflectionAndRefractionState.y ^ (int)reflectionAndRefractionState.x;
        reflectionAndRefractionState.y = mad((int)reflectionAndRefractionState.z, 10, -7680);
        directLightAccumulator.xyz = cb_reflections.vecProbes[reflectionAndRefractionState.y].vPosition.xyz + -effectAnimationState.xyz;
        directLightAccumulator.xyz = -cb_reflections.vecProbes[reflectionAndRefractionState.y].vExtents.xyz + abs(directLightAccumulator.xyz);
        transmissionState.xyz = max(float3(0,0,0), directLightAccumulator.xyz);
        reflectionAndRefractionState.z = dot(transmissionState.xyz, transmissionState.xyz);
        reflectionAndRefractionState.z = sqrt(reflectionAndRefractionState.z);
        reflectionAndRefractionState.w = max(directLightAccumulator.x, directLightAccumulator.y);
        reflectionAndRefractionState.w = max(reflectionAndRefractionState.w, directLightAccumulator.z);
        reflectionAndRefractionState.w = min(0, reflectionAndRefractionState.w);
        reflectionAndRefractionState.z = reflectionAndRefractionState.z + reflectionAndRefractionState.w;
        reflectionAndRefractionState.z = -cb_reflections.vecProbes[reflectionAndRefractionState.y].fMargin + reflectionAndRefractionState.z;
        reflectionAndRefractionState.z = cb_reflections.vecProbes[reflectionAndRefractionState.y].fGpuEnable * reflectionAndRefractionState.z;
        reflectionAndRefractionState.w = cmp(reflectionAndRefractionState.z < 0);
        if (reflectionAndRefractionState.w != 0) {
          reflectionAndRefractionState.z = saturate(cb_reflections.vecProbes[reflectionAndRefractionState.y].fMarginRcp * -reflectionAndRefractionState.z);
          reflectionAndRefractionState.w = cmp(0 != cb_reflections.vecProbes[reflectionAndRefractionState.y].fIsFallback);
          reflectionAndRefractionState.w = reflectionAndRefractionState.w ? 1 : reflectionAndRefractionState.z;
          directLightAccumulator.x = cb_reflections.vecProbes[reflectionAndRefractionState.y].fBlend * reflectionAndRefractionState.w;
          directLightAccumulator.y = cmp(1.000000 == cb_reflections.vecProbes[reflectionAndRefractionState.y].fIsFallback);
          if (directLightAccumulator.y != 0) {
            directLightAccumulator.y = cmp(1.000000 == cb_reflections.vecProbes[reflectionAndRefractionState.y].fParallax);
            transmissionState.xyz = cb_reflections.vecProbes[reflectionAndRefractionState.y].vMax.xyz + -effectAnimationState.xyz;
            transmissionState.xyz = transmissionState.xyz * materialSampleState.yzw;
            forwardAndBehindState.xyz = cb_reflections.vecProbes[reflectionAndRefractionState.y].vMin.xyz + -effectAnimationState.xyz;
            forwardAndBehindState.xyz = forwardAndBehindState.xyz * materialSampleState.yzw;
            transmissionState.xyz = max(forwardAndBehindState.xyz, transmissionState.xyz);
            directLightAccumulator.z = min(transmissionState.x, transmissionState.y);
            directLightAccumulator.z = min(directLightAccumulator.z, transmissionState.z);
            transmissionState.xyz = materialCoordinateState.yzw * directLightAccumulator.zzz + effectAnimationState.xyz;
            transmissionState.xyz = -cb_reflections.vecProbes[reflectionAndRefractionState.y].vPosition.xyz + transmissionState.xyz;
            directLightAccumulator.yzw = directLightAccumulator.yyy ? transmissionState.xyz : materialCoordinateState.yzw;
            transmissionState.x = abs(directLightAccumulator.y) + abs(directLightAccumulator.z);
            transmissionState.x = transmissionState.x + abs(directLightAccumulator.w);
            transmissionState.x = max(9.99999975e-05, transmissionState.x);
            transmissionState.x = rcp(transmissionState.x);
            directLightAccumulator.yz = transmissionState.xx * directLightAccumulator.yz;
            transmissionState.xy = float2(1,1) + -abs(directLightAccumulator.zy);
            transmissionState.zw = cmp(directLightAccumulator.yz < float2(0,0));
            transmissionState.xy = transmissionState.zw ? -transmissionState.xy : transmissionState.xy;
            directLightAccumulator.w = cmp(0 >= directLightAccumulator.w);
            directLightAccumulator.yz = directLightAccumulator.ww ? transmissionState.xy : directLightAccumulator.yz;
            directLightAccumulator.yz = float2(-2,2) + directLightAccumulator.yz;
            directLightAccumulator.w = max(abs(directLightAccumulator.y), abs(directLightAccumulator.z));
            directLightAccumulator.w = cmp(directLightAccumulator.w >= 1);
            directLightAccumulator.yz = directLightAccumulator.ww ? -directLightAccumulator.yz : directLightAccumulator.yz;
            transmissionState.xy = directLightAccumulator.yz * float2(0.5,0.5) + float2(0.5,0.5);
            transmissionState.z = cb_reflections.vecProbes[reflectionAndRefractionState.y].fSlotIndex;
            directLightAccumulator.yzw = taReflection.SampleLevel(LinearMirrorMirror_s, transmissionState.xyz, materialSampleState.x).xyz;
            lightGeometryState.w = reflectionAndRefractionState.w * cb_reflections.vecProbes[reflectionAndRefractionState.y].fBlend + lightGeometryState.w;
            shadowState.xyz = directLightAccumulator.yzw * directLightAccumulator.xxx + shadowState.xyz;
          } else {
            reflectionAndRefractionState.w = cb_reflections.vecProbes[reflectionAndRefractionState.y].fParallax * animationTransformState.z;
            directLightAccumulator.yzw = cb_reflections.vecProbes[reflectionAndRefractionState.y].vMax.xyz + -effectAnimationState.xyz;
            directLightAccumulator.yzw = directLightAccumulator.yzw * materialSampleState.yzw;
            transmissionState.xyz = cb_reflections.vecProbes[reflectionAndRefractionState.y].vMin.xyz + -effectAnimationState.xyz;
            transmissionState.xyz = transmissionState.xyz * materialSampleState.yzw;
            directLightAccumulator.yzw = max(transmissionState.xyz, directLightAccumulator.yzw);
            directLightAccumulator.y = min(directLightAccumulator.y, directLightAccumulator.z);
            directLightAccumulator.y = min(directLightAccumulator.y, directLightAccumulator.w);
            directLightAccumulator.yzw = materialCoordinateState.yzw * directLightAccumulator.yyy + effectAnimationState.xyz;
            directLightAccumulator.yzw = -cb_reflections.vecProbes[reflectionAndRefractionState.y].vPosition.xyz + directLightAccumulator.yzw;
            transmissionState.x = dot(directLightAccumulator.yzw, directLightAccumulator.yzw);
            transmissionState.x = rsqrt(transmissionState.x);
            directLightAccumulator.yzw = directLightAccumulator.yzw * transmissionState.xxx + -materialCoordinateState.yzw;
            directLightAccumulator.yzw = reflectionAndRefractionState.www * directLightAccumulator.yzw + materialCoordinateState.yzw;
            reflectionAndRefractionState.w = dot(directLightAccumulator.yzw, directLightAccumulator.yzw);
            reflectionAndRefractionState.w = rsqrt(reflectionAndRefractionState.w);
            directLightAccumulator.yzw = directLightAccumulator.yzw * reflectionAndRefractionState.www;
            reflectionAndRefractionState.w = abs(directLightAccumulator.y) + abs(directLightAccumulator.z);
            reflectionAndRefractionState.w = reflectionAndRefractionState.w + abs(directLightAccumulator.w);
            reflectionAndRefractionState.w = max(9.99999975e-05, reflectionAndRefractionState.w);
            reflectionAndRefractionState.w = rcp(reflectionAndRefractionState.w);
            transmissionState.xy = directLightAccumulator.yz * reflectionAndRefractionState.ww;
            transmissionState.zw = float2(1,1) + -abs(transmissionState.yx);
            forwardAndBehindState.xy = cmp(transmissionState.xy < float2(0,0));
            transmissionState.zw = forwardAndBehindState.xy ? -transmissionState.zw : transmissionState.zw;
            reflectionAndRefractionState.w = cmp(0 >= directLightAccumulator.w);
            transmissionState.xy = reflectionAndRefractionState.ww ? transmissionState.zw : transmissionState.xy;
            transmissionState.xy = float2(-2,2) + transmissionState.xy;
            reflectionAndRefractionState.w = max(abs(transmissionState.x), abs(transmissionState.y));
            reflectionAndRefractionState.w = cmp(reflectionAndRefractionState.w >= 1);
            transmissionState.xy = reflectionAndRefractionState.ww ? -transmissionState.xy : transmissionState.xy;
            transmissionState.xy = transmissionState.xy * float2(0.5,0.5) + float2(0.5,0.5);
            transmissionState.z = cb_reflections.vecProbes[reflectionAndRefractionState.y].fSlotIndex;
            transmissionState.xyzw = taReflection.SampleLevel(LinearMirrorMirror_s, transmissionState.xyz, materialSampleState.x).xyzw;
            reflectionAndRefractionState.w = transmissionState.w * transmissionState.w;
            reflectionAndRefractionState.w = reflectionAndRefractionState.w * 127.5 + 0.5;
            forwardAndBehindState.xyz = directLightAccumulator.yzw * reflectionAndRefractionState.www + cb_reflections.vecProbes[reflectionAndRefractionState.y].vPosition.xyz;
            gbufferAndPreviewState.xyz = -forwardAndBehindState.xyz + effectAnimationState.xyz;
            reflectionAndRefractionState.w = dot(gbufferAndPreviewState.xyz, gbufferAndPreviewState.xyz);
            forwardAndBehindState.xyz = cb_reflections.vecProbes[reflectionAndRefractionState.y].vGpuPosition.xyz + -forwardAndBehindState.xyz;
            forwardAndBehindState.xyz = -cb_reflections.vecProbes[reflectionAndRefractionState.y].vGpuExtents.xyz + abs(forwardAndBehindState.xyz);
            gbufferAndPreviewState.xyz = max(float3(0,0,0), forwardAndBehindState.xyz);
            transmissionState.w = dot(gbufferAndPreviewState.xyz, gbufferAndPreviewState.xyz);
            transmissionState.w = sqrt(transmissionState.w);
            forwardAndBehindState.x = max(forwardAndBehindState.x, forwardAndBehindState.y);
            forwardAndBehindState.x = max(forwardAndBehindState.x, forwardAndBehindState.z);
            forwardAndBehindState.x = min(0, forwardAndBehindState.x);
            transmissionState.w = forwardAndBehindState.x + transmissionState.w;
            transmissionState.w = -cb_reflections.vecProbes[reflectionAndRefractionState.y].fGpuMargin + transmissionState.w;
            reflectionAndRefractionState.y = saturate(cb_reflections.vecProbes[reflectionAndRefractionState.y].fGpuMarginRcp * -transmissionState.w);
            directLightAccumulator.y = dot(materialCoordinateState.yzw, directLightAccumulator.yzw);
            directLightAccumulator.y = directLightAccumulator.y * 0.5 + 0.5;
            directLightAccumulator.y = directLightAccumulator.y * directLightAccumulator.y;
            reflectionAndRefractionState.w = 0.000244140625 * reflectionAndRefractionState.w;
            reflectionAndRefractionState.w = min(1, reflectionAndRefractionState.w);
            reflectionAndRefractionState.w = 1 + -reflectionAndRefractionState.w;
            reflectionAndRefractionState.w = reflectionAndRefractionState.w * reflectionAndRefractionState.w;
            reflectionAndRefractionState.w = reflectionAndRefractionState.w * reflectionAndRefractionState.y;
            reflectionAndRefractionState.w = reflectionAndRefractionState.w * directLightAccumulator.y;
            reflectionAndRefractionState.w = reflectionAndRefractionState.w * reflectionAndRefractionState.z;
            reflectionAndRefractionState.w = reflectionAndRefractionState.w * 10 + 1;
            reflectionAndRefractionState.y = max(reflectionAndRefractionState.y, partPositionState.w);
            reflectionAndRefractionState.y = reflectionAndRefractionState.y * reflectionAndRefractionState.z;
            reflectionAndRefractionState.y = reflectionAndRefractionState.y * directLightAccumulator.y;
            reflectionAndRefractionState.y = reflectionAndRefractionState.w * reflectionAndRefractionState.y;
            reflectionAndRefractionState.z = reflectionAndRefractionState.y * directLightAccumulator.x;
            attenuationAndCookieState.w = reflectionAndRefractionState.y * directLightAccumulator.x + attenuationAndCookieState.w;
            reflectionAndRefractionState.y = cmp(0 < reflectionAndRefractionState.y);
            reflectionAndRefractionState.y = reflectionAndRefractionState.y ? 1.000000 : 0;
            shadowState.w = directLightAccumulator.x * reflectionAndRefractionState.y + shadowState.w;
            directLightAccumulator.xyz = transmissionState.xyz * reflectionAndRefractionState.zzz;
            lightGeometryState.xyz = directLightAccumulator.xyz * reflectionAndRefractionState.yyy + lightGeometryState.xyz;
          }
        }
      }
      profileMaterialState.xyz = lightGeometryState.xyz;
      lightIteratorState.xyz = shadowState.xyz;
      viewProjectionState.w = lightGeometryState.w;
      normalAndTangentState.w = attenuationAndCookieState.w;
      materialCoordinateState.x = shadowState.w;
    }
    partPositionState.w = max(0.125, normalAndTangentState.w);
    materialCoordinateState.yzw = profileMaterialState.xyz / partPositionState.www;
    partPositionState.w = max(0.00100000005, viewProjectionState.w);
    effectAnimationState.xyz = lightIteratorState.xyz / partPositionState.www;
    materialCoordinateState.x = saturate(materialCoordinateState.x);
    partPositionState.w = materialCoordinateState.x * materialCoordinateState.x;
    materialCoordinateState.xyz = -effectAnimationState.xyz + materialCoordinateState.yzw;
    materialCoordinateState.xyz = partPositionState.www * materialCoordinateState.xyz + effectAnimationState.xyz;
  } else {
    clusterMaskState.xyz = cb_vDirectionalLightColor.xyz;
    attenuationAndCookieState.xyz = float3(0,0,0);
    materialCoordinateState.xyz = float3(0,0,0);
  }
  materialCoordinateState.xyz = materialCoordinateState.xyz * partPositionState.zzz;
  effectAnimationState.xyz = attenuationAndCookieState.xyz + clusterMaskState.xyz;
  partPositionState.w = dot(v1.xyz, v1.xyz);
  partPositionState.w = sqrt(partPositionState.w);

  MainPartMultiWaterLighting result;
  result.directLight = effectAnimationState.xyz;
  result.reflection = materialCoordinateState.xyz;
  result.viewDistance = partPositionState.w;
  return result;
}

#endif

