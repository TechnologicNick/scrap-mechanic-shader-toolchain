// Shared high-quality water backend: single-probe reflection, clustered
// ambient/point/spot lighting, cookies, shadows, and indirect normalization.

struct MainPartWaterHighLightingInput
{
  float3 viewPosition;
  float2 screenUv;
  float3 normalView;
  float2 foldedReflectionUv;
  float2 unfoldedReflectionUv;
  bool reflectionHemisphere;
  float reflectionMip;
  float reflectionStrength;
};

struct MainPartWaterHighLighting
{
  float3 directLight;
  float3 reflection;
  float3 indirectLight;
  float3 weightedIndirectLight;
  float indirectDistanceWeight;
};

MainPartWaterHighLighting EvaluateMainPartWaterHighLighting(
    MainPartWaterHighLightingInput input)
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

  float3 v1 = input.viewPosition;
  float3 v7 = float3(input.screenUv, 0.0);
  viewProjectionState.xyz = input.normalView;
  materialCoordinateState.xy = input.foldedReflectionUv;
  animationTransformState.zw = input.unfoldedReflectionUv;
  viewProjectionState.w = input.reflectionHemisphere;
  partPositionState.z = input.reflectionMip;
  animationTransformState.y = input.reflectionStrength;
  animationTransformState.zw = viewProjectionState.ww ? materialCoordinateState.xy : animationTransformState.zw;
  animationTransformState.zw = float2(-2,2) + animationTransformState.zw;
  viewProjectionState.w = max(abs(animationTransformState.z), abs(animationTransformState.w));
  viewProjectionState.w = cmp(viewProjectionState.w >= 1);
  animationTransformState.zw = viewProjectionState.ww ? -animationTransformState.zw : animationTransformState.zw;
  materialCoordinateState.xy = animationTransformState.zw * float2(0.5,0.5) + float2(0.5,0.5);
  materialCoordinateState.z = 0;
  materialCoordinateState.xyz = taReflection.SampleLevel(LinearMirrorMirror_s, materialCoordinateState.xyz, partPositionState.z).xyz;
  materialCoordinateState.xyz = materialCoordinateState.xyz * animationTransformState.yyy;
  partPositionState.z = cmp(-v1.z < cb_cluster.fClusterMaxFarTotal);
  if (partPositionState.z != 0) {
    partPositionState.z = cb_vInverseCameraRange.x * -v1.z;
    effectAnimationState.xyz = viewToWorld._m01_m11_m21 * v1.yyy;
    effectAnimationState.xyz = viewToWorld._m00_m10_m20 * v1.xxx + effectAnimationState.xyz;
    effectAnimationState.xyz = viewToWorld._m02_m12_m22 * v1.zzz + effectAnimationState.xyz;
    effectAnimationState.xyz = viewToWorld._m03_m13_m23 + effectAnimationState.xyz;
    materialSampleState.xyz = ddx_coarse(effectAnimationState.xyz);
    materialSampleState.xyz = materialSampleState.xyz + effectAnimationState.xyz;
    profileMaterialState.xyz = ddy_coarse(effectAnimationState.xyz);
    materialSampleState.xyz = profileMaterialState.xyz + materialSampleState.xyz;
    partPositionState.z = saturate(6.66666651 * partPositionState.z);
    partPositionState.z = 1 + -partPositionState.z;
    animationTransformState.zw = cb_vInvRenderScale.xy * v7.xy;
    viewProjectionState.w = -v1.z * cb_cluster.fRcpClusterRange + cb_cluster.fClusterNearBias;
    viewProjectionState.w = rsqrt(viewProjectionState.w);
    viewProjectionState.w = 1 / viewProjectionState.w;
    viewProjectionState.w = cb_cluster.vVoxelDims.z * viewProjectionState.w;
    viewProjectionState.w = floor(viewProjectionState.w);
    viewProjectionState.w = (uint)viewProjectionState.w;
    animationTransformState.zw = cb_cluster.vVoxelDims.xy * animationTransformState.zw;
    animationTransformState.zw = (uint2)animationTransformState.zw;
    animationTransformState.z = mad((int)animationTransformState.w, asint(cb_cluster.uClusterWidth), (int)animationTransformState.z);
    animationTransformState.z = mad((int)viewProjectionState.w, asint(cb_cluster.uClusterSliceSize), (int)animationTransformState.z);
    animationTransformState.w = (int)animationTransformState.z * 33;
    animationTransformState.w = sbVoxelLightIds[animationTransformState.w].x;
    animationTransformState.z = mad((int)animationTransformState.z, 33, 1);
    profileMaterialState.xyz = (int3)animationTransformState.www & int3(255,0xff00,0xff0000);
    clusterMaskState.xyz = cb_vDirectionalLightColor.xyz;
    animationTransformState.w = profileMaterialState.x;
    while (true) {
      if (animationTransformState.w == 0) break;
      viewProjectionState.w = firstbitlow((uint)animationTransformState.w);
      materialCoordinateState.w = (int)animationTransformState.z + (int)viewProjectionState.w;
      effectAnimationState.w = 1 << (int)viewProjectionState.w;
      animationTransformState.w = (int)animationTransformState.w ^ (int)effectAnimationState.w;
      materialCoordinateState.w = sbVoxelLightIds[materialCoordinateState.w].x;
      viewProjectionState.w = (uint)viewProjectionState.w << 5;
      lightIteratorState.xyz = clusterMaskState.xyz;
      effectAnimationState.w = materialCoordinateState.w;
      while (true) {
        if (effectAnimationState.w == 0) break;
        materialSampleState.w = firstbitlow((uint)effectAnimationState.w);
        profileMaterialState.w = (int)viewProjectionState.w + (int)materialSampleState.w;
        materialSampleState.w = 1 << (int)materialSampleState.w;
        effectAnimationState.w = (int)effectAnimationState.w ^ (int)materialSampleState.w;
        materialSampleState.w = (uint)profileMaterialState.w << 1;
        lightGeometryState.xyz = cb_arrAmbient[materialSampleState.w].vPosition.xyz + -v1.xyz;
        profileMaterialState.w = dot(lightGeometryState.xyz, lightGeometryState.xyz);
        clusterMaskState.w = sqrt(profileMaterialState.w);
        clusterMaskState.w = saturate(cb_arrAmbient[materialSampleState.w].fRcpRadius * clusterMaskState.w);
        profileMaterialState.w = rsqrt(profileMaterialState.w);
        lightGeometryState.xyz = lightGeometryState.xyz * profileMaterialState.www;
        profileMaterialState.w = dot(lightGeometryState.xyz, viewProjectionState.xyz);
        profileMaterialState.w = abs(profileMaterialState.w) * 0.5 + 0.5;
        clusterMaskState.w = clusterMaskState.w * clusterMaskState.w;
        clusterMaskState.w = -clusterMaskState.w * clusterMaskState.w + 1;
        clusterMaskState.w = cb_arrAmbient[materialSampleState.w].fIntensity * clusterMaskState.w;
        clusterMaskState.w = clusterMaskState.w * partPositionState.z;
        profileMaterialState.w = clusterMaskState.w * profileMaterialState.w;
        lightGeometryState.xyz = cb_arrAmbient[materialSampleState.w].vColor.xyz * profileMaterialState.www;
        lightIteratorState.xyz = max(lightGeometryState.xyz, lightIteratorState.xyz);
      }
      clusterMaskState.xyz = lightIteratorState.xyz;
    }
    lightIteratorState.xyz = clusterMaskState.xyz;
    lightGeometryState.xyz = float3(0,0,0);
    partPositionState.z = profileMaterialState.y;
    while (true) {
      if (partPositionState.z == 0) break;
      animationTransformState.w = firstbitlow((uint)partPositionState.z);
      viewProjectionState.w = (int)animationTransformState.w + (int)animationTransformState.z;
      materialCoordinateState.w = 1 << (int)animationTransformState.w;
      partPositionState.z = (int)partPositionState.z ^ (int)materialCoordinateState.w;
      viewProjectionState.w = sbVoxelLightIds[viewProjectionState.w].x;
      animationTransformState.w = (uint)animationTransformState.w << 5;
      attenuationAndCookieState.xyz = lightIteratorState.xyz;
      shadowState.xyz = lightGeometryState.xyz;
      materialCoordinateState.w = viewProjectionState.w;
      while (true) {
        if (materialCoordinateState.w == 0) break;
        effectAnimationState.w = firstbitlow((uint)materialCoordinateState.w);
        materialSampleState.w = (int)animationTransformState.w + (int)effectAnimationState.w;
        effectAnimationState.w = 1 << (int)effectAnimationState.w;
        materialCoordinateState.w = (int)materialCoordinateState.w ^ (int)effectAnimationState.w;
        effectAnimationState.w = (uint)materialSampleState.w << 1;
        effectAnimationState.w = (int)effectAnimationState.w + -512;
        reflectionAndRefractionState.xyz = cb_arrPoint[effectAnimationState.w].vPosition.xyz + -v1.xyz;
        materialSampleState.w = dot(reflectionAndRefractionState.xyz, reflectionAndRefractionState.xyz);
        materialSampleState.w = sqrt(materialSampleState.w);
        profileMaterialState.x = saturate(cb_arrPoint[effectAnimationState.w].fRcpRadius * materialSampleState.w);
        materialSampleState.w = max(0.00100000005, materialSampleState.w);
        reflectionAndRefractionState.xyz = reflectionAndRefractionState.xyz / materialSampleState.www;
        materialSampleState.w = dot(reflectionAndRefractionState.xyz, viewProjectionState.xyz);
        materialSampleState.w = abs(materialSampleState.w) * 0.75 + 0.25;
        profileMaterialState.x = max(0.00999999978, profileMaterialState.x);
        profileMaterialState.x = log2(profileMaterialState.x);
        profileMaterialState.x = cb_arrPoint[effectAnimationState.w].fFalloffFactor * profileMaterialState.x;
        profileMaterialState.x = exp2(profileMaterialState.x);
        profileMaterialState.x = 1 + -profileMaterialState.x;
        profileMaterialState.x = cb_arrPoint[effectAnimationState.w].fIntensity * profileMaterialState.x;
        profileMaterialState.x = min(cb_arrPoint[effectAnimationState.w].fMaxIntensity, profileMaterialState.x);
        profileMaterialState.w = asuint(cb_arrPoint[effectAnimationState.w].uColor) >> 24;
        profileMaterialState.w = (uint)profileMaterialState.w;
        reflectionAndRefractionState.x = profileMaterialState.w * materialSampleState.w;
        if (8 == 0) directLightAccumulator.x = 0; else if (8+16 < 32) {         directLightAccumulator.x = (uint)cb_arrPoint[effectAnimationState.w].uColor << (32-(8 + 16)); directLightAccumulator.x = (uint)directLightAccumulator.x >> (32-8);        } else directLightAccumulator.x = (uint)cb_arrPoint[effectAnimationState.w].uColor >> 16;
        if (8 == 0) directLightAccumulator.y = 0; else if (8+8 < 32) {         directLightAccumulator.y = (uint)cb_arrPoint[effectAnimationState.w].uColor << (32-(8 + 8)); directLightAccumulator.y = (uint)directLightAccumulator.y >> (32-8);        } else directLightAccumulator.y = (uint)cb_arrPoint[effectAnimationState.w].uColor >> 8;
        directLightAccumulator.xy = (uint2)directLightAccumulator.xy;
        reflectionAndRefractionState.yz = directLightAccumulator.xy * materialSampleState.ww;
        reflectionAndRefractionState.xyz = reflectionAndRefractionState.xyz * profileMaterialState.xxx;
        reflectionAndRefractionState.xyz = float3(0.00392156886,0.00392156886,0.00392156886) * reflectionAndRefractionState.xyz;
        effectAnimationState.w = 1 & asint(cb_arrPoint[effectAnimationState.w].uColor);
        directLightAccumulator.xyz = max(float3(0,0,0), reflectionAndRefractionState.xyz);
        directLightAccumulator.xyz = directLightAccumulator.xyz + shadowState.xyz;
        reflectionAndRefractionState.xyz = max(reflectionAndRefractionState.xyz, attenuationAndCookieState.xyz);
        attenuationAndCookieState.xyz = effectAnimationState.www ? attenuationAndCookieState.xyz : reflectionAndRefractionState.xyz;
        shadowState.xyz = effectAnimationState.www ? directLightAccumulator.xyz : shadowState.xyz;
      }
      lightIteratorState.xyz = attenuationAndCookieState.xyz;
      lightGeometryState.xyz = shadowState.xyz;
    }
    profileMaterialState.xyw = lightIteratorState.xyz;
    clusterMaskState.xyz = lightGeometryState.xyz;
    partPositionState.z = profileMaterialState.z;
    while (true) {
      if (partPositionState.z == 0) break;
      animationTransformState.w = firstbitlow((uint)partPositionState.z);
      viewProjectionState.w = (int)animationTransformState.w + (int)animationTransformState.z;
      materialCoordinateState.w = 1 << (int)animationTransformState.w;
      partPositionState.z = (int)partPositionState.z ^ (int)materialCoordinateState.w;
      viewProjectionState.w = sbVoxelLightIds[viewProjectionState.w].x;
      animationTransformState.w = (uint)animationTransformState.w << 5;
      attenuationAndCookieState.xyz = profileMaterialState.xyw;
      shadowState.xyz = clusterMaskState.xyz;
      materialCoordinateState.w = viewProjectionState.w;
      while (true) {
        if (materialCoordinateState.w == 0) break;
        effectAnimationState.w = firstbitlow((uint)materialCoordinateState.w);
        materialSampleState.w = (int)animationTransformState.w + (int)effectAnimationState.w;
        effectAnimationState.w = 1 << (int)effectAnimationState.w;
        materialCoordinateState.w = (int)materialCoordinateState.w ^ (int)effectAnimationState.w;
        effectAnimationState.w = mad((int)materialSampleState.w, 9, -4608);
        reflectionAndRefractionState.xyz = cb_arrSpot[effectAnimationState.w].vPosition.xyz + -v1.xyz;
        materialSampleState.w = dot(reflectionAndRefractionState.xyz, reflectionAndRefractionState.xyz);
        materialSampleState.w = sqrt(materialSampleState.w);
        clusterMaskState.w = cb_arrSpot[effectAnimationState.w].fRcpRange * materialSampleState.w;
        lightIteratorState.w = cmp(1 >= clusterMaskState.w);
        if (lightIteratorState.w != 0) {
          materialSampleState.w = max(0.00100000005, materialSampleState.w);
          reflectionAndRefractionState.xyz = reflectionAndRefractionState.xyz / materialSampleState.www;
          materialSampleState.w = dot(-reflectionAndRefractionState.xyz, cb_arrSpot[effectAnimationState.w].vForward.xyz);
          lightIteratorState.w = cmp(0 < materialSampleState.w);
          if (lightIteratorState.w != 0) {
            lightIteratorState.w = dot(reflectionAndRefractionState.xyz, viewProjectionState.xyz);
            materialSampleState.w = saturate(materialSampleState.w * cb_arrSpot[effectAnimationState.w].fCutoffScale + cb_arrSpot[effectAnimationState.w].fCutoffOffset);
            reflectionAndRefractionState.xy = int2(240,1) & asint(cb_arrSpot[effectAnimationState.w].uColor);
            if (reflectionAndRefractionState.x != 0) {
              reflectionAndRefractionState.xzw = cb_arrSpot[effectAnimationState.w].xClip._m01_m11_m31 * effectAnimationState.yyy;
              reflectionAndRefractionState.xzw = cb_arrSpot[effectAnimationState.w].xClip._m00_m10_m30 * effectAnimationState.xxx + reflectionAndRefractionState.xzw;
              reflectionAndRefractionState.xzw = cb_arrSpot[effectAnimationState.w].xClip._m02_m12_m32 * effectAnimationState.zzz + reflectionAndRefractionState.xzw;
              reflectionAndRefractionState.xzw = cb_arrSpot[effectAnimationState.w].xClip._m03_m13_m33 + reflectionAndRefractionState.xzw;
              reflectionAndRefractionState.xz = reflectionAndRefractionState.xz / reflectionAndRefractionState.ww;
              directLightAccumulator.xy = reflectionAndRefractionState.xz * float2(0.5,0.5) + float2(0.5,0.5);
              reflectionAndRefractionState.xzw = cb_arrSpot[effectAnimationState.w].xClip._m01_m11_m31 * materialSampleState.yyy;
              reflectionAndRefractionState.xzw = cb_arrSpot[effectAnimationState.w].xClip._m00_m10_m30 * materialSampleState.xxx + reflectionAndRefractionState.xzw;
              reflectionAndRefractionState.xzw = cb_arrSpot[effectAnimationState.w].xClip._m02_m12_m32 * materialSampleState.zzz + reflectionAndRefractionState.xzw;
              reflectionAndRefractionState.xzw = cb_arrSpot[effectAnimationState.w].xClip._m03_m13_m33 + reflectionAndRefractionState.xzw;
              reflectionAndRefractionState.xz = reflectionAndRefractionState.xz / reflectionAndRefractionState.ww;
              reflectionAndRefractionState.xz = reflectionAndRefractionState.xz * float2(0.5,0.5) + float2(0.5,0.5);
              reflectionAndRefractionState.xz = directLightAccumulator.xy + -reflectionAndRefractionState.xz;
              if (4 == 0) lightGeometryState.w = 0; else if (4+4 < 32) {               lightGeometryState.w = (uint)cb_arrSpot[effectAnimationState.w].uColor << (32-(4 + 4)); lightGeometryState.w = (uint)lightGeometryState.w >> (32-4);              } else lightGeometryState.w = (uint)cb_arrSpot[effectAnimationState.w].uColor >> 4;
              lightGeometryState.w = (int)lightGeometryState.w + -1;
              directLightAccumulator.z = (uint)lightGeometryState.w;
              lightGeometryState.w = taCookies.SampleGrad(LinearClampClamp_s, directLightAccumulator.xyz, reflectionAndRefractionState.x, reflectionAndRefractionState.z).x;
              materialSampleState.w = lightGeometryState.w * materialSampleState.w;
            }
            lightGeometryState.w = cmp(0 < materialSampleState.w);
            clusterMaskState.w = max(0.00999999978, clusterMaskState.w);
            clusterMaskState.w = log2(clusterMaskState.w);
            clusterMaskState.w = cb_arrSpot[effectAnimationState.w].fFalloffFactor * clusterMaskState.w;
            clusterMaskState.w = exp2(clusterMaskState.w);
            clusterMaskState.w = 1 + -clusterMaskState.w;
            clusterMaskState.w = cb_arrSpot[effectAnimationState.w].fIntensity * clusterMaskState.w;
            materialSampleState.w = clusterMaskState.w * materialSampleState.w;
            materialSampleState.w = min(cb_arrSpot[effectAnimationState.w].fMaxIntensity, materialSampleState.w);
            clusterMaskState.w = abs(lightIteratorState.w) * 0.75 + 0.25;
            lightIteratorState.w = asuint(cb_arrSpot[effectAnimationState.w].uColor) >> 24;
            lightIteratorState.w = (uint)lightIteratorState.w;
            directLightAccumulator.x = lightIteratorState.w * clusterMaskState.w;
            if (8 == 0) reflectionAndRefractionState.x = 0; else if (8+16 < 32) {             reflectionAndRefractionState.x = (uint)cb_arrSpot[effectAnimationState.w].uColor << (32-(8 + 16)); reflectionAndRefractionState.x = (uint)reflectionAndRefractionState.x >> (32-8);            } else reflectionAndRefractionState.x = (uint)cb_arrSpot[effectAnimationState.w].uColor >> 16;
            if (8 == 0) reflectionAndRefractionState.z = 0; else if (8+8 < 32) {             reflectionAndRefractionState.z = (uint)cb_arrSpot[effectAnimationState.w].uColor << (32-(8 + 8)); reflectionAndRefractionState.z = (uint)reflectionAndRefractionState.z >> (32-8);            } else reflectionAndRefractionState.z = (uint)cb_arrSpot[effectAnimationState.w].uColor >> 8;
            reflectionAndRefractionState.xz = (uint2)reflectionAndRefractionState.xz;
            directLightAccumulator.yz = reflectionAndRefractionState.xz * clusterMaskState.ww;
            reflectionAndRefractionState.xzw = directLightAccumulator.xyz * materialSampleState.www;
            reflectionAndRefractionState.xzw = float3(0.00392156886,0.00392156886,0.00392156886) * reflectionAndRefractionState.xzw;
            directLightAccumulator.xyz = max(float3(0,0,0), reflectionAndRefractionState.xzw);
            directLightAccumulator.xyz = directLightAccumulator.xyz + shadowState.xyz;
            reflectionAndRefractionState.xzw = max(reflectionAndRefractionState.xzw, attenuationAndCookieState.xyz);
            reflectionAndRefractionState.xzw = reflectionAndRefractionState.yyy ? attenuationAndCookieState.xyz : reflectionAndRefractionState.xzw;
            directLightAccumulator.xyz = reflectionAndRefractionState.yyy ? directLightAccumulator.xyz : shadowState.xyz;
            attenuationAndCookieState.xyz = lightGeometryState.www ? reflectionAndRefractionState.xzw : attenuationAndCookieState.xyz;
            shadowState.xyz = lightGeometryState.www ? directLightAccumulator.xyz : shadowState.xyz;
          }
        }
      }
      profileMaterialState.xyw = attenuationAndCookieState.xyz;
      clusterMaskState.xyz = shadowState.xyz;
    }
  } else {
    profileMaterialState.xyw = cb_vDirectionalLightColor.xyz;
    clusterMaskState.xyz = float3(0,0,0);
  }
  effectAnimationState.xyz = clusterMaskState.xyz + profileMaterialState.xyw;
  partPositionState.z = dot(v1.xyz, v1.xyz);
  partPositionState.z = sqrt(partPositionState.z);
  materialSampleState.xyz = tIndirect.SampleLevel(PointClampClamp_s, v7.xy, 0).xyz;
  animationTransformState.z = dot(materialSampleState.xyz, float3(0.298999995,0.587000012,0.114));
  materialSampleState.xyz = float3(1.13,1.13,1.13) * materialSampleState.xyz;
  animationTransformState.z = animationTransformState.z * 0.200000003 + 1.39999998;
  materialSampleState.xyz = materialSampleState.xyz * animationTransformState.zzz;
  animationTransformState.z = dot(materialSampleState.xyz, float3(0.333333343,0.333333343,0.333333343));
  viewProjectionState.zw = float2(1.5,-6) + partPositionState.zz;
  viewProjectionState.zw = float2(0.00999999978,0.166666672) * viewProjectionState.wz;
  partPositionState.z = min(1, viewProjectionState.w);
  viewProjectionState.z = saturate(viewProjectionState.z);
  partPositionState.z = partPositionState.z * 1.25 + viewProjectionState.z;
  profileMaterialState.xyz = materialSampleState.xyz * partPositionState.zzz;
  animationTransformState.z = animationTransformState.z * animationTransformState.z;
  animationTransformState.z = 4 * animationTransformState.z;
  clusterMaskState.xyz = materialSampleState.xyz * partPositionState.zzz + -materialCoordinateState.xyz;
  materialCoordinateState.xyz = animationTransformState.zzz * clusterMaskState.xyz + materialCoordinateState.xyz;

  MainPartWaterHighLighting result;
  result.directLight = effectAnimationState.xyz;
  result.reflection = materialCoordinateState.xyz;
  result.indirectLight = materialSampleState.xyz;
  result.weightedIndirectLight = profileMaterialState.xyz;
  result.indirectDistanceWeight = partPositionState.z;
  return result;
}
