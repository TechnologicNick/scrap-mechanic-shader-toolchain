#ifndef MAIN_PART_GLASS_SURFACE_SHARED_INCLUDED
#define MAIN_PART_GLASS_SURFACE_SHARED_INCLUDED

// Medium-quality dissolving glass surface with clustered transmission and
// multi-probe reflection. The traversal remains instruction ordered because
// packed cluster masks, cookie gradients, and probe weights are DXBC-sensitive.

#define cmp -

struct MainPartDissolveGlassMaterial
{
  float3 viewDirection;
  float3 normalView;
  float3 diffuseColor;
  float gloss;
  float coverage;
  float reflectionScale;
  float inverseViewLength;
  float viewDistance;
  float glossExponent;
  float specularScale;
};

struct MainPartGlassLighting
{
  float3 directColor;
  float3 reflectedColor;
  float specular;
  float transmission;
};

struct MainPartGlassSurfaceComposite
{
  float4 color;
  float4 auxiliary;
};

#ifdef MAIN_PART_GLASS_SURFACE_HAS_DISSOLVE
float EvaluateMainPartUvDissolve(float2 uv, float cutoffOffset)
{
  float2 cutoffUv = uv * cb_dissolve.fScale
      + cb_dissolve.vScrollSpeed.xy * cb_fTime;
  float4 cutoffSamples = tCutoff.Gather(LinearWrapWrap_s, cutoffUv);
  float2 pairMaximum = max(cutoffSamples.xz, cutoffSamples.yw);
  float gatherMaximum = max(pairMaximum.x, pairMaximum.y) - 0.125;
  float4 accepted = gatherMaximum < cutoffSamples ? 1.0 : 0.0;
  float acceptedCount = dot(accepted, 1.0);
  float hasAcceptedSample = cmp(acceptedCount != 0.0);
  float averagedCutoff = dot(accepted * cutoffSamples, 1.0) / acceptedCount;
  averagedCutoff = hasAcceptedSample ? averagedCutoff : 0.0;

  float loopPosition = frac(cb_fTime * cb_dissolve.fLoopSpeed + cutoffOffset);
  loopPosition = loopPosition * cb_dissolve.fLoopLength
      - cb_dissolve.fLoopOffset;
  float signedDistance = loopPosition - averagedCutoff;
  if (abs(signedDistance) >= cb_dissolve.fLength)
    discard;

  float fade = saturate(
      cb_dissolve.fRcpFade * (cb_dissolve.fLength - abs(signedDistance)));
  return exp2(cb_dissolve.fFadePower * log2(fade));
}
#endif

#ifndef MAIN_PART_GLASS_SURFACE_GEOMETRIC_NORMAL_ONLY
float3 DecodeMainPartTwoSidedNormal(
    float2 uv,
    float3 normalView,
    float3 tangentView,
    float3 bitangentView,
    bool frontFace)
{
  float2 tangentNormal = tNor.SampleBias(
      LinearWrapWrap_s, uv, cb_fMipBias).xy;
  tangentNormal = tangentNormal * 1.99215686 - 1.0;
  float normalZ = sqrt(max(0.0, 1.0 - dot(tangentNormal, tangentNormal)));
  float3 result = bitangentView * tangentNormal.y;
  result = tangentView * tangentNormal.x + result;
  result = normalView * normalZ + result;
  result *= rsqrt(dot(result, result));
  result = frontFace ? result : -result;
  return result * rsqrt(dot(result, result));
}

#ifdef MAIN_PART_GLASS_SURFACE_HAS_DISSOLVE
MainPartDissolveGlassMaterial EvaluateMainPartDissolveGlassMaterial(
    float3 viewPosition,
    float2 uv,
    float3 normalView,
    float3 tangentView,
    float3 bitangentView,
    float4 vertexColor,
    float cutoffOffset,
    bool frontFace)
{
  MainPartDissolveGlassMaterial result;
  float4 asg = tAsg.SampleBias(LinearWrapWrap_s, uv, cb_fMipBias).yxwz;
  if (asg.y < 0.5)
    discard;

  float dissolve = EvaluateMainPartUvDissolve(uv, cutoffOffset);
  result.normalView = DecodeMainPartTwoSidedNormal(
      uv, normalView, tangentView, bitangentView, frontFace);

  float4 diffuse = tDif.SampleBias(LinearWrapWrap_s, uv, cb_fMipBias);
  diffuse.xyz = (diffuse.xyz - vertexColor.xyz) * diffuse.w
      + vertexColor.xyz;
  float4 dissolveColor = (cb_dissolve.vEndColor - cb_dissolve.vStartColor)
      * dissolve + cb_dissolve.vStartColor;
  result.diffuseColor = (diffuse.xyz - dissolveColor.xyz) * dissolve
      + dissolveColor.xyz;
  result.coverage = (asg.w * vertexColor.w - dissolveColor.w) * dissolve
      + dissolveColor.w;

  float inverseViewLength = rsqrt(dot(-viewPosition, -viewPosition));
  result.viewDirection = -viewPosition * inverseViewLength;
  result.inverseViewLength = inverseViewLength;
  result.viewDistance = sqrt(dot(viewPosition, viewPosition));
  result.gloss = asg.x;
  result.reflectionScale = asg.z;
  result.glossExponent = asg.x * asg.x * 750.0 + 35.0;
  result.specularScale = asg.z * asg.x;
  return result;
}

MainPartDissolveGlassMaterial EvaluateMainPartDissolveGlassMaterialAtUv(
    float3 viewPosition, float2 materialUv, float2 dissolveUv,
    float3 normalView, float3 tangentView, float3 bitangentView,
    float4 vertexColor, float cutoffOffset, bool frontFace)
{
  MainPartDissolveGlassMaterial result;
  float4 asg = tAsg.SampleBias(
      LinearWrapWrap_s, materialUv, cb_fMipBias).yxwz;
  if (asg.y < 0.5)
    discard;
  float dissolve = EvaluateMainPartUvDissolve(dissolveUv, cutoffOffset);
  result.normalView = DecodeMainPartTwoSidedNormal(
      materialUv, normalView, tangentView, bitangentView, frontFace);
  float4 diffuse = tDif.SampleBias(
      LinearWrapWrap_s, materialUv, cb_fMipBias);
  diffuse.xyz = (diffuse.xyz - vertexColor.xyz) * diffuse.w
      + vertexColor.xyz;
  float4 dissolveColor = (cb_dissolve.vEndColor - cb_dissolve.vStartColor)
      * dissolve + cb_dissolve.vStartColor;
  result.diffuseColor = (diffuse.xyz - dissolveColor.xyz) * dissolve
      + dissolveColor.xyz;
  result.coverage = (asg.w * vertexColor.w - dissolveColor.w) * dissolve
      + dissolveColor.w;
  float inverseViewLength = rsqrt(dot(-viewPosition, -viewPosition));
  result.viewDirection = -viewPosition * inverseViewLength;
  result.inverseViewLength = inverseViewLength;
  result.viewDistance = sqrt(dot(viewPosition, viewPosition));
  result.gloss = asg.x;
  result.reflectionScale = asg.z;
  result.glossExponent = asg.x * asg.x * 750.0 + 35.0;
  result.specularScale = asg.z * asg.x;
  return result;
}
#endif

MainPartDissolveGlassMaterial EvaluateMainPartGlassMaterial(
    float3 viewPosition,
    float2 uv,
    float3 normalView,
    float3 tangentView,
    float3 bitangentView,
    float4 vertexColor,
    bool frontFace)
{
  MainPartDissolveGlassMaterial result;
  float4 asg = tAsg.SampleBias(LinearWrapWrap_s, uv, cb_fMipBias).yxwz;
  if (asg.y < 0.5)
    discard;
  result.normalView = DecodeMainPartTwoSidedNormal(
      uv, normalView, tangentView, bitangentView, frontFace);
  float4 diffuse = tDif.SampleBias(LinearWrapWrap_s, uv, cb_fMipBias);
  result.diffuseColor = (diffuse.xyz - vertexColor.xyz) * diffuse.w
      + vertexColor.xyz;
  result.coverage = asg.w * vertexColor.w;
  float inverseViewLength = rsqrt(dot(-viewPosition, -viewPosition));
  result.viewDirection = -viewPosition * inverseViewLength;
  result.inverseViewLength = inverseViewLength;
  result.viewDistance = sqrt(dot(viewPosition, viewPosition));
  result.gloss = asg.x;
  result.reflectionScale = asg.z;
  result.glossExponent = asg.x * asg.x * 750.0 + 35.0;
  result.specularScale = asg.z * asg.x;
  return result;
}

MainPartDissolveGlassMaterial EvaluateMainPartGlassMaterialNoCutout(
    float3 viewPosition,
    float2 uv,
    float3 normalView,
    float3 tangentView,
    float3 bitangentView,
    float4 vertexColor,
    bool frontFace)
{
  MainPartDissolveGlassMaterial result;
  float3 asg = tAsg.SampleBias(LinearWrapWrap_s, uv, cb_fMipBias).yzw;
  result.normalView = DecodeMainPartTwoSidedNormal(
      uv, normalView, tangentView, bitangentView, frontFace);
  float4 diffuse = tDif.SampleBias(LinearWrapWrap_s, uv, cb_fMipBias);
  result.diffuseColor = (diffuse.xyz - vertexColor.xyz) * diffuse.w
      + vertexColor.xyz;
  result.coverage = vertexColor.w * asg.y;
  float inverseViewLength = rsqrt(dot(-viewPosition, -viewPosition));
  result.viewDirection = -viewPosition * inverseViewLength;
  result.inverseViewLength = inverseViewLength;
  result.viewDistance = sqrt(dot(viewPosition, viewPosition));
  result.gloss = asg.x;
  result.reflectionScale = asg.z;
  result.glossExponent = asg.x * asg.x * 750.0 + 35.0;
  result.specularScale = asg.z * asg.x;
  return result;
}
#endif

MainPartDissolveGlassMaterial EvaluateMainPartGlassMaterialGeometricNormal(
    float3 viewPosition, float2 uv, float3 normalView,
    float4 vertexColor, bool frontFace)
{
  MainPartDissolveGlassMaterial result;
  float4 asg = tAsg.SampleBias(LinearWrapWrap_s, uv, cb_fMipBias).yxwz;
  if (asg.y < 0.5)
    discard;
  result.normalView = frontFace ? normalView : -normalView;
  result.normalView *= rsqrt(dot(result.normalView, result.normalView));
  float4 diffuse = tDif.SampleBias(LinearWrapWrap_s, uv, cb_fMipBias);
  result.diffuseColor = (diffuse.xyz - vertexColor.xyz) * diffuse.w
      + vertexColor.xyz;
  result.coverage = asg.w * vertexColor.w;
  float inverseViewLength = rsqrt(dot(-viewPosition, -viewPosition));
  result.viewDirection = -viewPosition * inverseViewLength;
  result.inverseViewLength = inverseViewLength;
  result.viewDistance = sqrt(dot(viewPosition, viewPosition));
  result.gloss = asg.x;
  result.reflectionScale = asg.z;
  result.glossExponent = asg.x * asg.x * 750.0 + 35.0;
  result.specularScale = asg.z * asg.x;
  return result;
}

MainPartGlassLighting EvaluateMainPartGlassDirectionalLighting(
    float3 viewPosition,
    MainPartDissolveGlassMaterial material)
{
  MainPartGlassLighting result;
  result.reflectedColor = 0.0;
  if (cb_fDirectionalLightIntensity != 0.0)
  {
    float normalDotLight = dot(
        material.normalView, -cb_vDirectionalLightDirectionView.xyz);
    float halfLambert = normalDotLight * 0.5 + 0.5;
    float transmission = max(0.0, normalDotLight);
    transmission = min(1.0, transmission * cb_glass.fTransmissionRange
        + cb_glass.fTransmissionBase);

    float distanceShape = min(1.0, 0.00400000019 * material.viewDistance);
    distanceShape = 1.0 - distanceShape;
    distanceShape *= distanceShape;
    distanceShape = distanceShape * 0.200000018 + 0.400000006;
    float2 shapeRange = float2(1.0, 1.20000005) - distanceShape;
    float shapedLight = saturate(halfLambert - distanceShape) / shapeRange.x;
    shapedLight *= shapedLight;
    distanceShape = shapedLight * shapeRange.y + distanceShape;

    float3 mappedLight = tLightColorMap.SampleLevel(
        LinearWrapClamp_s,
        float2(cb_fTimeOfDay, saturate(halfLambert)), 0).xyz;
    mappedLight = (mappedLight - cb_vDirectionalShadowColor.xyz)
        * halfLambert + cb_vDirectionalShadowColor.xyz;
    result.directColor = mappedLight
        * (cb_fDirectionalLightMapMul * distanceShape)
        * cb_fDirectionalLightIntensity;
    result.transmission = cb_fDirectionalLightIntensity * transmission;

    float3 halfDirection = material.viewDirection
        - cb_vDirectionalLightDirectionView.xyz;
    halfDirection *= rsqrt(dot(halfDirection, halfDirection));
    float specular = dot(halfDirection, material.normalView) * 0.5 + 0.5;
    specular = exp2(log2(abs(specular)) * material.glossExponent);
    specular *= transmission;
    result.specular = saturate(specular * material.specularScale);
  }
  else
  {
    result.directColor = 0.0;
    result.specular = 0.0;
    result.transmission = 0.0;
  }
  return result;
}

#ifndef MAIN_PART_GLASS_SURFACE_SKIP_FRAME_COMPOSITION
float2 ClampMainPartFrameUv(float2 screenUv)
{
  float2 upperClamped = min(cb_vRenderScale.xy, screenUv);
  float2 upperOverflow = max(0.0, screenUv - cb_vUvLimit.xy);
  return upperClamped - upperOverflow;
}

MainPartGlassSurfaceComposite ComposeMainPartDissolveGlassSurface(
    float3 screenUv,
    float4 fogColor,
    bool frontFace,
    MainPartDissolveGlassMaterial material,
    MainPartGlassLighting lighting)
{
  MainPartGlassSurfaceComposite result;

  float responsive = saturate(lighting.transmission);
  responsive = responsive * cb_glass.fResponsiveGlowRange
      + cb_glass.fResponsiveGlowBase;
  responsive *= material.coverage;
  lighting.directColor = responsive * (1.0 - lighting.directColor)
      + lighting.directColor;
  float auxiliaryCoverage = min(0.5, 0.5 * responsive);

  float normalFacing = dot(material.viewDirection, material.normalView);
  float minimumFresnel = material.gloss * 0.5 + 0.00999999978;
  float grazing = 1.0 - normalFacing;
  float fresnel = grazing * grazing;
  fresnel *= fresnel;
  fresnel *= grazing;
  fresnel = (1.0 - minimumFresnel) * fresnel + minimumFresnel;

  float faceTransparency = frontFace
      ? cb_glass.fTransparencyFront
      : cb_glass.fTransparencyBack;
  float transparency = saturate(
      faceTransparency + lighting.specular + fresnel);
  float reflectionEnergy = lighting.specular + fresnel;
  float3 glassColor = lighting.directColor * reflectionEnergy;

  float4 frame = tFrame.SampleLevel(
      LinearMirrorMirror_s, ClampMainPartFrameUv(screenUv.xy), 0);
  float3 frameColor = frame.xyz;
  glassColor = material.diffuseColor * lighting.directColor + glassColor;
  glassColor += lighting.reflectedColor;
  glassColor = (glassColor - frameColor) * transparency + frameColor;

  float fogStrength = 0.349999994 * auxiliaryCoverage;
  float distanceFade = min(1.0, 0.00999999978 * material.viewDistance);
  fogStrength *= 1.0 - distanceFade;
  float largestChannel = max(abs(glassColor.x), abs(glassColor.y));
  largestChannel = max(largestChannel, abs(glassColor.z));
  fogStrength = (1.0 - fogStrength * largestChannel) * fogColor.w;
  result.color.xyz = (fogColor.xyz - glassColor) * fogStrength + glassColor;
#ifdef MAIN_PART_GLASS_SURFACE_NO_CUTOUT
  result.color.w = max(frame.w, transparency);
#else
  result.color.w = transparency;
#endif
  result.auxiliary = float4(
      auxiliaryCoverage, 0.0, 0.0, result.color.w);
  return result;
}
#endif

#ifdef MAIN_PART_GLASS_SURFACE_ENABLE_SINGLE_PROBE
float2 EncodeMainPartOctahedralDirection(float3 direction)
{
  float inverseL1 = rcp(max(
      9.99999975e-05,
      abs(direction.x) + abs(direction.y) + abs(direction.z)));
  float2 encoded = direction.xy * inverseL1;
  float2 folded = 1.0 - abs(encoded.yx);
  folded = encoded < 0.0 ? -folded : folded;
  encoded = direction.z <= 0.0 ? folded : encoded;
  encoded += float2(-2.0, 2.0);
  encoded = max(abs(encoded.x), abs(encoded.y)) >= 1.0
      ? -encoded : encoded;
  return encoded * 0.5 + 0.5;
}

float3 EvaluateMainPartSingleReflection(
    MainPartDissolveGlassMaterial material)
{
  float3 reflectedView = reflect(-material.viewDirection, material.normalView);
  float3 reflectedWorld = viewToWorld._m01_m11_m21 * reflectedView.y;
  reflectedWorld = viewToWorld._m00_m10_m20 * reflectedView.x
      + reflectedWorld;
  reflectedWorld = viewToWorld._m02_m12_m22 * reflectedView.z
      + reflectedWorld;
  float roughnessLod = 5.0 * sqrt(max(0.00999999978, 1.0 - material.gloss));
  float3 address = float3(
      EncodeMainPartOctahedralDirection(reflectedWorld), 0.0);
  return taReflection.SampleLevel(
      LinearMirrorMirror_s, address, roughnessLod).xyz
      * material.specularScale;
}
#endif

#ifdef MAIN_PART_GLASS_SURFACE_ENABLE_MEDIUM_CLUSTERED
void EvaluateMainPartGlassSurfaceMedium(
    float4 v0, float3 v1, float2 v2, float3 v3, float3 v4,
    float3 v5, float4 v6, float3 v7, float4 v8, float v9, uint v10,
    out float4 o0, out float4 o1)
{
  float4 partPositionState,animationTransformState,viewProjectionState,normalAndTangentState,materialCoordinateState,effectAnimationState,materialSampleState,profileMaterialState,clusterMaskState,lightIteratorState,lightGeometryState,attenuationAndCookieState,shadowState,reflectionAndRefractionState,directLightAccumulator,transmissionState,forwardAndBehindState,gbufferAndPreviewState,partScratch;
  // Skinning, effects, and material lighting retain DXBC order.
  uint4 packedBitmask, integerDestination;
  float4 floatDestination;

  MainPartDissolveGlassMaterial material;
#ifdef MAIN_PART_GLASS_SURFACE_HAS_DISSOLVE
  material =
      EvaluateMainPartDissolveGlassMaterial(
          v1, v2, v3, v4, v5, v6, v9, v10 != 0);
#else
#ifdef MAIN_PART_GLASS_SURFACE_NO_CUTOUT
  material = EvaluateMainPartGlassMaterialNoCutout(
      v1, v2, v3, v4, v5, v6, v10 != 0);
#else
  material = EvaluateMainPartGlassMaterial(
      v1, v2, v3, v4, v5, v6, v10 != 0);
#endif
#endif
  MainPartGlassLighting lighting =
      EvaluateMainPartGlassDirectionalLighting(v1, material);

  // Bridge the typed front end into the instruction-ordered cluster backend.
  partPositionState.x = material.gloss;
  partPositionState.y = material.coverage;
  partPositionState.z = material.reflectionScale;
  partPositionState.w = material.inverseViewLength;
  normalAndTangentState.xyz = material.viewDirection;
  normalAndTangentState.w = material.specularScale;
  animationTransformState.x = material.viewDistance;
  animationTransformState.yzw = material.normalView;
  viewProjectionState.xyz = material.diffuseColor;
  viewProjectionState.w = material.glossExponent;
  materialCoordinateState.yzw = lighting.directColor;
  materialCoordinateState.x = lighting.specular;
  effectAnimationState.x = lighting.transmission;
  // Phase 4: clustered point/spot transmission and multi-probe reflection.
  effectAnimationState.y = cmp(-v1.z < cb_cluster.fClusterMaxFarTotal);
  if (effectAnimationState.y != 0) {
    effectAnimationState.yzw = viewToWorld._m01_m11_m21 * v1.yyy;
    effectAnimationState.yzw = viewToWorld._m00_m10_m20 * v1.xxx + effectAnimationState.yzw;
    effectAnimationState.yzw = viewToWorld._m02_m12_m22 * v1.zzz + effectAnimationState.yzw;
    effectAnimationState.yzw = viewToWorld._m03_m13_m23 + effectAnimationState.yzw;
    materialSampleState.x = 1 + -partPositionState.x;
    materialSampleState.yzw = ddx_coarse(effectAnimationState.yzw);
    materialSampleState.yzw = materialSampleState.yzw + effectAnimationState.yzw;
    profileMaterialState.xyz = ddy_coarse(effectAnimationState.yzw);
    materialSampleState.yzw = profileMaterialState.xyz + materialSampleState.yzw;
    profileMaterialState.xy = cb_vInvRenderScale.xy * v7.xy;
    profileMaterialState.z = -v1.z * cb_cluster.fRcpClusterRange + cb_cluster.fClusterNearBias;
    profileMaterialState.z = rsqrt(profileMaterialState.z);
    profileMaterialState.z = 1 / profileMaterialState.z;
    profileMaterialState.xyz = cb_cluster.vVoxelDims.xyz * profileMaterialState.xyz;
    profileMaterialState.z = floor(profileMaterialState.z);
    profileMaterialState.xyz = (uint3)profileMaterialState.xyz;
    profileMaterialState.x = mad((int)profileMaterialState.y, asint(cb_cluster.uClusterWidth), (int)profileMaterialState.x);
    profileMaterialState.x = mad((int)profileMaterialState.z, asint(cb_cluster.uClusterSliceSize), (int)profileMaterialState.x);
    profileMaterialState.y = (int)profileMaterialState.x * 33;
    profileMaterialState.y = sbVoxelLightIds[profileMaterialState.y].x;
    profileMaterialState.x = mad((int)profileMaterialState.x, 33, 1);
    profileMaterialState.yzw = (int3)profileMaterialState.yyy & int3(0xff00,0xff0000,0xff000000);
    clusterMaskState.xyz = materialCoordinateState.yzw;
    lightIteratorState.xyz = float3(0,0,0);
    clusterMaskState.w = effectAnimationState.x;
    lightIteratorState.w = materialCoordinateState.x;
    lightGeometryState.x = profileMaterialState.y;
    while (true) {
      if (lightGeometryState.x == 0) break;
      lightGeometryState.y = firstbitlow((uint)lightGeometryState.x);
      lightGeometryState.z = (int)profileMaterialState.x + (int)lightGeometryState.y;
      lightGeometryState.w = 1 << (int)lightGeometryState.y;
      lightGeometryState.x = (int)lightGeometryState.w ^ (int)lightGeometryState.x;
      lightGeometryState.z = sbVoxelLightIds[lightGeometryState.z].x;
      lightGeometryState.y = (uint)lightGeometryState.y << 5;
      attenuationAndCookieState.xyz = clusterMaskState.xyz;
      shadowState.xyz = lightIteratorState.xyz;
      lightGeometryState.w = clusterMaskState.w;
      attenuationAndCookieState.w = lightIteratorState.w;
      shadowState.w = lightGeometryState.z;
      while (true) {
        if (shadowState.w == 0) break;
        reflectionAndRefractionState.x = firstbitlow((uint)shadowState.w);
        reflectionAndRefractionState.y = (int)lightGeometryState.y + (int)reflectionAndRefractionState.x;
        reflectionAndRefractionState.x = 1 << (int)reflectionAndRefractionState.x;
        shadowState.w = (int)shadowState.w ^ (int)reflectionAndRefractionState.x;
        reflectionAndRefractionState.x = (uint)reflectionAndRefractionState.y << 1;
        reflectionAndRefractionState.x = (int)reflectionAndRefractionState.x + -512;
        reflectionAndRefractionState.yzw = cb_arrPoint[reflectionAndRefractionState.x].vPosition.xyz + -v1.xyz;
        directLightAccumulator.x = dot(reflectionAndRefractionState.yzw, reflectionAndRefractionState.yzw);
        directLightAccumulator.x = sqrt(directLightAccumulator.x);
        directLightAccumulator.y = max(0.00100000005, directLightAccumulator.x);
        reflectionAndRefractionState.yzw = reflectionAndRefractionState.yzw / directLightAccumulator.yyy;
        directLightAccumulator.y = dot(reflectionAndRefractionState.yzw, animationTransformState.yzw);
        directLightAccumulator.y = max(0, directLightAccumulator.y);
        directLightAccumulator.y = directLightAccumulator.y * cb_glass.fTransmissionRange + cb_glass.fTransmissionBase;
        directLightAccumulator.x = saturate(cb_arrPoint[reflectionAndRefractionState.x].fRcpRadius * directLightAccumulator.x);
        directLightAccumulator.x = max(0.00999999978, directLightAccumulator.x);
        directLightAccumulator.x = log2(directLightAccumulator.x);
        directLightAccumulator.x = cb_arrPoint[reflectionAndRefractionState.x].fFalloffFactor * directLightAccumulator.x;
        directLightAccumulator.x = exp2(directLightAccumulator.x);
        directLightAccumulator.x = 1 + -directLightAccumulator.x;
        directLightAccumulator.x = cb_arrPoint[reflectionAndRefractionState.x].fIntensity * directLightAccumulator.x;
        directLightAccumulator.x = min(cb_arrPoint[reflectionAndRefractionState.x].fMaxIntensity, directLightAccumulator.x);
        directLightAccumulator.z = asuint(cb_arrPoint[reflectionAndRefractionState.x].uColor) >> 24;
        directLightAccumulator.z = (uint)directLightAccumulator.z;
        transmissionState.x = directLightAccumulator.z * directLightAccumulator.y;
        if (8 == 0) directLightAccumulator.z = 0; else if (8+16 < 32) {         directLightAccumulator.z = (uint)cb_arrPoint[reflectionAndRefractionState.x].uColor << (32-(8 + 16)); directLightAccumulator.z = (uint)directLightAccumulator.z >> (32-8);        } else directLightAccumulator.z = (uint)cb_arrPoint[reflectionAndRefractionState.x].uColor >> 16;
        if (8 == 0) directLightAccumulator.w = 0; else if (8+8 < 32) {         directLightAccumulator.w = (uint)cb_arrPoint[reflectionAndRefractionState.x].uColor << (32-(8 + 8)); directLightAccumulator.w = (uint)directLightAccumulator.w >> (32-8);        } else directLightAccumulator.w = (uint)cb_arrPoint[reflectionAndRefractionState.x].uColor >> 8;
        directLightAccumulator.zw = (uint2)directLightAccumulator.zw;
        transmissionState.yz = directLightAccumulator.zw * directLightAccumulator.yy;
        reflectionAndRefractionState.yzw = -v1.xyz * partPositionState.www + reflectionAndRefractionState.yzw;
        directLightAccumulator.z = dot(reflectionAndRefractionState.yzw, reflectionAndRefractionState.yzw);
        directLightAccumulator.z = rsqrt(directLightAccumulator.z);
        reflectionAndRefractionState.yzw = directLightAccumulator.zzz * reflectionAndRefractionState.yzw;
        reflectionAndRefractionState.y = dot(reflectionAndRefractionState.yzw, animationTransformState.yzw);
        reflectionAndRefractionState.y = reflectionAndRefractionState.y * 0.5 + 0.5;
        reflectionAndRefractionState.y = log2(abs(reflectionAndRefractionState.y));
        reflectionAndRefractionState.y = reflectionAndRefractionState.y * viewProjectionState.w;
        reflectionAndRefractionState.y = exp2(reflectionAndRefractionState.y);
        reflectionAndRefractionState.y = reflectionAndRefractionState.y * directLightAccumulator.x;
        reflectionAndRefractionState.y = saturate(reflectionAndRefractionState.y * normalAndTangentState.w);
        attenuationAndCookieState.w = max(reflectionAndRefractionState.y, attenuationAndCookieState.w);
        reflectionAndRefractionState.y = directLightAccumulator.y * directLightAccumulator.x;
        lightGeometryState.w = max(reflectionAndRefractionState.y, lightGeometryState.w);
        reflectionAndRefractionState.yzw = transmissionState.xyz * directLightAccumulator.xxx;
        reflectionAndRefractionState.yzw = float3(0.00392156886,0.00392156886,0.00392156886) * reflectionAndRefractionState.yzw;
        reflectionAndRefractionState.x = 1 & asint(cb_arrPoint[reflectionAndRefractionState.x].uColor);
        directLightAccumulator.xyz = max(float3(0,0,0), reflectionAndRefractionState.yzw);
        directLightAccumulator.xyz = directLightAccumulator.xyz + shadowState.xyz;
        reflectionAndRefractionState.yzw = max(reflectionAndRefractionState.yzw, attenuationAndCookieState.xyz);
        attenuationAndCookieState.xyz = reflectionAndRefractionState.xxx ? attenuationAndCookieState.xyz : reflectionAndRefractionState.yzw;
        shadowState.xyz = reflectionAndRefractionState.xxx ? directLightAccumulator.xyz : shadowState.xyz;
      }
      clusterMaskState.xyz = attenuationAndCookieState.xyz;
      lightIteratorState.xyz = shadowState.xyz;
      clusterMaskState.w = lightGeometryState.w;
      lightIteratorState.w = attenuationAndCookieState.w;
    }
    materialCoordinateState.yzw = clusterMaskState.xyz;
    lightGeometryState.xyz = lightIteratorState.xyz;
    effectAnimationState.x = clusterMaskState.w;
    materialCoordinateState.x = lightIteratorState.w;
    profileMaterialState.y = profileMaterialState.z;
    while (true) {
      if (profileMaterialState.y == 0) break;
      lightGeometryState.w = firstbitlow((uint)profileMaterialState.y);
      attenuationAndCookieState.x = (int)profileMaterialState.x + (int)lightGeometryState.w;
      attenuationAndCookieState.y = 1 << (int)lightGeometryState.w;
      profileMaterialState.y = (int)profileMaterialState.y ^ (int)attenuationAndCookieState.y;
      attenuationAndCookieState.x = sbVoxelLightIds[attenuationAndCookieState.x].x;
      lightGeometryState.w = (uint)lightGeometryState.w << 5;
      attenuationAndCookieState.yzw = materialCoordinateState.yzw;
      shadowState.xyz = lightGeometryState.xyz;
      shadowState.w = effectAnimationState.x;
      reflectionAndRefractionState.x = materialCoordinateState.x;
      reflectionAndRefractionState.y = attenuationAndCookieState.x;
      while (true) {
        if (reflectionAndRefractionState.y == 0) break;
        reflectionAndRefractionState.z = firstbitlow((uint)reflectionAndRefractionState.y);
        reflectionAndRefractionState.w = (int)lightGeometryState.w + (int)reflectionAndRefractionState.z;
        reflectionAndRefractionState.z = 1 << (int)reflectionAndRefractionState.z;
        reflectionAndRefractionState.y = (int)reflectionAndRefractionState.z ^ (int)reflectionAndRefractionState.y;
        reflectionAndRefractionState.z = mad((int)reflectionAndRefractionState.w, 9, -4608);
        directLightAccumulator.xyz = cb_arrSpot[reflectionAndRefractionState.z].vPosition.xyz + -v1.xyz;
        reflectionAndRefractionState.w = dot(directLightAccumulator.xyz, directLightAccumulator.xyz);
        reflectionAndRefractionState.w = sqrt(reflectionAndRefractionState.w);
        directLightAccumulator.w = cb_arrSpot[reflectionAndRefractionState.z].fRcpRange * reflectionAndRefractionState.w;
        transmissionState.x = cmp(1 >= directLightAccumulator.w);
        if (transmissionState.x != 0) {
          reflectionAndRefractionState.w = max(0.00100000005, reflectionAndRefractionState.w);
          directLightAccumulator.xyz = directLightAccumulator.xyz / reflectionAndRefractionState.www;
          reflectionAndRefractionState.w = dot(-directLightAccumulator.xyz, cb_arrSpot[reflectionAndRefractionState.z].vForward.xyz);
          transmissionState.x = cmp(0 < reflectionAndRefractionState.w);
          if (transmissionState.x != 0) {
            reflectionAndRefractionState.w = saturate(reflectionAndRefractionState.w * cb_arrSpot[reflectionAndRefractionState.z].fCutoffScale + cb_arrSpot[reflectionAndRefractionState.z].fCutoffOffset);
            transmissionState.x = 240 & asint(cb_arrSpot[reflectionAndRefractionState.z].uColor);
            if (transmissionState.x != 0) {
              transmissionState.xyz = cb_arrSpot[reflectionAndRefractionState.z].xClip._m01_m11_m31 * effectAnimationState.zzz;
              transmissionState.xyz = cb_arrSpot[reflectionAndRefractionState.z].xClip._m00_m10_m30 * effectAnimationState.yyy + transmissionState.xyz;
              transmissionState.xyz = cb_arrSpot[reflectionAndRefractionState.z].xClip._m02_m12_m32 * effectAnimationState.www + transmissionState.xyz;
              transmissionState.xyz = cb_arrSpot[reflectionAndRefractionState.z].xClip._m03_m13_m33 + transmissionState.xyz;
              transmissionState.xy = transmissionState.xy / transmissionState.zz;
              transmissionState.xy = transmissionState.xy * float2(0.5,0.5) + float2(0.5,0.5);
              forwardAndBehindState.xyz = cb_arrSpot[reflectionAndRefractionState.z].xClip._m01_m11_m31 * materialSampleState.zzz;
              forwardAndBehindState.xyz = cb_arrSpot[reflectionAndRefractionState.z].xClip._m00_m10_m30 * materialSampleState.yyy + forwardAndBehindState.xyz;
              forwardAndBehindState.xyz = cb_arrSpot[reflectionAndRefractionState.z].xClip._m02_m12_m32 * materialSampleState.www + forwardAndBehindState.xyz;
              forwardAndBehindState.xyz = cb_arrSpot[reflectionAndRefractionState.z].xClip._m03_m13_m33 + forwardAndBehindState.xyz;
              forwardAndBehindState.xy = forwardAndBehindState.xy / forwardAndBehindState.zz;
              forwardAndBehindState.xy = forwardAndBehindState.xy * float2(0.5,0.5) + float2(0.5,0.5);
              forwardAndBehindState.xy = -forwardAndBehindState.xy + transmissionState.xy;
              if (4 == 0) transmissionState.w = 0; else if (4+4 < 32) {               transmissionState.w = (uint)cb_arrSpot[reflectionAndRefractionState.z].uColor << (32-(4 + 4)); transmissionState.w = (uint)transmissionState.w >> (32-4);              } else transmissionState.w = (uint)cb_arrSpot[reflectionAndRefractionState.z].uColor >> 4;
              transmissionState.w = (int)transmissionState.w + -1;
              transmissionState.z = (uint)transmissionState.w;
              transmissionState.x = taCookies.SampleGrad(LinearClampClamp_s, transmissionState.xyz, forwardAndBehindState.x, forwardAndBehindState.y).x;
              reflectionAndRefractionState.w = transmissionState.x * reflectionAndRefractionState.w;
            }
            transmissionState.x = cmp(0 < reflectionAndRefractionState.w);
            if (transmissionState.x != 0) {
              directLightAccumulator.w = max(0.00999999978, directLightAccumulator.w);
              directLightAccumulator.w = log2(directLightAccumulator.w);
              directLightAccumulator.w = cb_arrSpot[reflectionAndRefractionState.z].fFalloffFactor * directLightAccumulator.w;
              directLightAccumulator.w = exp2(directLightAccumulator.w);
              directLightAccumulator.w = 1 + -directLightAccumulator.w;
              directLightAccumulator.w = cb_arrSpot[reflectionAndRefractionState.z].fIntensity * directLightAccumulator.w;
              reflectionAndRefractionState.w = directLightAccumulator.w * reflectionAndRefractionState.w;
              reflectionAndRefractionState.w = min(cb_arrSpot[reflectionAndRefractionState.z].fMaxIntensity, reflectionAndRefractionState.w);
              directLightAccumulator.w = dot(directLightAccumulator.xyz, animationTransformState.yzw);
              directLightAccumulator.w = max(0, directLightAccumulator.w);
              directLightAccumulator.w = directLightAccumulator.w * cb_glass.fTransmissionRange + cb_glass.fTransmissionBase;
              transmissionState.x = asuint(cb_arrSpot[reflectionAndRefractionState.z].uColor) >> 24;
              transmissionState.x = (uint)transmissionState.x;
              transmissionState.x = transmissionState.x * directLightAccumulator.w;
              if (8 == 0) forwardAndBehindState.x = 0; else if (8+16 < 32) {               forwardAndBehindState.x = (uint)cb_arrSpot[reflectionAndRefractionState.z].uColor << (32-(8 + 16)); forwardAndBehindState.x = (uint)forwardAndBehindState.x >> (32-8);              } else forwardAndBehindState.x = (uint)cb_arrSpot[reflectionAndRefractionState.z].uColor >> 16;
              if (8 == 0) forwardAndBehindState.y = 0; else if (8+8 < 32) {               forwardAndBehindState.y = (uint)cb_arrSpot[reflectionAndRefractionState.z].uColor << (32-(8 + 8)); forwardAndBehindState.y = (uint)forwardAndBehindState.y >> (32-8);              } else forwardAndBehindState.y = (uint)cb_arrSpot[reflectionAndRefractionState.z].uColor >> 8;
              forwardAndBehindState.xy = (uint2)forwardAndBehindState.xy;
              transmissionState.yz = forwardAndBehindState.xy * directLightAccumulator.ww;
              directLightAccumulator.xyz = -v1.xyz * partPositionState.www + directLightAccumulator.xyz;
              transmissionState.w = dot(directLightAccumulator.xyz, directLightAccumulator.xyz);
              transmissionState.w = rsqrt(transmissionState.w);
              directLightAccumulator.xyz = transmissionState.www * directLightAccumulator.xyz;
              directLightAccumulator.x = dot(directLightAccumulator.xyz, animationTransformState.yzw);
              directLightAccumulator.x = directLightAccumulator.x * 0.5 + 0.5;
              directLightAccumulator.x = log2(abs(directLightAccumulator.x));
              directLightAccumulator.x = directLightAccumulator.x * viewProjectionState.w;
              directLightAccumulator.x = exp2(directLightAccumulator.x);
              directLightAccumulator.x = directLightAccumulator.x * reflectionAndRefractionState.w;
              directLightAccumulator.x = saturate(directLightAccumulator.x * normalAndTangentState.w);
              reflectionAndRefractionState.x = max(directLightAccumulator.x, reflectionAndRefractionState.x);
              directLightAccumulator.x = directLightAccumulator.w * reflectionAndRefractionState.w;
              shadowState.w = max(directLightAccumulator.x, shadowState.w);
              directLightAccumulator.xyz = transmissionState.xyz * reflectionAndRefractionState.www;
              directLightAccumulator.xyz = float3(0.00392156886,0.00392156886,0.00392156886) * directLightAccumulator.xyz;
              reflectionAndRefractionState.z = 1 & asint(cb_arrSpot[reflectionAndRefractionState.z].uColor);
              transmissionState.xyz = max(float3(0,0,0), directLightAccumulator.xyz);
              transmissionState.xyz = transmissionState.xyz + shadowState.xyz;
              directLightAccumulator.xyz = max(directLightAccumulator.xyz, attenuationAndCookieState.yzw);
              attenuationAndCookieState.yzw = reflectionAndRefractionState.zzz ? attenuationAndCookieState.yzw : directLightAccumulator.xyz;
              shadowState.xyz = reflectionAndRefractionState.zzz ? transmissionState.xyz : shadowState.xyz;
            }
          }
        }
      }
      materialCoordinateState.yzw = attenuationAndCookieState.yzw;
      lightGeometryState.xyz = shadowState.xyz;
      effectAnimationState.x = shadowState.w;
      materialCoordinateState.x = reflectionAndRefractionState.x;
    }
#ifdef MAIN_PART_GLASS_SURFACE_ENABLE_MULTI_PROBES
    partPositionState.w = dot(-normalAndTangentState.xyz, animationTransformState.yzw);
    partPositionState.w = partPositionState.w + partPositionState.w;
    materialSampleState.yzw = animationTransformState.yzw * -partPositionState.www + -normalAndTangentState.xyz;
    clusterMaskState.xyz = viewToWorld._m01_m11_m21 * materialSampleState.zzz;
    clusterMaskState.xyz = viewToWorld._m00_m10_m20 * materialSampleState.yyy + clusterMaskState.xyz;
    materialSampleState.yzw = viewToWorld._m02_m12_m22 * materialSampleState.www + clusterMaskState.xyz;
    partPositionState.w = log2(abs(materialSampleState.x));
    partPositionState.w = 0.75 * partPositionState.w;
    partPositionState.w = exp2(partPositionState.w);
    profileMaterialState.yz = float2(5,0.5) * partPositionState.ww;
    viewProjectionState.w = min(1, profileMaterialState.z);
    viewProjectionState.w = 1 + -viewProjectionState.w;
    partPositionState.w = partPositionState.w * 5 + -3;
    partPositionState.w = saturate(partPositionState.w + partPositionState.w);
    partPositionState.w = 1 + -partPositionState.w;
    clusterMaskState.xyz = rcp(materialSampleState.yzw);
    lightIteratorState.xyz = float3(0,0,0);
    attenuationAndCookieState.xyz = float3(0,0,0);
    normalAndTangentState.w = 0;
    materialSampleState.x = 0;
    profileMaterialState.z = 0;
    clusterMaskState.w = profileMaterialState.w;
    while (true) {
      if (clusterMaskState.w == 0) break;
      lightIteratorState.w = firstbitlow((uint)clusterMaskState.w);
      lightGeometryState.w = (int)profileMaterialState.x + (int)lightIteratorState.w;
      attenuationAndCookieState.w = 1 << (int)lightIteratorState.w;
      clusterMaskState.w = (int)clusterMaskState.w ^ (int)attenuationAndCookieState.w;
      lightGeometryState.w = sbVoxelLightIds[lightGeometryState.w].x;
      lightIteratorState.w = (uint)lightIteratorState.w << 5;
      shadowState.xyz = lightIteratorState.xyz;
      reflectionAndRefractionState.xyz = attenuationAndCookieState.xyz;
      attenuationAndCookieState.w = normalAndTangentState.w;
      shadowState.w = materialSampleState.x;
      reflectionAndRefractionState.w = profileMaterialState.z;
      directLightAccumulator.x = lightGeometryState.w;
      while (true) {
        if (directLightAccumulator.x == 0) break;
        directLightAccumulator.y = firstbitlow((uint)directLightAccumulator.x);
        directLightAccumulator.z = (int)lightIteratorState.w + (int)directLightAccumulator.y;
        directLightAccumulator.y = 1 << (int)directLightAccumulator.y;
        directLightAccumulator.x = (int)directLightAccumulator.y ^ (int)directLightAccumulator.x;
        directLightAccumulator.y = mad((int)directLightAccumulator.z, 10, -7680);
        transmissionState.xyz = cb_reflections.vecProbes[directLightAccumulator.y].vPosition.xyz + -effectAnimationState.yzw;
        transmissionState.xyz = -cb_reflections.vecProbes[directLightAccumulator.y].vExtents.xyz + abs(transmissionState.xyz);
        forwardAndBehindState.xyz = max(float3(0,0,0), transmissionState.xyz);
        directLightAccumulator.z = dot(forwardAndBehindState.xyz, forwardAndBehindState.xyz);
        directLightAccumulator.z = sqrt(directLightAccumulator.z);
        directLightAccumulator.w = max(transmissionState.x, transmissionState.y);
        directLightAccumulator.w = max(directLightAccumulator.w, transmissionState.z);
        directLightAccumulator.w = min(0, directLightAccumulator.w);
        directLightAccumulator.z = directLightAccumulator.z + directLightAccumulator.w;
        directLightAccumulator.z = -cb_reflections.vecProbes[directLightAccumulator.y].fMargin + directLightAccumulator.z;
        directLightAccumulator.z = cb_reflections.vecProbes[directLightAccumulator.y].fGpuEnable * directLightAccumulator.z;
        directLightAccumulator.w = cmp(directLightAccumulator.z < 0);
        if (directLightAccumulator.w != 0) {
          directLightAccumulator.z = saturate(cb_reflections.vecProbes[directLightAccumulator.y].fMarginRcp * -directLightAccumulator.z);
          directLightAccumulator.w = cmp(0 != cb_reflections.vecProbes[directLightAccumulator.y].fIsFallback);
          directLightAccumulator.w = directLightAccumulator.w ? 1 : directLightAccumulator.z;
          transmissionState.x = cb_reflections.vecProbes[directLightAccumulator.y].fBlend * directLightAccumulator.w;
          transmissionState.y = cmp(1.000000 == cb_reflections.vecProbes[directLightAccumulator.y].fIsFallback);
          if (transmissionState.y != 0) {
            transmissionState.y = cmp(1.000000 == cb_reflections.vecProbes[directLightAccumulator.y].fParallax);
            forwardAndBehindState.xyz = cb_reflections.vecProbes[directLightAccumulator.y].vMax.xyz + -effectAnimationState.yzw;
            forwardAndBehindState.xyz = forwardAndBehindState.xyz * clusterMaskState.xyz;
            gbufferAndPreviewState.xyz = cb_reflections.vecProbes[directLightAccumulator.y].vMin.xyz + -effectAnimationState.yzw;
            gbufferAndPreviewState.xyz = gbufferAndPreviewState.xyz * clusterMaskState.xyz;
            forwardAndBehindState.xyz = max(gbufferAndPreviewState.xyz, forwardAndBehindState.xyz);
            transmissionState.z = min(forwardAndBehindState.x, forwardAndBehindState.y);
            transmissionState.z = min(transmissionState.z, forwardAndBehindState.z);
            forwardAndBehindState.xyz = materialSampleState.yzw * transmissionState.zzz + effectAnimationState.yzw;
            forwardAndBehindState.xyz = -cb_reflections.vecProbes[directLightAccumulator.y].vPosition.xyz + forwardAndBehindState.xyz;
            transmissionState.yzw = transmissionState.yyy ? forwardAndBehindState.xyz : materialSampleState.yzw;
            forwardAndBehindState.x = abs(transmissionState.y) + abs(transmissionState.z);
            forwardAndBehindState.x = forwardAndBehindState.x + abs(transmissionState.w);
            forwardAndBehindState.x = max(9.99999975e-05, forwardAndBehindState.x);
            forwardAndBehindState.x = rcp(forwardAndBehindState.x);
            transmissionState.yz = forwardAndBehindState.xx * transmissionState.yz;
            forwardAndBehindState.xy = float2(1,1) + -abs(transmissionState.zy);
            forwardAndBehindState.zw = cmp(transmissionState.yz < float2(0,0));
            forwardAndBehindState.xy = forwardAndBehindState.zw ? -forwardAndBehindState.xy : forwardAndBehindState.xy;
            transmissionState.w = cmp(0 >= transmissionState.w);
            transmissionState.yz = transmissionState.ww ? forwardAndBehindState.xy : transmissionState.yz;
            transmissionState.yz = float2(-2,2) + transmissionState.yz;
            transmissionState.w = max(abs(transmissionState.y), abs(transmissionState.z));
            transmissionState.w = cmp(transmissionState.w >= 1);
            transmissionState.yz = transmissionState.ww ? -transmissionState.yz : transmissionState.yz;
            forwardAndBehindState.xy = transmissionState.yz * float2(0.5,0.5) + float2(0.5,0.5);
            forwardAndBehindState.z = cb_reflections.vecProbes[directLightAccumulator.y].fSlotIndex;
            transmissionState.yzw = taReflection.SampleLevel(LinearMirrorMirror_s, forwardAndBehindState.xyz, profileMaterialState.y).xyz;
            attenuationAndCookieState.w = directLightAccumulator.w * cb_reflections.vecProbes[directLightAccumulator.y].fBlend + attenuationAndCookieState.w;
            reflectionAndRefractionState.xyz = transmissionState.yzw * transmissionState.xxx + reflectionAndRefractionState.xyz;
          } else {
            directLightAccumulator.w = cb_reflections.vecProbes[directLightAccumulator.y].fParallax * partPositionState.w;
            transmissionState.yzw = cb_reflections.vecProbes[directLightAccumulator.y].vMax.xyz + -effectAnimationState.yzw;
            transmissionState.yzw = transmissionState.yzw * clusterMaskState.xyz;
            forwardAndBehindState.xyz = cb_reflections.vecProbes[directLightAccumulator.y].vMin.xyz + -effectAnimationState.yzw;
            forwardAndBehindState.xyz = forwardAndBehindState.xyz * clusterMaskState.xyz;
            transmissionState.yzw = max(forwardAndBehindState.xyz, transmissionState.yzw);
            transmissionState.y = min(transmissionState.y, transmissionState.z);
            transmissionState.y = min(transmissionState.y, transmissionState.w);
            transmissionState.yzw = materialSampleState.yzw * transmissionState.yyy + effectAnimationState.yzw;
            transmissionState.yzw = -cb_reflections.vecProbes[directLightAccumulator.y].vPosition.xyz + transmissionState.yzw;
            forwardAndBehindState.x = dot(transmissionState.yzw, transmissionState.yzw);
            forwardAndBehindState.x = rsqrt(forwardAndBehindState.x);
            transmissionState.yzw = transmissionState.yzw * forwardAndBehindState.xxx + -materialSampleState.yzw;
            transmissionState.yzw = directLightAccumulator.www * transmissionState.yzw + materialSampleState.yzw;
            directLightAccumulator.w = dot(transmissionState.yzw, transmissionState.yzw);
            directLightAccumulator.w = rsqrt(directLightAccumulator.w);
            transmissionState.yzw = transmissionState.yzw * directLightAccumulator.www;
            directLightAccumulator.w = abs(transmissionState.y) + abs(transmissionState.z);
            directLightAccumulator.w = directLightAccumulator.w + abs(transmissionState.w);
            directLightAccumulator.w = max(9.99999975e-05, directLightAccumulator.w);
            directLightAccumulator.w = rcp(directLightAccumulator.w);
            forwardAndBehindState.xy = transmissionState.yz * directLightAccumulator.ww;
            forwardAndBehindState.zw = float2(1,1) + -abs(forwardAndBehindState.yx);
            gbufferAndPreviewState.xy = cmp(forwardAndBehindState.xy < float2(0,0));
            forwardAndBehindState.zw = gbufferAndPreviewState.xy ? -forwardAndBehindState.zw : forwardAndBehindState.zw;
            directLightAccumulator.w = cmp(0 >= transmissionState.w);
            forwardAndBehindState.xy = directLightAccumulator.ww ? forwardAndBehindState.zw : forwardAndBehindState.xy;
            forwardAndBehindState.xy = float2(-2,2) + forwardAndBehindState.xy;
            directLightAccumulator.w = max(abs(forwardAndBehindState.x), abs(forwardAndBehindState.y));
            directLightAccumulator.w = cmp(directLightAccumulator.w >= 1);
            forwardAndBehindState.xy = directLightAccumulator.ww ? -forwardAndBehindState.xy : forwardAndBehindState.xy;
            forwardAndBehindState.xy = forwardAndBehindState.xy * float2(0.5,0.5) + float2(0.5,0.5);
            forwardAndBehindState.z = cb_reflections.vecProbes[directLightAccumulator.y].fSlotIndex;
            forwardAndBehindState.xyzw = taReflection.SampleLevel(LinearMirrorMirror_s, forwardAndBehindState.xyz, profileMaterialState.y).xyzw;
            directLightAccumulator.w = forwardAndBehindState.w * forwardAndBehindState.w;
            directLightAccumulator.w = directLightAccumulator.w * 127.5 + 0.5;
            gbufferAndPreviewState.xyz = transmissionState.yzw * directLightAccumulator.www + cb_reflections.vecProbes[directLightAccumulator.y].vPosition.xyz;
            partScratch.xyz = -gbufferAndPreviewState.xyz + effectAnimationState.yzw;
            directLightAccumulator.w = dot(partScratch.xyz, partScratch.xyz);
            gbufferAndPreviewState.xyz = cb_reflections.vecProbes[directLightAccumulator.y].vGpuPosition.xyz + -gbufferAndPreviewState.xyz;
            gbufferAndPreviewState.xyz = -cb_reflections.vecProbes[directLightAccumulator.y].vGpuExtents.xyz + abs(gbufferAndPreviewState.xyz);
            partScratch.xyz = max(float3(0,0,0), gbufferAndPreviewState.xyz);
            forwardAndBehindState.w = dot(partScratch.xyz, partScratch.xyz);
            forwardAndBehindState.w = sqrt(forwardAndBehindState.w);
            gbufferAndPreviewState.x = max(gbufferAndPreviewState.x, gbufferAndPreviewState.y);
            gbufferAndPreviewState.x = max(gbufferAndPreviewState.x, gbufferAndPreviewState.z);
            gbufferAndPreviewState.x = min(0, gbufferAndPreviewState.x);
            forwardAndBehindState.w = gbufferAndPreviewState.x + forwardAndBehindState.w;
            forwardAndBehindState.w = -cb_reflections.vecProbes[directLightAccumulator.y].fGpuMargin + forwardAndBehindState.w;
            directLightAccumulator.y = saturate(cb_reflections.vecProbes[directLightAccumulator.y].fGpuMarginRcp * -forwardAndBehindState.w);
            transmissionState.y = dot(materialSampleState.yzw, transmissionState.yzw);
            transmissionState.y = transmissionState.y * 0.5 + 0.5;
            transmissionState.y = transmissionState.y * transmissionState.y;
            directLightAccumulator.w = 0.000244140625 * directLightAccumulator.w;
            directLightAccumulator.w = min(1, directLightAccumulator.w);
            directLightAccumulator.w = 1 + -directLightAccumulator.w;
            directLightAccumulator.w = directLightAccumulator.w * directLightAccumulator.w;
            directLightAccumulator.w = directLightAccumulator.w * directLightAccumulator.y;
            directLightAccumulator.w = directLightAccumulator.w * transmissionState.y;
            directLightAccumulator.w = directLightAccumulator.w * directLightAccumulator.z;
            directLightAccumulator.w = directLightAccumulator.w * 10 + 1;
            directLightAccumulator.y = max(directLightAccumulator.y, viewProjectionState.w);
            directLightAccumulator.y = directLightAccumulator.y * directLightAccumulator.z;
            directLightAccumulator.y = directLightAccumulator.y * transmissionState.y;
            directLightAccumulator.y = directLightAccumulator.w * directLightAccumulator.y;
            directLightAccumulator.z = directLightAccumulator.y * transmissionState.x;
            shadowState.w = directLightAccumulator.y * transmissionState.x + shadowState.w;
            directLightAccumulator.y = cmp(0 < directLightAccumulator.y);
            directLightAccumulator.y = directLightAccumulator.y ? 1.000000 : 0;
            reflectionAndRefractionState.w = transmissionState.x * directLightAccumulator.y + reflectionAndRefractionState.w;
            transmissionState.xyz = forwardAndBehindState.xyz * directLightAccumulator.zzz;
            shadowState.xyz = transmissionState.xyz * directLightAccumulator.yyy + shadowState.xyz;
          }
        }
      }
      lightIteratorState.xyz = shadowState.xyz;
      attenuationAndCookieState.xyz = reflectionAndRefractionState.xyz;
      normalAndTangentState.w = attenuationAndCookieState.w;
      materialSampleState.x = shadowState.w;
      profileMaterialState.z = reflectionAndRefractionState.w;
    }
    partPositionState.w = max(0.125, materialSampleState.x);
    effectAnimationState.yzw = lightIteratorState.xyz / partPositionState.www;
    partPositionState.w = max(0.00100000005, normalAndTangentState.w);
    materialSampleState.xyz = attenuationAndCookieState.xyz / partPositionState.www;
    profileMaterialState.z = saturate(profileMaterialState.z);
    partPositionState.w = profileMaterialState.z * profileMaterialState.z;
    effectAnimationState.yzw = -materialSampleState.xyz + effectAnimationState.yzw;
    effectAnimationState.yzw = partPositionState.www * effectAnimationState.yzw + materialSampleState.xyz;
#endif
  } else {
    lightGeometryState.xyz = float3(0,0,0);
#ifdef MAIN_PART_GLASS_SURFACE_ENABLE_MULTI_PROBES
    effectAnimationState.yzw = float3(0,0,0);
#endif
  }
  lighting.directColor = materialCoordinateState.yzw + lightGeometryState.xyz;
#ifdef MAIN_PART_GLASS_SURFACE_ENABLE_MULTI_PROBES
  lighting.reflectedColor = effectAnimationState.yzw
      * material.reflectionScale;
#elif defined(MAIN_PART_GLASS_SURFACE_ENABLE_SINGLE_PROBE)
  lighting.reflectedColor = EvaluateMainPartSingleReflection(material);
#else
  lighting.reflectedColor = float3(0.0, 0.0, 0.0);
#endif
#ifdef MAIN_PART_GLASS_SURFACE_OFF_AMBIENT
  lighting.reflectedColor = material.gloss * 0.119999997;
#endif
  lighting.specular = materialCoordinateState.x;
  lighting.transmission = effectAnimationState.x;
  MainPartGlassSurfaceComposite composite =
      ComposeMainPartDissolveGlassSurface(
          v7, v8, v10 != 0, material, lighting);
  o0 = composite.color;
  o1 = composite.auxiliary;
  return;
}
#endif

#endif // MAIN_PART_GLASS_SURFACE_SHARED_INCLUDED
