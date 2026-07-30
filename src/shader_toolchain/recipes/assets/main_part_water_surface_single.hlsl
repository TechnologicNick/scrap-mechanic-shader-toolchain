#ifndef MAIN_PART_WATER_SURFACE_SINGLE_HLSL
#define MAIN_PART_WATER_SURFACE_SINGLE_HLSL

// Medium-quality single-probe transparent water evaluator.
// Phases:
// 1. Sample diffuse/ASG inputs and build view, normal, and Fresnel terms.
// 2. Sample the single reflection layer and optional frame refraction.
// 3. Decode the clustered ambient, point, and spot-light masks.
// 4. Accumulate cookie-aware lighting and emit color plus the auxiliary target.
//
struct MainPartSingleWaterForwardOutput
{
  float4 color;
  float4 gForward;
};

MainPartSingleWaterForwardOutput EvaluateMainPartSingleWaterSurface(
    float3 v1, float2 v2, float3 v3, float3 v4, float3 v5,
    float4 v6, float3 v7, float4 v8, uint v9)
{
  float4 partPositionState,animationTransformState,viewProjectionState,normalAndTangentState,materialCoordinateState,effectAnimationState,materialSampleState,profileMaterialState,clusterMaskState,lightIteratorState,lightGeometryState,attenuationAndCookieState,shadowState,reflectionAndRefractionState;
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
  normalAndTangentState.xyzw = tDif.SampleBias(LinearWrapWrap_s, v2.xy, cb_fMipBias).xyzw;
  normalAndTangentState.xyz = -v6.xyz + normalAndTangentState.xyz;
  normalAndTangentState.xyz = normalAndTangentState.www * normalAndTangentState.xyz + v6.xyz;
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
  normalAndTangentState.w = max(0.00999999978, normalAndTangentState.w);
  animationTransformState.x = 4 * animationTransformState.x;
  animationTransformState.xz = max(float2(0.100000001,0.00999999978), animationTransformState.xz);
  normalAndTangentState.w = log2(normalAndTangentState.w);
  animationTransformState.x = normalAndTangentState.w * animationTransformState.x;
  animationTransformState.x = exp2(animationTransformState.x);
  animationTransformState.x = min(1, animationTransformState.x);
  animationTransformState.x = 1 + -animationTransformState.x;
  animationTransformState.x = max(0.25, animationTransformState.x);
  animationTransformState.x = min(0.800000012, animationTransformState.x);
  normalAndTangentState.w = 0.995000005 * viewProjectionState.w;
  materialCoordinateState.x = -viewProjectionState.w * 0.995000005 + 1;
  partPositionState.w = abs(partPositionState.w) * abs(partPositionState.w) + -normalAndTangentState.w;
  normalAndTangentState.w = 1 / materialCoordinateState.x;
  partPositionState.w = saturate(normalAndTangentState.w * partPositionState.w);
  normalAndTangentState.w = partPositionState.w * -2 + 3;
  partPositionState.w = partPositionState.w * partPositionState.w;
  partPositionState.w = normalAndTangentState.w * partPositionState.w;
  partPositionState.w = saturate(partPositionState.w * viewProjectionState.w);
  animationTransformState.x = animationTransformState.x * animationTransformState.y + partPositionState.w;
  animationTransformState.x = saturate(animationTransformState.w * 0.25 + animationTransformState.x);
  animationTransformState.w = dot(-partPositionState.xyz, viewProjectionState.xyz);
  animationTransformState.w = animationTransformState.w + animationTransformState.w;
  partPositionState.xyz = viewProjectionState.xyz * -animationTransformState.www + -partPositionState.xyz;
  materialCoordinateState.xyz = viewToWorld._m01_m11_m21 * partPositionState.yyy;
  materialCoordinateState.xyz = viewToWorld._m00_m10_m20 * partPositionState.xxx + materialCoordinateState.xyz;
  partPositionState.xyz = viewToWorld._m02_m12_m22 * partPositionState.zzz + materialCoordinateState.xyz;
  animationTransformState.z = rsqrt(animationTransformState.z);
  animationTransformState.z = 1 / animationTransformState.z;
  animationTransformState.z = 5 * animationTransformState.z;
  animationTransformState.w = abs(partPositionState.x) + abs(partPositionState.y);
  animationTransformState.w = animationTransformState.w + abs(partPositionState.z);
  animationTransformState.w = max(9.99999975e-05, animationTransformState.w);
  animationTransformState.w = rcp(animationTransformState.w);
  partPositionState.xy = animationTransformState.ww * partPositionState.xy;
  materialCoordinateState.xy = float2(1,1) + -abs(partPositionState.yx);
  materialCoordinateState.zw = cmp(partPositionState.xy < float2(0,0));
  materialCoordinateState.xy = materialCoordinateState.zw ? -materialCoordinateState.xy : materialCoordinateState.xy;
  partPositionState.z = cmp(0 >= partPositionState.z);
  partPositionState.xy = partPositionState.zz ? materialCoordinateState.xy : partPositionState.xy;
  partPositionState.xy = float2(-2,2) + partPositionState.xy;
  partPositionState.z = max(abs(partPositionState.x), abs(partPositionState.y));
  partPositionState.z = cmp(partPositionState.z >= 1);
  partPositionState.xy = partPositionState.zz ? -partPositionState.xy : partPositionState.xy;
  partPositionState.xy = partPositionState.xy * float2(0.5,0.5) + float2(0.5,0.5);
  partPositionState.z = 0;
  partPositionState.xyz = taReflection.SampleLevel(LinearMirrorMirror_s, partPositionState.xyz, animationTransformState.z).xyz;
  animationTransformState.z = cmp(-v1.z < cb_cluster.fClusterMaxFarTotal);
  if (animationTransformState.z != 0) {
    animationTransformState.z = cb_vInverseCameraRange.x * -v1.z;
    materialCoordinateState.xyz = viewToWorld._m01_m11_m21 * v1.yyy;
    materialCoordinateState.xyz = viewToWorld._m00_m10_m20 * v1.xxx + materialCoordinateState.xyz;
    materialCoordinateState.xyz = viewToWorld._m02_m12_m22 * v1.zzz + materialCoordinateState.xyz;
    materialCoordinateState.xyz = viewToWorld._m03_m13_m23 + materialCoordinateState.xyz;
    effectAnimationState.xyz = ddx_coarse(materialCoordinateState.xyz);
    effectAnimationState.xyz = effectAnimationState.xyz + materialCoordinateState.xyz;
    materialSampleState.xyz = ddy_coarse(materialCoordinateState.xyz);
    effectAnimationState.xyz = materialSampleState.xyz + effectAnimationState.xyz;
    animationTransformState.z = saturate(6.66666651 * animationTransformState.z);
    animationTransformState.z = 1 + -animationTransformState.z;
    materialSampleState.xy = cb_vInvRenderScale.xy * v7.xy;
    animationTransformState.w = -v1.z * cb_cluster.fRcpClusterRange + cb_cluster.fClusterNearBias;
    animationTransformState.w = rsqrt(animationTransformState.w);
    animationTransformState.w = 1 / animationTransformState.w;
    animationTransformState.w = cb_cluster.vVoxelDims.z * animationTransformState.w;
    animationTransformState.w = floor(animationTransformState.w);
    animationTransformState.w = (uint)animationTransformState.w;
    materialSampleState.xy = cb_cluster.vVoxelDims.xy * materialSampleState.xy;
    materialSampleState.xy = (uint2)materialSampleState.xy;
    viewProjectionState.w = mad((int)materialSampleState.y, asint(cb_cluster.uClusterWidth), (int)materialSampleState.x);
    animationTransformState.w = mad((int)animationTransformState.w, asint(cb_cluster.uClusterSliceSize), (int)viewProjectionState.w);
    viewProjectionState.w = (int)animationTransformState.w * 33;
    viewProjectionState.w = sbVoxelLightIds[viewProjectionState.w].x;
    animationTransformState.w = mad((int)animationTransformState.w, 33, 1);
    materialSampleState.xyz = (int3)viewProjectionState.www & int3(255,0xff00,0xff0000);
    profileMaterialState.xyz = cb_vDirectionalLightColor.xyz;
    viewProjectionState.w = materialSampleState.x;
    while (true) {
      if (viewProjectionState.w == 0) break;
      normalAndTangentState.w = firstbitlow((uint)viewProjectionState.w);
      materialCoordinateState.w = (int)animationTransformState.w + (int)normalAndTangentState.w;
      effectAnimationState.w = 1 << (int)normalAndTangentState.w;
      viewProjectionState.w = (int)viewProjectionState.w ^ (int)effectAnimationState.w;
      materialCoordinateState.w = sbVoxelLightIds[materialCoordinateState.w].x;
      normalAndTangentState.w = (uint)normalAndTangentState.w << 5;
      clusterMaskState.xyz = profileMaterialState.xyz;
      effectAnimationState.w = materialCoordinateState.w;
      while (true) {
        if (effectAnimationState.w == 0) break;
        materialSampleState.w = firstbitlow((uint)effectAnimationState.w);
        profileMaterialState.w = (int)normalAndTangentState.w + (int)materialSampleState.w;
        materialSampleState.w = 1 << (int)materialSampleState.w;
        effectAnimationState.w = (int)effectAnimationState.w ^ (int)materialSampleState.w;
        materialSampleState.w = (uint)profileMaterialState.w << 1;
        lightIteratorState.xyz = cb_arrAmbient[materialSampleState.w].vPosition.xyz + -v1.xyz;
        profileMaterialState.w = dot(lightIteratorState.xyz, lightIteratorState.xyz);
        clusterMaskState.w = sqrt(profileMaterialState.w);
        clusterMaskState.w = saturate(cb_arrAmbient[materialSampleState.w].fRcpRadius * clusterMaskState.w);
        profileMaterialState.w = rsqrt(profileMaterialState.w);
        lightIteratorState.xyz = lightIteratorState.xyz * profileMaterialState.www;
        profileMaterialState.w = dot(lightIteratorState.xyz, viewProjectionState.xyz);
        profileMaterialState.w = abs(profileMaterialState.w) * 0.5 + 0.5;
        clusterMaskState.w = clusterMaskState.w * clusterMaskState.w;
        clusterMaskState.w = -clusterMaskState.w * clusterMaskState.w + 1;
        clusterMaskState.w = cb_arrAmbient[materialSampleState.w].fIntensity * clusterMaskState.w;
        clusterMaskState.w = clusterMaskState.w * animationTransformState.z;
        profileMaterialState.w = clusterMaskState.w * profileMaterialState.w;
        lightIteratorState.xyz = cb_arrAmbient[materialSampleState.w].vColor.xyz * profileMaterialState.www;
        clusterMaskState.xyz = max(lightIteratorState.xyz, clusterMaskState.xyz);
      }
      profileMaterialState.xyz = clusterMaskState.xyz;
    }
    clusterMaskState.xyz = profileMaterialState.xyz;
    lightIteratorState.xyz = float3(0,0,0);
    animationTransformState.z = materialSampleState.y;
    while (true) {
      if (animationTransformState.z == 0) break;
      viewProjectionState.w = firstbitlow((uint)animationTransformState.z);
      normalAndTangentState.w = (int)animationTransformState.w + (int)viewProjectionState.w;
      materialCoordinateState.w = 1 << (int)viewProjectionState.w;
      animationTransformState.z = (int)animationTransformState.z ^ (int)materialCoordinateState.w;
      normalAndTangentState.w = sbVoxelLightIds[normalAndTangentState.w].x;
      viewProjectionState.w = (uint)viewProjectionState.w << 5;
      lightGeometryState.xyz = clusterMaskState.xyz;
      attenuationAndCookieState.xyz = lightIteratorState.xyz;
      materialCoordinateState.w = normalAndTangentState.w;
      while (true) {
        if (materialCoordinateState.w == 0) break;
        effectAnimationState.w = firstbitlow((uint)materialCoordinateState.w);
        materialSampleState.x = (int)viewProjectionState.w + (int)effectAnimationState.w;
        effectAnimationState.w = 1 << (int)effectAnimationState.w;
        materialCoordinateState.w = (int)materialCoordinateState.w ^ (int)effectAnimationState.w;
        effectAnimationState.w = (uint)materialSampleState.x << 1;
        effectAnimationState.w = (int)effectAnimationState.w + -512;
        shadowState.xyz = cb_arrPoint[effectAnimationState.w].vPosition.xyz + -v1.xyz;
        materialSampleState.x = dot(shadowState.xyz, shadowState.xyz);
        materialSampleState.x = sqrt(materialSampleState.x);
        materialSampleState.w = saturate(cb_arrPoint[effectAnimationState.w].fRcpRadius * materialSampleState.x);
        materialSampleState.x = max(0.00100000005, materialSampleState.x);
        shadowState.xyz = shadowState.xyz / materialSampleState.xxx;
        materialSampleState.x = dot(shadowState.xyz, viewProjectionState.xyz);
        materialSampleState.x = abs(materialSampleState.x) * 0.75 + 0.25;
        materialSampleState.w = max(0.00999999978, materialSampleState.w);
        materialSampleState.w = log2(materialSampleState.w);
        materialSampleState.w = cb_arrPoint[effectAnimationState.w].fFalloffFactor * materialSampleState.w;
        materialSampleState.w = exp2(materialSampleState.w);
        materialSampleState.w = 1 + -materialSampleState.w;
        materialSampleState.w = cb_arrPoint[effectAnimationState.w].fIntensity * materialSampleState.w;
        materialSampleState.w = min(cb_arrPoint[effectAnimationState.w].fMaxIntensity, materialSampleState.w);
        profileMaterialState.w = asuint(cb_arrPoint[effectAnimationState.w].uColor) >> 24;
        profileMaterialState.w = (uint)profileMaterialState.w;
        shadowState.x = profileMaterialState.w * materialSampleState.x;
        if (8 == 0) reflectionAndRefractionState.x = 0; else if (8+16 < 32) {         reflectionAndRefractionState.x = (uint)cb_arrPoint[effectAnimationState.w].uColor << (32-(8 + 16)); reflectionAndRefractionState.x = (uint)reflectionAndRefractionState.x >> (32-8);        } else reflectionAndRefractionState.x = (uint)cb_arrPoint[effectAnimationState.w].uColor >> 16;
        if (8 == 0) reflectionAndRefractionState.y = 0; else if (8+8 < 32) {         reflectionAndRefractionState.y = (uint)cb_arrPoint[effectAnimationState.w].uColor << (32-(8 + 8)); reflectionAndRefractionState.y = (uint)reflectionAndRefractionState.y >> (32-8);        } else reflectionAndRefractionState.y = (uint)cb_arrPoint[effectAnimationState.w].uColor >> 8;
        reflectionAndRefractionState.xy = (uint2)reflectionAndRefractionState.xy;
        shadowState.yz = reflectionAndRefractionState.xy * materialSampleState.xx;
        shadowState.xyz = shadowState.xyz * materialSampleState.www;
        shadowState.xyz = float3(0.00392156886,0.00392156886,0.00392156886) * shadowState.xyz;
        effectAnimationState.w = 1 & asint(cb_arrPoint[effectAnimationState.w].uColor);
        reflectionAndRefractionState.xyz = max(float3(0,0,0), shadowState.xyz);
        reflectionAndRefractionState.xyz = reflectionAndRefractionState.xyz + attenuationAndCookieState.xyz;
        shadowState.xyz = max(shadowState.xyz, lightGeometryState.xyz);
        lightGeometryState.xyz = effectAnimationState.www ? lightGeometryState.xyz : shadowState.xyz;
        attenuationAndCookieState.xyz = effectAnimationState.www ? reflectionAndRefractionState.xyz : attenuationAndCookieState.xyz;
      }
      clusterMaskState.xyz = lightGeometryState.xyz;
      lightIteratorState.xyz = attenuationAndCookieState.xyz;
    }
    materialSampleState.xyw = clusterMaskState.xyz;
    profileMaterialState.xyz = lightIteratorState.xyz;
    animationTransformState.z = materialSampleState.z;
    while (true) {
      if (animationTransformState.z == 0) break;
      viewProjectionState.w = firstbitlow((uint)animationTransformState.z);
      normalAndTangentState.w = (int)animationTransformState.w + (int)viewProjectionState.w;
      materialCoordinateState.w = 1 << (int)viewProjectionState.w;
      animationTransformState.z = (int)animationTransformState.z ^ (int)materialCoordinateState.w;
      normalAndTangentState.w = sbVoxelLightIds[normalAndTangentState.w].x;
      viewProjectionState.w = (uint)viewProjectionState.w << 5;
      lightGeometryState.xyz = materialSampleState.xyw;
      attenuationAndCookieState.xyz = profileMaterialState.xyz;
      materialCoordinateState.w = normalAndTangentState.w;
      while (true) {
        if (materialCoordinateState.w == 0) break;
        effectAnimationState.w = firstbitlow((uint)materialCoordinateState.w);
        profileMaterialState.w = (int)viewProjectionState.w + (int)effectAnimationState.w;
        effectAnimationState.w = 1 << (int)effectAnimationState.w;
        materialCoordinateState.w = (int)materialCoordinateState.w ^ (int)effectAnimationState.w;
        effectAnimationState.w = mad((int)profileMaterialState.w, 9, -4608);
        shadowState.xyz = cb_arrSpot[effectAnimationState.w].vPosition.xyz + -v1.xyz;
        profileMaterialState.w = dot(shadowState.xyz, shadowState.xyz);
        profileMaterialState.w = sqrt(profileMaterialState.w);
        clusterMaskState.w = cb_arrSpot[effectAnimationState.w].fRcpRange * profileMaterialState.w;
        lightIteratorState.w = cmp(1 >= clusterMaskState.w);
        if (lightIteratorState.w != 0) {
          profileMaterialState.w = max(0.00100000005, profileMaterialState.w);
          shadowState.xyz = shadowState.xyz / profileMaterialState.www;
          profileMaterialState.w = dot(-shadowState.xyz, cb_arrSpot[effectAnimationState.w].vForward.xyz);
          lightIteratorState.w = cmp(0 < profileMaterialState.w);
          if (lightIteratorState.w != 0) {
            lightIteratorState.w = dot(shadowState.xyz, viewProjectionState.xyz);
            profileMaterialState.w = saturate(profileMaterialState.w * cb_arrSpot[effectAnimationState.w].fCutoffScale + cb_arrSpot[effectAnimationState.w].fCutoffOffset);
            shadowState.xy = int2(240,1) & asint(cb_arrSpot[effectAnimationState.w].uColor);
            if (shadowState.x != 0) {
              shadowState.xzw = cb_arrSpot[effectAnimationState.w].xClip._m01_m11_m31 * materialCoordinateState.yyy;
              shadowState.xzw = cb_arrSpot[effectAnimationState.w].xClip._m00_m10_m30 * materialCoordinateState.xxx + shadowState.xzw;
              shadowState.xzw = cb_arrSpot[effectAnimationState.w].xClip._m02_m12_m32 * materialCoordinateState.zzz + shadowState.xzw;
              shadowState.xzw = cb_arrSpot[effectAnimationState.w].xClip._m03_m13_m33 + shadowState.xzw;
              shadowState.xz = shadowState.xz / shadowState.ww;
              reflectionAndRefractionState.xy = shadowState.xz * float2(0.5,0.5) + float2(0.5,0.5);
              shadowState.xzw = cb_arrSpot[effectAnimationState.w].xClip._m01_m11_m31 * effectAnimationState.yyy;
              shadowState.xzw = cb_arrSpot[effectAnimationState.w].xClip._m00_m10_m30 * effectAnimationState.xxx + shadowState.xzw;
              shadowState.xzw = cb_arrSpot[effectAnimationState.w].xClip._m02_m12_m32 * effectAnimationState.zzz + shadowState.xzw;
              shadowState.xzw = cb_arrSpot[effectAnimationState.w].xClip._m03_m13_m33 + shadowState.xzw;
              shadowState.xz = shadowState.xz / shadowState.ww;
              shadowState.xz = shadowState.xz * float2(0.5,0.5) + float2(0.5,0.5);
              shadowState.xz = reflectionAndRefractionState.xy + -shadowState.xz;
              if (4 == 0) lightGeometryState.w = 0; else if (4+4 < 32) {               lightGeometryState.w = (uint)cb_arrSpot[effectAnimationState.w].uColor << (32-(4 + 4)); lightGeometryState.w = (uint)lightGeometryState.w >> (32-4);              } else lightGeometryState.w = (uint)cb_arrSpot[effectAnimationState.w].uColor >> 4;
              lightGeometryState.w = (int)lightGeometryState.w + -1;
              reflectionAndRefractionState.z = (uint)lightGeometryState.w;
              lightGeometryState.w = taCookies.SampleGrad(LinearClampClamp_s, reflectionAndRefractionState.xyz, shadowState.x, shadowState.z).x;
              profileMaterialState.w = lightGeometryState.w * profileMaterialState.w;
            }
            lightGeometryState.w = cmp(0 < profileMaterialState.w);
            clusterMaskState.w = max(0.00999999978, clusterMaskState.w);
            clusterMaskState.w = log2(clusterMaskState.w);
            clusterMaskState.w = cb_arrSpot[effectAnimationState.w].fFalloffFactor * clusterMaskState.w;
            clusterMaskState.w = exp2(clusterMaskState.w);
            clusterMaskState.w = 1 + -clusterMaskState.w;
            clusterMaskState.w = cb_arrSpot[effectAnimationState.w].fIntensity * clusterMaskState.w;
            profileMaterialState.w = clusterMaskState.w * profileMaterialState.w;
            profileMaterialState.w = min(cb_arrSpot[effectAnimationState.w].fMaxIntensity, profileMaterialState.w);
            clusterMaskState.w = abs(lightIteratorState.w) * 0.75 + 0.25;
            lightIteratorState.w = asuint(cb_arrSpot[effectAnimationState.w].uColor) >> 24;
            lightIteratorState.w = (uint)lightIteratorState.w;
            reflectionAndRefractionState.x = lightIteratorState.w * clusterMaskState.w;
            if (8 == 0) shadowState.x = 0; else if (8+16 < 32) {             shadowState.x = (uint)cb_arrSpot[effectAnimationState.w].uColor << (32-(8 + 16)); shadowState.x = (uint)shadowState.x >> (32-8);            } else shadowState.x = (uint)cb_arrSpot[effectAnimationState.w].uColor >> 16;
            if (8 == 0) shadowState.z = 0; else if (8+8 < 32) {             shadowState.z = (uint)cb_arrSpot[effectAnimationState.w].uColor << (32-(8 + 8)); shadowState.z = (uint)shadowState.z >> (32-8);            } else shadowState.z = (uint)cb_arrSpot[effectAnimationState.w].uColor >> 8;
            shadowState.xz = (uint2)shadowState.xz;
            reflectionAndRefractionState.yz = shadowState.xz * clusterMaskState.ww;
            shadowState.xzw = reflectionAndRefractionState.xyz * profileMaterialState.www;
            shadowState.xzw = float3(0.00392156886,0.00392156886,0.00392156886) * shadowState.xzw;
            reflectionAndRefractionState.xyz = max(float3(0,0,0), shadowState.xzw);
            reflectionAndRefractionState.xyz = reflectionAndRefractionState.xyz + attenuationAndCookieState.xyz;
            shadowState.xzw = max(shadowState.xzw, lightGeometryState.xyz);
            shadowState.xzw = shadowState.yyy ? lightGeometryState.xyz : shadowState.xzw;
            reflectionAndRefractionState.xyz = shadowState.yyy ? reflectionAndRefractionState.xyz : attenuationAndCookieState.xyz;
            lightGeometryState.xyz = lightGeometryState.www ? shadowState.xzw : lightGeometryState.xyz;
            attenuationAndCookieState.xyz = lightGeometryState.www ? reflectionAndRefractionState.xyz : attenuationAndCookieState.xyz;
          }
        }
      }
      materialSampleState.xyw = lightGeometryState.xyz;
      profileMaterialState.xyz = attenuationAndCookieState.xyz;
    }
  } else {
    materialSampleState.xyw = cb_vDirectionalLightColor.xyz;
    profileMaterialState.xyz = float3(0,0,0);
  }
  viewProjectionState.xyz = profileMaterialState.xyz + materialSampleState.xyw;
  normalAndTangentState.xyz = normalAndTangentState.xyz * viewProjectionState.xyz;
  partPositionState.xyz = partPositionState.xyz * animationTransformState.yyy + -normalAndTangentState.xyz;
  partPositionState.xyz = animationTransformState.yyy * partPositionState.xyz + normalAndTangentState.xyz;
  partPositionState.xyz = viewProjectionState.xyz * partPositionState.www + partPositionState.xyz;
  partPositionState.w = cmp(0.00100000005 < animationTransformState.x);
  if (partPositionState.w != 0) {
    animationTransformState.yzw = tFrame.Sample(LinearClampClamp_s, v7.xy).xyz;
    viewProjectionState.xyz = -animationTransformState.yzw + partPositionState.xyz;
    partPositionState.xyz = animationTransformState.xxx * viewProjectionState.xyz + animationTransformState.yzw;
  }
  animationTransformState.xyz = v8.xyz + -partPositionState.xyz;
  MainPartSingleWaterForwardOutput result;
  result.color.xyz = v8.www * animationTransformState.xyz + partPositionState.xyz;
  result.color.w = 1;
  result.gForward = float4(0,0,0,1);
  return result;
}

#endif // MAIN_PART_WATER_SURFACE_SINGLE_HLSL
