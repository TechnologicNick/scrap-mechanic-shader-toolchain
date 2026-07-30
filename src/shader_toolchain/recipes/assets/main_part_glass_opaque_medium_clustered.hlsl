// Instruction-sensitive clustered point/spot kernel used by opaque glass.
// The traversal stays in recovered DXBC order, but all state crossing this
// boundary is expressed in material/lighting terms rather than registers.

struct MainPartOpaqueGlassClusterInput
{
  float3 viewPosition;
  float2 screenUv;
  float3 normalView;
  float3 viewDirection;
  float glossExponent;
  float specularScale;
  float3 directionalColor;
  float directionalTransmission;
  float directionalSpecular;
};

struct MainPartOpaqueGlassClusterLighting
{
  float3 maxLightColor;
  float3 additiveLightColor;
  float maximumTransmission;
  float maximumSpecular;
};

MainPartOpaqueGlassClusterLighting EvaluateMainPartOpaqueGlassCluster(
    MainPartOpaqueGlassClusterInput input)
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

  float3 v1 = input.viewPosition;
  float3 v7 = float3(input.screenUv, 0.0);
  partPositionState.x = rsqrt(dot(-v1, -v1));
  partPositionState.yzw = input.viewDirection;
  viewProjectionState.xyz = input.normalView;
  viewProjectionState.w = input.glossExponent;
  animationTransformState.z = input.specularScale;
  materialCoordinateState.xzw = input.directionalColor;
  normalAndTangentState.w = input.directionalTransmission;
  materialCoordinateState.y = input.directionalSpecular;

  effectAnimationState.x = cmp(-v1.z < cb_cluster.fClusterMaxFarTotal);
  if (effectAnimationState.x != 0) {
    effectAnimationState.xyz = viewToWorld._m01_m11_m21 * v1.yyy;
    effectAnimationState.xyz = viewToWorld._m00_m10_m20 * v1.xxx + effectAnimationState.xyz;
    effectAnimationState.xyz = viewToWorld._m02_m12_m22 * v1.zzz + effectAnimationState.xyz;
    effectAnimationState.xyz = viewToWorld._m03_m13_m23 + effectAnimationState.xyz;
    materialSampleState.xyz = ddx_coarse(effectAnimationState.xyz);
    materialSampleState.xyz = materialSampleState.xyz + effectAnimationState.xyz;
    profileMaterialState.xyz = ddy_coarse(effectAnimationState.xyz);
    materialSampleState.xyz = profileMaterialState.xyz + materialSampleState.xyz;
    profileMaterialState.xy = cb_vInvRenderScale.xy * v7.xy;
    effectAnimationState.w = -v1.z * cb_cluster.fRcpClusterRange + cb_cluster.fClusterNearBias;
    effectAnimationState.w = rsqrt(effectAnimationState.w);
    effectAnimationState.w = 1 / effectAnimationState.w;
    effectAnimationState.w = cb_cluster.vVoxelDims.z * effectAnimationState.w;
    effectAnimationState.w = floor(effectAnimationState.w);
    effectAnimationState.w = (uint)effectAnimationState.w;
    profileMaterialState.xy = cb_cluster.vVoxelDims.xy * profileMaterialState.xy;
    profileMaterialState.xy = (uint2)profileMaterialState.xy;
    materialSampleState.w = mad((int)profileMaterialState.y, asint(cb_cluster.uClusterWidth), (int)profileMaterialState.x);
    effectAnimationState.w = mad((int)effectAnimationState.w, asint(cb_cluster.uClusterSliceSize), (int)materialSampleState.w);
    materialSampleState.w = (int)effectAnimationState.w * 33;
    materialSampleState.w = sbVoxelLightIds[materialSampleState.w].x;
    effectAnimationState.w = mad((int)effectAnimationState.w, 33, 1);
    profileMaterialState.xy = (int2)materialSampleState.ww & int2(0xff00,0xff0000);
    clusterMaskState.xyz = materialCoordinateState.xzw;
    lightIteratorState.xyz = float3(0,0,0);
    materialSampleState.w = normalAndTangentState.w;
    profileMaterialState.z = materialCoordinateState.y;
    profileMaterialState.w = profileMaterialState.x;
    while (true) {
      if (profileMaterialState.w == 0) break;
      clusterMaskState.w = firstbitlow((uint)profileMaterialState.w);
      lightIteratorState.w = (int)effectAnimationState.w + (int)clusterMaskState.w;
      lightGeometryState.x = 1 << (int)clusterMaskState.w;
      profileMaterialState.w = (int)profileMaterialState.w ^ (int)lightGeometryState.x;
      lightIteratorState.w = sbVoxelLightIds[lightIteratorState.w].x;
      clusterMaskState.w = (uint)clusterMaskState.w << 5;
      lightGeometryState.xyz = clusterMaskState.xyz;
      attenuationAndCookieState.xyz = lightIteratorState.xyz;
      lightGeometryState.w = materialSampleState.w;
      attenuationAndCookieState.w = profileMaterialState.z;
      shadowState.x = lightIteratorState.w;
      while (true) {
        if (shadowState.x == 0) break;
        shadowState.y = firstbitlow((uint)shadowState.x);
        shadowState.z = (int)clusterMaskState.w + (int)shadowState.y;
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
        shadowState.w = max(0, shadowState.w);
        shadowState.w = shadowState.w * cb_glass.fTransmissionRange + cb_glass.fTransmissionBase;
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
        directLightAccumulator.x = reflectionAndRefractionState.w * shadowState.w;
        if (8 == 0) transmissionState.x = 0; else if (8+16 < 32) {         transmissionState.x = (uint)cb_arrPoint[shadowState.y].uColor << (32-(8 + 16)); transmissionState.x = (uint)transmissionState.x >> (32-8);        } else transmissionState.x = (uint)cb_arrPoint[shadowState.y].uColor >> 16;
        if (8 == 0) transmissionState.y = 0; else if (8+8 < 32) {         transmissionState.y = (uint)cb_arrPoint[shadowState.y].uColor << (32-(8 + 8)); transmissionState.y = (uint)transmissionState.y >> (32-8);        } else transmissionState.y = (uint)cb_arrPoint[shadowState.y].uColor >> 8;
        transmissionState.xy = (uint2)transmissionState.xy;
        directLightAccumulator.yz = transmissionState.xy * shadowState.ww;
        reflectionAndRefractionState.xyz = -v1.xyz * partPositionState.xxx + reflectionAndRefractionState.xyz;
        reflectionAndRefractionState.w = dot(reflectionAndRefractionState.xyz, reflectionAndRefractionState.xyz);
        reflectionAndRefractionState.w = rsqrt(reflectionAndRefractionState.w);
        reflectionAndRefractionState.xyz = reflectionAndRefractionState.xyz * reflectionAndRefractionState.www;
        reflectionAndRefractionState.x = dot(reflectionAndRefractionState.xyz, viewProjectionState.xyz);
        reflectionAndRefractionState.x = reflectionAndRefractionState.x * 0.5 + 0.5;
        reflectionAndRefractionState.x = log2(abs(reflectionAndRefractionState.x));
        reflectionAndRefractionState.x = reflectionAndRefractionState.x * viewProjectionState.w;
        reflectionAndRefractionState.x = exp2(reflectionAndRefractionState.x);
        reflectionAndRefractionState.x = reflectionAndRefractionState.x * shadowState.z;
        reflectionAndRefractionState.x = saturate(reflectionAndRefractionState.x * animationTransformState.z);
        attenuationAndCookieState.w = max(reflectionAndRefractionState.x, attenuationAndCookieState.w);
        shadowState.w = shadowState.w * shadowState.z;
        lightGeometryState.w = max(shadowState.w, lightGeometryState.w);
        reflectionAndRefractionState.xyz = directLightAccumulator.xyz * shadowState.zzz;
        reflectionAndRefractionState.xyz = float3(0.00392156886,0.00392156886,0.00392156886) * reflectionAndRefractionState.xyz;
        shadowState.y = 1 & asint(cb_arrPoint[shadowState.y].uColor);
        directLightAccumulator.xyz = max(float3(0,0,0), reflectionAndRefractionState.xyz);
        directLightAccumulator.xyz = directLightAccumulator.xyz + attenuationAndCookieState.xyz;
        reflectionAndRefractionState.xyz = max(reflectionAndRefractionState.xyz, lightGeometryState.xyz);
        lightGeometryState.xyz = shadowState.yyy ? lightGeometryState.xyz : reflectionAndRefractionState.xyz;
        attenuationAndCookieState.xyz = shadowState.yyy ? directLightAccumulator.xyz : attenuationAndCookieState.xyz;
      }
      clusterMaskState.xyz = lightGeometryState.xyz;
      lightIteratorState.xyz = attenuationAndCookieState.xyz;
      materialSampleState.w = lightGeometryState.w;
      profileMaterialState.z = attenuationAndCookieState.w;
    }
    materialCoordinateState.xzw = clusterMaskState.xyz;
    lightGeometryState.xyz = lightIteratorState.xyz;
    normalAndTangentState.w = materialSampleState.w;
    materialCoordinateState.y = profileMaterialState.z;
    profileMaterialState.x = profileMaterialState.y;
    while (true) {
      if (profileMaterialState.x == 0) break;
      profileMaterialState.w = firstbitlow((uint)profileMaterialState.x);
      clusterMaskState.w = (int)effectAnimationState.w + (int)profileMaterialState.w;
      lightIteratorState.w = 1 << (int)profileMaterialState.w;
      profileMaterialState.x = (int)profileMaterialState.x ^ (int)lightIteratorState.w;
      clusterMaskState.w = sbVoxelLightIds[clusterMaskState.w].x;
      profileMaterialState.w = (uint)profileMaterialState.w << 5;
      attenuationAndCookieState.xyz = materialCoordinateState.xzw;
      shadowState.xyz = lightGeometryState.xyz;
      lightIteratorState.w = normalAndTangentState.w;
      lightGeometryState.w = materialCoordinateState.y;
      attenuationAndCookieState.w = clusterMaskState.w;
      while (true) {
        if (attenuationAndCookieState.w == 0) break;
        shadowState.w = firstbitlow((uint)attenuationAndCookieState.w);
        reflectionAndRefractionState.x = (int)profileMaterialState.w + (int)shadowState.w;
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
              directLightAccumulator.x = max(0, directLightAccumulator.x);
              directLightAccumulator.x = directLightAccumulator.x * cb_glass.fTransmissionRange + cb_glass.fTransmissionBase;
              directLightAccumulator.y = asuint(cb_arrSpot[shadowState.w].uColor) >> 24;
              directLightAccumulator.y = (uint)directLightAccumulator.y;
              transmissionState.x = directLightAccumulator.y * directLightAccumulator.x;
              if (8 == 0) directLightAccumulator.y = 0; else if (8+16 < 32) {               directLightAccumulator.y = (uint)cb_arrSpot[shadowState.w].uColor << (32-(8 + 16)); directLightAccumulator.y = (uint)directLightAccumulator.y >> (32-8);              } else directLightAccumulator.y = (uint)cb_arrSpot[shadowState.w].uColor >> 16;
              if (8 == 0) directLightAccumulator.z = 0; else if (8+8 < 32) {               directLightAccumulator.z = (uint)cb_arrSpot[shadowState.w].uColor << (32-(8 + 8)); directLightAccumulator.z = (uint)directLightAccumulator.z >> (32-8);              } else directLightAccumulator.z = (uint)cb_arrSpot[shadowState.w].uColor >> 8;
              directLightAccumulator.yz = (uint2)directLightAccumulator.yz;
              transmissionState.yz = directLightAccumulator.yz * directLightAccumulator.xx;
              reflectionAndRefractionState.xyz = -v1.xyz * partPositionState.xxx + reflectionAndRefractionState.xyz;
              directLightAccumulator.y = dot(reflectionAndRefractionState.xyz, reflectionAndRefractionState.xyz);
              directLightAccumulator.y = rsqrt(directLightAccumulator.y);
              reflectionAndRefractionState.xyz = directLightAccumulator.yyy * reflectionAndRefractionState.xyz;
              reflectionAndRefractionState.x = dot(reflectionAndRefractionState.xyz, viewProjectionState.xyz);
              reflectionAndRefractionState.x = reflectionAndRefractionState.x * 0.5 + 0.5;
              reflectionAndRefractionState.x = log2(abs(reflectionAndRefractionState.x));
              reflectionAndRefractionState.x = reflectionAndRefractionState.x * viewProjectionState.w;
              reflectionAndRefractionState.x = exp2(reflectionAndRefractionState.x);
              reflectionAndRefractionState.x = reflectionAndRefractionState.x * reflectionAndRefractionState.w;
              reflectionAndRefractionState.x = saturate(reflectionAndRefractionState.x * animationTransformState.z);
              lightGeometryState.w = max(reflectionAndRefractionState.x, lightGeometryState.w);
              reflectionAndRefractionState.x = directLightAccumulator.x * reflectionAndRefractionState.w;
              lightIteratorState.w = max(reflectionAndRefractionState.x, lightIteratorState.w);
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
      materialCoordinateState.xzw = attenuationAndCookieState.xyz;
      lightGeometryState.xyz = shadowState.xyz;
      normalAndTangentState.w = lightIteratorState.w;
      materialCoordinateState.y = lightGeometryState.w;
    }
  } else {
    lightGeometryState.xyz = float3(0,0,0);
  }

  MainPartOpaqueGlassClusterLighting result;
  result.maxLightColor = materialCoordinateState.xzw;
  result.additiveLightColor = lightGeometryState.xyz;
  result.maximumTransmission = normalAndTangentState.w;
  result.maximumSpecular = materialCoordinateState.y;
  return result;
}
