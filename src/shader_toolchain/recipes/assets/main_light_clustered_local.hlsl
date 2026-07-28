// Recovered clustered-local-light path shared by the unadorned permutations.
// The arithmetic association intentionally follows the DXBC instruction order.

#include "indirect_cascade_upscale_primitives.hlsl"

struct MainLightSurface
{
  int3 pixel;
  float linearDepth;
  float4 albedo;
  float4 material;
  uint profile;
  float materialVisibility;
  float2 ambientOcclusion;
  float3 normal;
  float3 viewPosition;
  float3 worldPosition;
  float3 viewDirection;
  float3 tangent;
  float3 derivativeWorldPosition;
  float cameraRange;
  bool rejectBackLights;
  float specularBias;
  float specularPower;
  float specularExponent;
  float specularScale;
  float diffuseCompensation;
  float farLightFade;
};

struct MainLightCluster
{
  uint header;
  uint firstWord;
  uint ambientMask;
  uint pointMask;
  uint spotMask;
};

struct MainLightAccumulation
{
  float3 maximum;
  float3 additive;
};

float LinearizeMainLightDepth(float deviceDepth)
{
#if MAIN_LIGHT_COMPACT_ORTHO
  float linearDepth = 1.0 + -deviceDepth;
  linearDepth = linearDepth * cb_vInverseCameraRange.y
      + cb_vNearFarViewCorner.x;
  return linearDepth;
#else
  float denominator = cb_xViewToProjection._m22 + deviceDepth;
  return cb_xViewToProjection._m23 / denominator;
#endif
}

float3 DecodeMainLightNormal(float2 packedNormal)
{
  float2 octahedral = packedNormal * float2(2.0, 2.0)
      + float2(-1.0, -1.0);
  float z = 1.0 + -abs(octahedral.x);
  z = z + -abs(octahedral.y);
  float fold = saturate(-z);
  float2 nonnegative = octahedral >= float2(0.0, 0.0);
  float2 correction = nonnegative ? -fold.xx : fold.xx;
  float3 normal = float3(octahedral + correction, z);
  float inverseLength = rsqrt(dot(normal, normal));
  return normal * inverseLength.xxx;
}

float3 TransformMainLightPosition(float4x4 transform, float3 position)
{
  float3 result = transform._m01_m11_m21 * position.yyy;
  result = transform._m00_m10_m20 * position.xxx + result;
  result = transform._m02_m12_m22 * position.zzz + result;
  return transform._m03_m13_m23 + result;
}

float3 DecodeMainLightColor(uint packedColor)
{
  float3 channels;
  channels.x = (uint)(packedColor >> 24);
  channels.y = (uint)((packedColor >> 16) & 255u);
  channels.z = (uint)((packedColor >> 8) & 255u);
  channels.yz = float2(0.00392156886, 0.00392156886) * channels.yz;
  channels.x = 0.00392156886 * channels.x;
  return channels;
}

MainLightSurface LoadMainLightSurface(float2 uv)
{
  MainLightSurface surface;
  float2 viewportSize = asuint(cb_vuViewportSize.xy);
  surface.pixel.xy = (uint2)(uv * viewportSize);
  surface.pixel.z = 0;
  surface.linearDepth = LinearizeMainLightDepth(
      tDepth.Load(surface.pixel).x);
  surface.albedo = tDif.Load(surface.pixel);
  surface.material = tMat.Load(surface.pixel);
  float profile = surface.material.w * 255.0 + 0.5;
  profile = (uint)profile;
  surface.profile = (int)profile & 7;
  bool profileTwo = surface.profile == 2;
  bool profileOne = surface.profile == 1;
#if MAIN_LIGHT_COMPACT_TEMPORAL_AO
  float2 ambientOcclusion = tAo.Load(surface.pixel).xy;
  surface.ambientOcclusion = ambientOcclusion;
  if (profileTwo || profileOne)
  {
    float visibility = surface.material.z * ambientOcclusion.x + 0.5;
    surface.materialVisibility = min(1.0, visibility);
  }
  else
  {
    surface.materialVisibility = ambientOcclusion.x;
    if (surface.profile == 5)
    {
      float visibility = 0.349999994 + surface.materialVisibility;
      surface.materialVisibility = min(1.0, visibility);
    }
  }
  float cavityVisibility = saturate(0.800000012 + -ambientOcclusion.y);
  cavityVisibility = saturate(
      cavityVisibility * 0.200000003 + surface.materialVisibility);
  surface.materialVisibility = profileTwo || profileOne
      ? cavityVisibility
      : surface.materialVisibility;
#else
  surface.ambientOcclusion = float2(1.0, 1.0);
  if (profileTwo || profileOne)
  {
    float visibility = 0.5 + surface.material.z;
    surface.materialVisibility = min(1.0, visibility);
  }
  else
  {
    surface.materialVisibility = 1.0;
  }
#endif
  return surface;
}

void PrepareMainLightSurface(float2 uv, inout MainLightSurface surface)
{
  surface.normal = DecodeMainLightNormal(tNor.Load(surface.pixel).xy);

#if MAIN_LIGHT_COMPACT_HIGH
  bool anisotropicProfile = surface.profile == 4 || surface.profile == 6;
  if (anisotropicProfile)
  {
    float3 reference = abs(surface.normal.y) > 0.99000001
        ? float3(0.0, 0.0, 1.0)
        : float3(1.0, 0.0, 0.0);
    float3 tangent = cross(surface.normal, reference);
    tangent = tangent * rsqrt(dot(tangent, tangent)).xxx;
    float3 bitangent = cross(tangent, surface.normal);
    float angle = 6.28318548 * surface.material.z;
    float sine;
    float cosine;
    sincos(angle, sine, cosine);
    surface.tangent = sine.xxx * bitangent + cosine.xxx * tangent;
  }
  else
  {
    surface.tangent = float3(0.0, 1.0, 0.0);
  }
#else
  surface.tangent = float3(0.0, 1.0, 0.0);
#endif

  float2 clip = uv * float2(1.0, -1.0) + float2(0.0, 1.0);
  clip = clip * float2(2.0, 2.0) + float2(-1.0, -1.0);
#if MAIN_LIGHT_COMPACT_ORTHO
  surface.viewPosition.xy = cb_vNearFarViewCorner.zw * clip
      + cb_vViewTranslate.xy;
#else
  clip = cb_vNearFarViewCorner.zw * clip;
  surface.viewPosition.xy = clip * surface.linearDepth.xx;
#endif
  surface.viewPosition.z = -surface.linearDepth;
  surface.worldPosition = TransformMainLightPosition(
      viewToWorld, surface.viewPosition);

  float inverseViewLength = rsqrt(dot(-surface.viewPosition, -surface.viewPosition));
  surface.viewDirection = -surface.viewPosition * inverseViewLength.xxx;
  surface.cameraRange = cb_vInverseCameraRange.x * surface.linearDepth;

  bool profileSix = surface.profile == 6;
  bool profileSeven = surface.profile == 7;
  surface.rejectBackLights = surface.profile == 0;
  float specialProfile = profileSix || profileSeven;
  float profileScale = surface.material.x * 1.20000005 + 0.5;
  float profileBase = 1.0;
  if (specialProfile)
  {
    profileScale = 2.4000001;
    profileBase = 0.5;
  }

  float grazing = dot(surface.viewDirection, surface.normal);
  grazing = 1.0 + -abs(grazing);
  float roughnessSquared = surface.material.y * surface.material.y;
  surface.specularExponent = roughnessSquared * 750.0 + 35.0;
  float powerScale = roughnessSquared * profileScale + 1.79999995;
  powerScale = max(0.00999999978, powerScale);
  float powerBase = profileBase + surface.material.y;
  powerBase = grazing * powerBase;
  powerBase = max(0.00999999978, powerBase);
  powerBase = log2(powerBase);
  powerBase = powerScale * powerBase;
  surface.specularPower = exp2(powerBase);
  surface.specularBias = roughnessSquared * -0.5
      + (1.0 + -surface.material.x);
  surface.specularScale = dot(
      surface.material.xx, surface.material.yy);
#if MAIN_LIGHT_COMPACT_MEDIUM
  float diffuseLoss = surface.material.y
      + -(1.0 + -surface.material.x);
  diffuseLoss = max(0.0, diffuseLoss);
  surface.diffuseCompensation = 1.0 + -diffuseLoss;
#else
  surface.diffuseCompensation = 1.0;
#endif

  float3 derivative = ddx_coarse(surface.worldPosition);
  derivative = derivative + surface.worldPosition;
  derivative = ddy_coarse(surface.worldPosition) + derivative;
  surface.derivativeWorldPosition = derivative;
  surface.farLightFade = saturate(6.66666651 * surface.cameraRange);
  surface.farLightFade = 1.0 + -surface.farLightFade;
}

MainLightCluster ResolveMainLightCluster(float2 uv, float linearDepth)
{
  float slice = linearDepth * cb_cluster.fRcpClusterRange
      + cb_cluster.fClusterNearBias;
  slice = rsqrt(slice);
  slice = 1.0 / slice;
  slice = cb_cluster.vVoxelDims.z * slice;
  slice = floor(slice);
  slice = (uint)slice;
  float2 tile = cb_cluster.vVoxelDims.xy * uv;
  tile = (uint2)tile;
  float voxel = mad(
      (int)tile.y, asint(cb_cluster.uClusterWidth), (int)tile.x);
  voxel = mad(
      (int)slice, asint(cb_cluster.uClusterSliceSize), (int)voxel);
  uint header = sbVoxelLightIds[(int)voxel * 33].x;

  MainLightCluster cluster;
  cluster.header = header;
  cluster.firstWord = mad((int)voxel, 33, 1);
  cluster.ambientMask = (int)header & 255;
  cluster.pointMask = (int)header & 0xff00;
  cluster.spotMask = (int)header & 0xff0000;
  return cluster;
}

float3 EvaluateMainLightCamera(MainLightSurface surface)
{
  float visibility = saturate(surface.materialVisibility);
  float range = saturate(cb_fCameraLightInvRange * surface.cameraRange);
  range = 1.0 + -range;
  float inverseViewLength = rsqrt(dot(
      surface.viewPosition, surface.viewPosition));
  float3 viewDirection = surface.viewPosition * inverseViewLength.xxx;
  float facing = dot(surface.normal, -viewDirection);
  facing = facing * 0.75 + 0.25;
  float intensity = cb_fCameraLightIntensity * range;
  intensity = intensity * visibility;
  intensity = facing * intensity;
  float3 lighting = cb_vCameraLightColor.xyz * intensity.xxx;
  lighting = lighting * surface.albedo.xyz;
  return max(float3(0.0, 0.0, 0.0), lighting);
}

#if MAIN_LIGHT_COMPACT_DIRECTIONAL_SHADOWS
float EvaluateMainLightCloudShadow(float3 worldPosition)
{
  if (cb_clouds.fCloudShadowCoveragesInv >= 1.0)
    return 0.0;
  float3 planetRelative = -cb_clouds.vPlanetCenter.xyz + worldPosition;
  float projectedDistance = dot(
      planetRelative, -cb_vDirectionalLightDirectionWorld.xyz);
  float discriminant = dot(planetRelative, planetRelative)
      + -cb_clouds.fAtmosphereRadiusSqr;
  discriminant = projectedDistance * projectedDistance + -discriminant;
  discriminant = max(0.0, discriminant);
  float root = sqrt(discriminant);
  float distanceA = -projectedDistance + root;
  float distanceB = -projectedDistance + -root;
  float rayDistance = max(distanceA, distanceB);
  float2 cloudUv = -cb_vDirectionalLightDirectionWorld.xy
      * rayDistance.xx + cb_clouds.vRawScroll.xy;
  cloudUv = cloudUv + worldPosition.xy;
  cloudUv = float2(9.2307695e-05, 9.2307695e-05) * cloudUv;
  float shadow = tCloudMap.SampleLevel(LinearWrapWrap_s, cloudUv, 0).x;
  shadow = -cb_clouds.fCloudShadowCoveragesInv + shadow;
  shadow = 5.88235283 * shadow;
  shadow = min(1.0, shadow);
  shadow = 1.0 + -shadow;
  bool belowSoftEdge = shadow < 0.300000012;
  float maximumShadow = -cb_clouds.fCloudCoveragesInv
      * cb_clouds.fCloudCoveragesInv + 1.0;
  float softEdge = 0.300000012 + -shadow;
  shadow = 1.0 / shadow;
  shadow = saturate(softEdge * shadow);
  shadow = 1.0 + -shadow;
  shadow = shadow * shadow;
  shadow = -shadow * shadow + 1.0;
  shadow = min(maximumShadow, shadow);
  return belowSoftEdge ? shadow : 0.0;
}
#endif

#if MAIN_LIGHT_COMPACT_DIRECTIONAL
float3 EvaluateMainLightDirectional(MainLightSurface surface)
{
  float rawNormalDotLight = dot(
      surface.normal, -cb_vDirectionalLightDirectionView.xyz);
  float shadowResponse = 1.0;
  float materialVisibility = surface.materialVisibility;
#if MAIN_LIGHT_COMPACT_DIRECTIONAL_SHADOWS
  float cloudShadow = EvaluateMainLightCloudShadow(surface.worldPosition);
  bool profileTwo = surface.profile == 2;
  bool profileOne = surface.profile == 1;
#if MAIN_LIGHT_COMPACT_TEMPORAL_AO
  shadowResponse = saturate(surface.ambientOcclusion.y + -cloudShadow);
  if (profileTwo || profileOne)
  {
    float cavityVisibility = 0.800000012 + -shadowResponse;
    cavityVisibility = max(0.0, cavityVisibility);
    cavityVisibility = saturate(
        cavityVisibility * 0.200000003 + surface.ambientOcclusion.x);
    materialVisibility = cavityVisibility;
  }
#else
  if (profileTwo || profileOne)
  {
    float cloudVisibility = 1.0 + -cloudShadow;
    cloudVisibility = min(1.0, cloudVisibility);
    cloudVisibility = 0.800000012 + -cloudVisibility;
    cloudVisibility = max(0.0, cloudVisibility);
    cloudVisibility = saturate(
        cloudVisibility * 0.200000003 + materialVisibility);
    materialVisibility = cloudVisibility;
  }
  UpscaleCascadeSelection cascade = SelectUpscaleCascade(
      surface.worldPosition,
      cb_arrCascades[0], cb_arrCascades[1],
      cb_arrCascades[2], cb_arrCascades[3]);
  float cameraRangeFade = 1.0 + -surface.cameraRange;
#if MAIN_LIGHT_COMPACT_MEDIUM
  float cascadeVisibility = EvaluateUpscaleMediumCascadeShadow(
      taCascades, sShadowSamplerLinear_s, cascade,
      surface.worldPosition, cameraRangeFade,
      cb_vCascadeSplits, cb_vCascadeSize, cb_vCascadePixelSize,
      cb_arrCascades[1], cb_arrCascades[2], cb_arrCascades[3]);
#else
  float cascadeVisibility = EvaluateUpscaleLowCascadeShadow(
      taCascades, sShadowSamplerLinear_s, cascade,
      surface.worldPosition, cameraRangeFade,
      cb_vCascadeSplits, cb_vCascadeSize, cb_vCascadePixelSize,
      cb_arrCascades[1], cb_arrCascades[2], cb_arrCascades[3]);
#endif
  float facing = 0.400000006 + rawNormalDotLight;
  facing = saturate(1.66666663 * facing);
  float facingCurve = facing * -2.0 + 3.0;
  facing = facing * facing;
  facing = facingCurve * facing;
  shadowResponse = saturate(cascadeVisibility * facing + -cloudShadow);
#endif
#endif
  float lightMapNormal = rawNormalDotLight * 0.5 + 0.5;
  float litNormal = rawNormalDotLight * shadowResponse;
  litNormal = litNormal * 0.5 + 0.5;

  float viewDistance = sqrt(dot(
      surface.viewPosition, surface.viewPosition));
  float distanceBlend = 0.00400000019 * viewDistance;
  distanceBlend = min(1.0, distanceBlend);
  float nearWeight = 1.0 + -distanceBlend;
  nearWeight = nearWeight * nearWeight;
  float missingVisibility = 1.0 + -materialVisibility;
  float visibility = distanceBlend * missingVisibility
      + materialVisibility;
  visibility = visibility * visibility;
  float visibilityFourth = visibility * visibility;
  float farCurve = 0.400000006 * visibilityFourth;
  float nearCurve = visibility * 0.200000018 + 0.400000006;
  nearCurve = -visibilityFourth * 0.400000006 + nearCurve;
  nearCurve = nearWeight * nearCurve + farCurve;
  float denominator = 1.0 + -nearCurve;
  float upperDenominator = 1.20000005 + -nearCurve;
  float ramp = saturate(lightMapNormal + -nearCurve);
  ramp = ramp / denominator;
  ramp = ramp * ramp;
  float lightMapV = ramp * upperDenominator + nearCurve;

  float2 lightMapUv = float2(cb_fTimeOfDay, saturate(lightMapNormal));
  float3 lightColor = tLightColorMap.SampleLevel(
      LinearWrapClamp_s, lightMapUv, 0).xyz;
  lightColor = -cb_vDirectionalShadowColor.xyz + lightColor;
  float colorRamp = lightMapNormal * shadowResponse;
  lightColor = colorRamp.xxx * lightColor
      + cb_vDirectionalShadowColor.xyz;
  lightMapV = cb_fDirectionalLightMapMul * lightMapV;
  lightColor = lightColor * lightMapV.xxx;

  float3 halfVector = surface.viewDirection
      + -cb_vDirectionalLightDirectionView.xyz;
  float inverseHalfLength = rsqrt(dot(halfVector, halfVector));
  halfVector = halfVector * inverseHalfLength.xxx;
  float normalDotHalf = dot(halfVector, surface.normal);
  normalDotHalf = normalDotHalf * 0.5 + 0.5;
  float intensity = cb_fDirectionalLightIntensity * litNormal;
  float specular = log2(abs(normalDotHalf));
  specular = specular * surface.specularExponent;
  specular = exp2(specular);
  specular = specular * intensity;
  specular = specular * surface.specularScale;
  float broadSpecular = abs(normalDotHalf) * abs(normalDotHalf)
      + -surface.specularBias;
  broadSpecular = broadSpecular * (1.0 + surface.specularBias);
  broadSpecular = broadSpecular * surface.specularPower;
  broadSpecular = saturate(broadSpecular * intensity);
  broadSpecular = max(broadSpecular, specular);
  float3 lighting = broadSpecular.xxx * lightColor;
  float3 diffuse = surface.albedo.xyz * lightColor;
  diffuse = diffuse * surface.diffuseCompensation.xxx;
  lighting = diffuse + lighting;
  lighting = lighting * materialVisibility.xxx;
  return max(float3(0.0, 0.0, 0.0), lighting);
}
#endif

float3 AccumulateMainLightAmbient(
    MainLightSurface surface, MainLightCluster cluster, float3 maximum)
{
  uint mask = cluster.ambientMask;
  while (mask != 0)
  {
    uint wordBit = firstbitlow(mask);
    uint wordMask = 1u << wordBit;
    mask = mask ^ wordMask;
    uint lightWord = sbVoxelLightIds[cluster.firstWord + wordBit].x;
    uint wordBase = wordBit << 5;
    while (lightWord != 0)
    {
      uint lightBit = firstbitlow(lightWord);
      lightWord = lightWord ^ (1u << lightBit);
      uint lightIndex = wordBase + lightBit;
      float3 toLight = cb_arrAmbient[lightIndex].vPosition.xyz
          + -surface.viewPosition;
      float distanceSquared = dot(toLight, toLight);
      float distanceToLight = sqrt(distanceSquared);
      float normalizedDistance = saturate(
          cb_arrAmbient[lightIndex].fRcpRadius * distanceToLight);
      float inverseDistance = rsqrt(distanceSquared);
      toLight = toLight * inverseDistance.xxx;
      float diffuse = dot(toLight, surface.normal);
      diffuse = diffuse * 0.5 + 0.5;
      float radial = normalizedDistance * normalizedDistance;
      radial = -radial * radial + 1.0;
      radial = radial * surface.materialVisibility;
      float3 color = cb_arrAmbient[lightIndex].vColor.xyz
          * surface.albedo.xyz;
      float intensity = cb_arrAmbient[lightIndex].fIntensity * radial;
      intensity = intensity * surface.farLightFade;
      intensity = intensity * diffuse;
      color = color * intensity.xxx;
      maximum = max(color, maximum);
    }
  }
  return maximum;
}

#if MAIN_LIGHT_COMPACT_HIGH
float3 EvaluateMainLightHighBrdf(
    MainLightSurface surface,
    float3 lightDirection,
    float rawIntensity,
    float diffuseFactor,
    float3 packedColor)
{
  float diffuseIntensity = rawIntensity * diffuseFactor;
  float3 diffuseLight = packedColor * diffuseIntensity.xxx;
  float3 rawLight = packedColor * rawIntensity.xxx;
  float3 halfVector = surface.viewDirection + lightDirection;
  halfVector = halfVector * rsqrt(dot(halfVector, halfVector)).xxx;
  float normalDotHalf = dot(halfVector, surface.normal);
  normalDotHalf = normalDotHalf * 0.5 + 0.5;

  float materialX = surface.material.x;
  float materialY = surface.material.y;
  float materialZ = surface.material.z;
  float normalDotView = dot(surface.viewDirection, surface.normal);
  float grazing = 1.0 + -abs(normalDotView);
  float grazingSquared = grazing * grazing;
  float roughnessSquared = materialY * materialY;
  float specularScale = dot(
      surface.material.xx, surface.material.yy);
  float defaultExponent = roughnessSquared * 750.0 + 35.0;
  bool specialProfile = surface.profile == 6 || surface.profile == 7;
  float powerScale = roughnessSquared
      * (specialProfile ? 2.4000001 : materialX * 1.20000005 + 0.5)
      + 1.79999995;
  powerScale = max(0.00999999978, powerScale);
  float profilePowerBase = specialProfile ? 0.5 : 1.0;
  float powerBase = grazing * (profilePowerBase + materialY);
  powerBase = max(0.00999999978, powerBase);
  powerBase = log2(powerBase);
  float specularPower = exp2(powerBase * powerScale);
  float specularBias = roughnessSquared * -0.5 + (1.0 + -materialX);
  float diffuseLoss = materialX + materialY + -1.0;
  diffuseLoss = max(0.0, diffuseLoss);
  float diffuseCompensation = 1.0 + -diffuseLoss;
  float3 diffuseLighting = diffuseLight * surface.albedo.xyz;
  diffuseLighting = diffuseLighting * diffuseCompensation.xxx;
  uint profileIndex = ((uint)(surface.material.w * 255.0 + 0.5)) >> 3;

  float narrowSpecular = log2(abs(normalDotHalf));
  narrowSpecular = narrowSpecular * defaultExponent;
  narrowSpecular = exp2(narrowSpecular);
  narrowSpecular = narrowSpecular * diffuseIntensity;
  narrowSpecular = narrowSpecular * specularScale;
  float broadSpecular = abs(normalDotHalf) * abs(normalDotHalf)
      + -specularBias;
  broadSpecular = broadSpecular * (1.0 + specularBias);
  broadSpecular = broadSpecular * specularPower;
  broadSpecular = saturate(broadSpecular * diffuseIntensity);

  if (surface.profile == 1 || surface.profile == 2)
  {
    float transmission = dot(-lightDirection, surface.viewDirection);
    transmission = max(0.0, transmission);
    transmission = transmission * grazingSquared;
    float subdermal = saturate(
        (1.0 + -materialZ) * 0.644999981 + -0.300000012);
    transmission = transmission * subdermal;
    transmission = min(1.0, transmission);
    transmission = transmission * saturate(rawIntensity);
    float3 transmitted = rawLight * surface.albedo.xyz;
    diffuseLighting = transmitted * transmission.xxx + diffuseLighting;
    float specular = max(broadSpecular, narrowSpecular);
    return specular.xxx * diffuseLight + diffuseLighting;
  }

  if (surface.profile == 3)
  {
    float backscatter = dot(-lightDirection, surface.viewDirection);
    backscatter = backscatter * 0.5 + 0.5;
    backscatter = backscatter * backscatter;
    float wrapped = abs(normalDotHalf) * diffuseFactor;
    wrapped = wrapped * cb_profiles.arrSkin[profileIndex].fSubdermalStrength
        + cb_profiles.arrSkin[profileIndex].fSubdermalOffset;
    backscatter = backscatter * grazingSquared;
    backscatter = cb_profiles.arrSkin[profileIndex].fTranslucency
        * backscatter;
    wrapped = max(backscatter, wrapped);
    wrapped = wrapped * rawIntensity;
    wrapped = wrapped * materialZ;
    diffuseLighting = wrapped.xxx
        * cb_profiles.arrSkin[profileIndex].vSubdermalColor.xyz
        + diffuseLighting;
    float skinExponent = cb_profiles.arrSkin[profileIndex].fBroadLobeScale
        * defaultExponent;
    float skinSpecular = log2(abs(normalDotHalf));
    skinSpecular = exp2(skinSpecular * skinExponent);
    skinSpecular = skinSpecular * skinSpecular;
    float defaultLobe = log2(abs(normalDotHalf));
    defaultLobe = exp2(defaultLobe * defaultExponent);
    skinSpecular = max(skinSpecular, defaultLobe);
    skinSpecular = skinSpecular * diffuseIntensity;
    float fresnel = grazingSquared * grazingSquared;
    fresnel = fresnel * abs(grazing);
    fresnel = min(1.0, fresnel);
    fresnel = fresnel * materialY;
    float specular = max(
        diffuseIntensity * fresnel,
        skinSpecular * roughnessSquared);
    return specular.xxx * diffuseLight + diffuseLighting;
  }

  float3 bitangent = cross(surface.tangent, surface.normal);
  bitangent = bitangent * rsqrt(dot(bitangent, bitangent)).xxx;
  float tangentDotHalf = dot(surface.tangent, halfVector);
  float bitangentDotHalf = dot(bitangent, halfVector);
  float albedoMaximum = max(
      surface.albedo.x, max(surface.albedo.y, surface.albedo.z));
  float hairDiffuse = albedoMaximum
      * cb_profiles.arrHair[profileIndex].fDiffuseCompensation + 1.0;
  float hairTransmission = 1.0 + -albedoMaximum;
  hairTransmission = hairTransmission * grazingSquared;
  hairTransmission = saturate(
      cb_profiles.arrHair[profileIndex].fTranslucency * hairTransmission);

  if (surface.profile == 4)
  {
    float2 anisotropy = max(
        cb_profiles.arrMetal[profileIndex].vAnisotropy.xy,
        float2(9.99999975e-05, 9.99999975e-05));
    float2 anisotropicHalf = float2(tangentDotHalf, bitangentDotHalf)
        / anisotropy;
    anisotropicHalf = anisotropicHalf * anisotropicHalf;
    float lobe = min(1.0, anisotropicHalf.x + anisotropicHalf.y);
    lobe = log2(lobe);
    lobe = cb_profiles.arrHair[profileIndex].fShininess * lobe;
    lobe = exp2(lobe);
    lobe = 1.0 + -lobe;
    lobe = lobe * specularScale;
    lobe = lobe * diffuseIntensity;
    float3 transmitted = rawLight * surface.albedo.xyz;
    diffuseLighting = transmitted
        * (saturate(rawIntensity) * hairTransmission).xxx
        + diffuseLighting;
    broadSpecular = max(broadSpecular, lobe);
    float3 oneMinusSpecular = 1.0 + -lerp(
        surface.albedo.xyz,
        cb_profiles.arrMetal[profileIndex].vSpecularColor.xyz,
        cb_profiles.arrMetal[profileIndex].vSpecularColor.w);
    float average = dot(
        oneMinusSpecular, float3(0.333333343, 0.333333343, 0.333333343));
    float compensation = cb_profiles.arrMetal[profileIndex]
        .fDiffuseCompensation * abs(average);
    float3 specularColor = diffuseLight + compensation.xxx;
    return broadSpecular.xxx * specularColor + diffuseLighting;
  }

  if (surface.profile == 5)
  {
    float wrappedDiffuse = diffuseFactor * 0.75 + 0.25;
    float inverseWrapped = 1.0 + -wrappedDiffuse;
    wrappedDiffuse = max(0.75, wrappedDiffuse);
    wrappedDiffuse = -materialY * abs(normalDotView) + wrappedDiffuse;
    wrappedDiffuse = inverseWrapped * grazingSquared + wrappedDiffuse;
    wrappedDiffuse = min(wrappedDiffuse, surface.materialVisibility);
    wrappedDiffuse = rawIntensity * wrappedDiffuse;
    wrappedDiffuse = 0.75 * wrappedDiffuse;
    float3 transmitted = rawLight * surface.albedo.xyz;
    diffuseLighting = transmitted * wrappedDiffuse.xxx + diffuseLighting;
    float specular = max(broadSpecular, narrowSpecular);
    return specular.xxx * diffuseLight + diffuseLighting;
  }

  if (surface.profile == 6 || surface.profile == 7)
  {
    float2 denominator;
    denominator.x = 1.0;
    denominator.y = (1.0 + -materialX) * materialY;
    denominator.y = denominator.y * -0.899999976 + 1.0;
    denominator.y = max(9.99999975e-05, denominator.y);
    float exponent = materialX;
    float anisotropicBias = materialX * 0.5 + specularBias + 0.5;
    float3 specularTint = diffuseLight;
    if (surface.profile == 6)
    {
      denominator = max(
          cb_profiles.arrMetal[profileIndex].vAnisotropy.xy,
          float2(9.99999975e-05, 9.99999975e-05));
      exponent = cb_profiles.arrMetal[profileIndex].fShininess
          * specularScale;
      anisotropicBias = exponent * 0.5 + specularBias + 0.5;
      float3 metalSpecular = lerp(
          surface.albedo.xyz,
          cb_profiles.arrMetal[profileIndex].vSpecularColor.xyz,
          cb_profiles.arrMetal[profileIndex].vSpecularColor.w);
      float3 oneMinusSpecular = 1.0 + -metalSpecular;
      float average = dot(oneMinusSpecular,
          float3(0.333333343, 0.333333343, 0.333333343));
      float compensation = cb_profiles.arrMetal[profileIndex]
          .fDiffuseCompensation * abs(average);
      specularTint = diffuseLight * metalSpecular + compensation.xxx;
    }
    float2 anisotropicHalf = float2(tangentDotHalf, bitangentDotHalf)
        / denominator;
    anisotropicHalf = anisotropicHalf * anisotropicHalf;
    float lobe = min(1.0, anisotropicHalf.x + anisotropicHalf.y);
    lobe = log2(lobe);
    lobe = exponent * lobe;
    lobe = exp2(lobe);
    lobe = 1.0 + -lobe;
    lobe = lobe * specularScale;
    lobe = lobe * diffuseIntensity;
    float anisotropicBroad = abs(normalDotHalf) * abs(normalDotHalf)
        + -specularBias;
    anisotropicBroad = anisotropicBroad * anisotropicBias;
    anisotropicBroad = anisotropicBroad * specularPower;
    anisotropicBroad = saturate(anisotropicBroad * diffuseIntensity);
    float specular = max(anisotropicBroad, lobe);
    return specular.xxx * specularTint + diffuseLighting;
  }

  float specular = max(broadSpecular, narrowSpecular);
  return specular.xxx * diffuseLight + diffuseLighting;
}
#endif

void AccumulateMainLightPoint(
    MainLightSurface surface,
    MainLightCluster cluster,
    inout MainLightAccumulation accumulation)
{
  uint mask = cluster.pointMask;
  while (mask != 0)
  {
    uint wordBit = firstbitlow(mask);
    mask = mask ^ (1u << wordBit);
    uint lightWord = sbVoxelLightIds[cluster.firstWord + wordBit].x;
    uint wordBase = wordBit << 5;
    while (lightWord != 0)
    {
      uint lightBit = firstbitlow(lightWord);
      lightWord = lightWord ^ (1u << lightBit);
      uint lightIndex = wordBase + lightBit - 256;
      float3 toLight = cb_arrPoint[lightIndex].vPosition.xyz
          + -surface.viewPosition;
      float distanceToLight = sqrt(dot(toLight, toLight));
      float safeDistance = max(0.00100000005, distanceToLight);
      toLight = toLight / safeDistance.xxx;
      float normalDotLight = dot(toLight, surface.normal);
      if (!(surface.rejectBackLights && normalDotLight < -0.25))
      {
        float normalizedDistance = saturate(
            cb_arrPoint[lightIndex].fRcpRadius * distanceToLight);
        float radial = -0.100000001 + normalizedDistance;
        radial = max(0.0, radial);
        radial = 1.11111116 * radial;
        radial = radial * radial;
        float2 diffuseCurve = radial * float2(0.275362313, -0.379999995)
            + float2(0.724637687, 0.379999995);
        float diffuse = normalDotLight * diffuseCurve.x + diffuseCurve.y;
        diffuse = max(0.0, diffuse);
        normalizedDistance = max(0.00999999978, normalizedDistance);
        normalizedDistance = log2(normalizedDistance);
        normalizedDistance = cb_arrPoint[lightIndex].fFalloffFactor
            * normalizedDistance;
        normalizedDistance = exp2(normalizedDistance);
        normalizedDistance = 1.0 + -normalizedDistance;
        float intensity = cb_arrPoint[lightIndex].fIntensity
            * normalizedDistance;
        intensity = intensity * surface.materialVisibility;
        intensity = min(cb_arrPoint[lightIndex].fMaxIntensity, intensity);
        float3 color = DecodeMainLightColor(cb_arrPoint[lightIndex].uColor);
#if MAIN_LIGHT_COMPACT_HIGH
        float3 lighting = EvaluateMainLightHighBrdf(
            surface, toLight, intensity, diffuse, color);
#else
        intensity = intensity * diffuse;
        color = color * intensity.xxx;

        float3 halfVector = surface.viewDirection + toLight;
        float inverseHalfLength = rsqrt(dot(halfVector, halfVector));
        halfVector = halfVector * inverseHalfLength.xxx;
        float normalDotHalf = dot(halfVector, surface.normal);
        normalDotHalf = normalDotHalf * 0.5 + 0.5;
        float specular = log2(abs(normalDotHalf));
        specular = specular * surface.specularExponent;
        specular = exp2(specular);
        specular = specular * intensity;
        specular = specular * surface.specularScale;
        float broadSpecular = abs(normalDotHalf) * abs(normalDotHalf)
            + -surface.specularBias;
        broadSpecular = broadSpecular * (1.0 + surface.specularBias);
        broadSpecular = broadSpecular * surface.specularPower;
        broadSpecular = saturate(broadSpecular * intensity);
        broadSpecular = max(broadSpecular, specular);
        float3 lighting = broadSpecular.xxx * color;
        float3 diffuseLighting = surface.albedo.xyz * color;
        diffuseLighting = diffuseLighting * surface.diffuseCompensation.xxx;
        lighting = diffuseLighting + lighting;
#endif
        bool additive = (cb_arrPoint[lightIndex].uColor & 1u) != 0;
        float3 positive = max(float3(0.0, 0.0, 0.0), lighting);
        accumulation.additive = additive
            ? positive + accumulation.additive
            : accumulation.additive;
        accumulation.maximum = additive
            ? accumulation.maximum
            : max(lighting, accumulation.maximum);
      }
    }
  }
}

void AccumulateMainLightSpot(
    MainLightSurface surface,
    MainLightCluster cluster,
    inout MainLightAccumulation accumulation)
{
#if MAIN_LIGHT_COMPACT_SSS
  float4 subsurfaceMask = tSSS.Load(surface.pixel);
  bool useSubsurfaceMask = (cluster.header & cb_cluster.uSSMask) != 0;
  if (!useSubsurfaceMask)
    subsurfaceMask = float4(1.0, 1.0, 1.0, 1.0);
#endif
  uint mask = cluster.spotMask;
  while (mask != 0)
  {
    uint wordBit = firstbitlow(mask);
    mask = mask ^ (1u << wordBit);
    uint lightWord = sbVoxelLightIds[cluster.firstWord + wordBit].x;
    uint wordBase = wordBit << 5;
    while (lightWord != 0)
    {
      uint lightBit = firstbitlow(lightWord);
      lightWord = lightWord ^ (1u << lightBit);
      uint lightIndex = wordBase + lightBit - 512;
      float3 toLight = cb_arrSpot[lightIndex].vPosition.xyz
          + -surface.viewPosition;
      float distanceToLight = sqrt(dot(toLight, toLight));
      float normalizedDistance = cb_arrSpot[lightIndex].fRcpRange
          * distanceToLight;
      if (normalizedDistance <= 1.0)
      {
        float safeDistance = max(0.00100000005, distanceToLight);
        toLight = toLight / safeDistance.xxx;
        float cone = dot(-toLight, cb_arrSpot[lightIndex].vForward.xyz);
        if (cone > 0.0)
        {
          float normalDotLight = dot(toLight, surface.normal);
          if (!(surface.rejectBackLights && normalDotLight < -0.25))
          {
            float4 projected = cb_arrSpot[lightIndex].xClip._m01_m11_m21_m31
                * surface.worldPosition.yyyy;
            projected = cb_arrSpot[lightIndex].xClip._m00_m10_m20_m30
                * surface.worldPosition.xxxx + projected;
            projected = cb_arrSpot[lightIndex].xClip._m02_m12_m22_m32
                * surface.worldPosition.zzzz + projected;
            projected = cb_arrSpot[lightIndex].xClip._m03_m13_m23_m33
                + projected;
            projected.xyz = projected.xyz / projected.www;
            float2 cookieUv = projected.xy * float2(0.5, 0.5)
                + float2(0.5, 0.5);
            cone = saturate(cone * cb_arrSpot[lightIndex].fCutoffScale
                + cb_arrSpot[lightIndex].fCutoffOffset);
            if ((cb_arrSpot[lightIndex].uColor & 240u) != 0)
            {
              float3 projectedDerivative =
                  cb_arrSpot[lightIndex].xClip._m01_m11_m31
                  * surface.derivativeWorldPosition.yyy;
              projectedDerivative = cb_arrSpot[lightIndex].xClip._m00_m10_m30
                  * surface.derivativeWorldPosition.xxx + projectedDerivative;
              projectedDerivative = cb_arrSpot[lightIndex].xClip._m02_m12_m32
                  * surface.derivativeWorldPosition.zzz + projectedDerivative;
              projectedDerivative = cb_arrSpot[lightIndex].xClip._m03_m13_m33
                  + projectedDerivative;
              float2 cookieGradient = projectedDerivative.xy
                  / projectedDerivative.zz;
              cookieGradient = cookieGradient * float2(0.5, 0.5)
                  + float2(0.5, 0.5);
              cookieGradient = cookieUv + -cookieGradient;
              uint cookieIndex = ((cb_arrSpot[lightIndex].uColor >> 4) & 15u)
                  - 1u;
              float3 cookieCoordinate;
              cookieCoordinate.xy = cb_cookies[cookieIndex].vScroll.xy
                  + cookieUv;
              cookieCoordinate.z = cookieIndex;
#if MAIN_LIGHT_COMPACT_FLOW_COOKIE
              float cookie;
              if (cb_cookies[cookieIndex].fFlowB
                  != cb_cookies[cookieIndex].fFlowA)
              {
                float2 flow = taCookiesFlow.SampleGrad(
                    LinearWrapWrap_s, cookieCoordinate,
                    cookieGradient.x, cookieGradient.y).xy;
                flow = flow * float2(2.0, 2.0) + float2(-1.0, -1.0);
                float3 coordinateA = cookieCoordinate;
                coordinateA.xy = -flow * cb_cookies[cookieIndex].fFlowA
                    + cookieCoordinate.xy;
                float sampleA = taCookies.SampleGrad(
                    LinearWrapWrap_s, coordinateA,
                    cookieGradient.x, cookieGradient.y).x;
                float3 coordinateB = cookieCoordinate;
                coordinateB.xy = -flow * cb_cookies[cookieIndex].fFlowB
                    + cookieCoordinate.xy;
                float sampleB = taCookies.SampleGrad(
                    LinearWrapWrap_s, coordinateB,
                    cookieGradient.x, cookieGradient.y).x;
                cookie = cb_cookies[cookieIndex].fFlowBlend
                    * (sampleB + -sampleA) + sampleA;
              }
              else
              {
                cookie = taCookies.SampleGrad(
                    LinearWrapWrap_s, cookieCoordinate,
                    cookieGradient.x, cookieGradient.y).x;
              }
#else
              float cookie = taCookies.SampleGrad(
                  LinearWrapWrap_s, cookieCoordinate,
                  cookieGradient.x, cookieGradient.y).x;
#endif
              cone = cookie * cone;
            }
#if MAIN_LIGHT_COMPACT_SHADOWS
            if (cb_arrSpot[lightIndex].shadowProps.fScale != 0.0)
            {
              float2 atlasScale;
              atlasScale.x = cb_arrSpot[lightIndex].shadowProps.fScale
                  * cb_cluster.fShadowAtlasAspect;
              atlasScale.y = cb_arrSpot[lightIndex].shadowProps.fScale;
              float2 atlasUv = cookieUv * atlasScale
                  + cb_arrSpot[lightIndex].shadowProps.vPosition.xy;
              float shadowDepth = -normalDotLight * normalDotLight + 1.0;
              shadowDepth = sqrt(shadowDepth);
              shadowDepth = shadowDepth * 0.000500000024 + 0.00079999998;
              shadowDepth = shadowDepth / projected.w;
              shadowDepth = projected.z + shadowDepth;
              float visibility = tShadowAtlas.SampleCmpLevelZero(
                  sShadowSamplerLinear_s, atlasUv, shadowDepth).x;
#if MAIN_LIGHT_COMPACT_SSS
              uint subsurfaceIndex = cb_arrSpot[lightIndex].uSSSIndex;
              float subsurfaceVisibility = subsurfaceMask[subsurfaceIndex];
              float inverseSubsurface = 1.0 + -subsurfaceVisibility;
              subsurfaceVisibility = cb_arrSpot[lightIndex].fSSSMask
                  * inverseSubsurface + subsurfaceVisibility;
              visibility = min(subsurfaceVisibility, visibility);
#endif
              visibility = cb_arrSpot[lightIndex].shadowProps.fFade
                  + visibility;
              visibility = min(1.0, visibility);
              cone = visibility * cone;
            }
#endif
            cone = cone * surface.materialVisibility;
            if (cone > 0.0)
            {
              normalizedDistance = max(0.00999999978, normalizedDistance);
              normalizedDistance = log2(normalizedDistance);
              normalizedDistance = cb_arrSpot[lightIndex].fFalloffFactor
                  * normalizedDistance;
              normalizedDistance = exp2(normalizedDistance);
              normalizedDistance = 1.0 + -normalizedDistance;
              float intensity = cb_arrSpot[lightIndex].fIntensity
                  * normalizedDistance;
              intensity = intensity * cone;
              intensity = min(cb_arrSpot[lightIndex].fMaxIntensity, intensity);
              float radial = distanceToLight
                  * cb_arrSpot[lightIndex].fRcpRange + -0.100000001;
              radial = max(0.0, radial);
              radial = 1.11111116 * radial;
              radial = radial * radial;
              float2 diffuseCurve = radial
                  * float2(0.275362313, -0.379999995)
                  + float2(0.724637687, 0.379999995);
              float diffuse = normalDotLight * diffuseCurve.x
                  + diffuseCurve.y;
              diffuse = max(0.0, diffuse);
              float3 color = DecodeMainLightColor(
                  cb_arrSpot[lightIndex].uColor);
#if MAIN_LIGHT_COMPACT_HIGH
              float3 lighting = EvaluateMainLightHighBrdf(
                  surface, toLight, intensity, diffuse, color);
#else
              intensity = intensity * diffuse;
              color = color * intensity.xxx;

              float3 halfVector = surface.viewDirection + toLight;
              float inverseHalfLength = rsqrt(dot(halfVector, halfVector));
              halfVector = halfVector * inverseHalfLength.xxx;
              float normalDotHalf = dot(halfVector, surface.normal);
              normalDotHalf = normalDotHalf * 0.5 + 0.5;
              float specular = log2(abs(normalDotHalf));
              specular = specular * surface.specularExponent;
              specular = exp2(specular);
              specular = specular * intensity;
              specular = specular * surface.specularScale;
              float broadSpecular = abs(normalDotHalf) * abs(normalDotHalf)
                  + -surface.specularBias;
              broadSpecular = broadSpecular * (1.0 + surface.specularBias);
              broadSpecular = broadSpecular * surface.specularPower;
              broadSpecular = saturate(broadSpecular * intensity);
              broadSpecular = max(broadSpecular, specular);
              float3 lighting = broadSpecular.xxx * color;
              float3 diffuseLighting = surface.albedo.xyz * color;
              diffuseLighting = diffuseLighting
                  * surface.diffuseCompensation.xxx;
              lighting = diffuseLighting + lighting;
#endif
              bool additive = (cb_arrSpot[lightIndex].uColor & 1u) != 0;
              float3 positive = max(float3(0.0, 0.0, 0.0), lighting);
              accumulation.additive = additive
                  ? positive + accumulation.additive
                  : accumulation.additive;
              accumulation.maximum = additive
                  ? accumulation.maximum
                  : max(lighting, accumulation.maximum);
            }
          }
        }
      }
    }
  }
}

float3 EvaluateMainLightClusteredLocal(float2 uv)
{
  MainLightSurface surface = LoadMainLightSurface(uv);
  MainLightAccumulation lighting;
#if MAIN_LIGHT_COMPACT_CAMERA || MAIN_LIGHT_COMPACT_DIRECTIONAL
  PrepareMainLightSurface(uv, surface);
#endif
#if MAIN_LIGHT_COMPACT_CAMERA
  lighting.maximum = EvaluateMainLightCamera(surface);
#else
  lighting.maximum = float3(0.0, 0.0, 0.0);
#endif
#if MAIN_LIGHT_COMPACT_DIRECTIONAL
  lighting.maximum = max(
      EvaluateMainLightDirectional(surface), lighting.maximum);
#endif
  lighting.additive = float3(0.0, 0.0, 0.0);
#if MAIN_LIGHT_COMPACT_HORIZON \
    && !MAIN_LIGHT_COMPACT_CAMERA \
    && !MAIN_LIGHT_COMPACT_DIRECTIONAL
  PrepareMainLightSurface(uv, surface);
#endif
  if (surface.linearDepth < cb_cluster.fClusterMaxFarLights)
  {
#if !MAIN_LIGHT_COMPACT_HORIZON \
    && !MAIN_LIGHT_COMPACT_CAMERA \
    && !MAIN_LIGHT_COMPACT_DIRECTIONAL
    PrepareMainLightSurface(uv, surface);
#endif
    MainLightCluster cluster = ResolveMainLightCluster(
        uv, surface.linearDepth);
    lighting.maximum = AccumulateMainLightAmbient(
        surface, cluster, lighting.maximum);
    AccumulateMainLightPoint(surface, cluster, lighting);
    AccumulateMainLightSpot(surface, cluster, lighting);
  }
  lighting.maximum = saturate(lighting.maximum);
  float3 localLighting = lighting.maximum + lighting.additive;
#if MAIN_LIGHT_COMPACT_HORIZON
  float viewDistance = sqrt(dot(surface.viewPosition, surface.viewPosition));
  float horizonFade = -cb_fHorizonLightStart + viewDistance;
  horizonFade = saturate(cb_fHorizonLightInvRange * horizonFade);
  horizonFade = 1.0 + -horizonFade;
  horizonFade = log2(horizonFade);
  horizonFade = cb_fHorizonLightFalloff * horizonFade;
  horizonFade = exp2(horizonFade);
  float normalDotHorizon = dot(
      surface.normal, cb_vHorizonLightDirection.xyz);
  float4 horizonColor = normalDotHorizon > 0.0
      ? cb_vHorizonLightColorBottom
      : cb_vHorizonLightColorTop;
  horizonColor = -cb_vHorizonLightColorMiddle + horizonColor;
  horizonColor = abs(normalDotHorizon).xxxx * horizonColor
      + cb_vHorizonLightColorMiddle;
  float unlit = dot(localLighting, float3(1.0, 1.0, 1.0));
  unlit = 1.0 + -unlit;
  unlit = unlit * unlit;
  horizonColor.w = horizonColor.w * surface.diffuseCompensation;
  horizonFade = horizonColor.w * horizonFade;
  horizonColor.xyz = horizonColor.xyz * horizonFade.xxx;
  horizonColor.xyz = horizonColor.xyz * surface.albedo.xyz;
  localLighting = horizonColor.xyz * unlit.xxx + localLighting;
#endif
  float3 difference = surface.albedo.xyz + -localLighting;
  return surface.albedo.www * difference + localLighting;
}
