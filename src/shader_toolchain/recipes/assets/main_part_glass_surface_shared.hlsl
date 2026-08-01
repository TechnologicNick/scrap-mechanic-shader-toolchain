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

#ifdef MAIN_PART_GLASS_SURFACE_LIGHT_CAP
#include "main_part_light_cap.hlsl"
#endif

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

#ifdef MAIN_PART_GLASS_SURFACE_LIGHT_CAP
MainPartDissolveGlassMaterial EvaluateMainPartLightCapGlassMaterial(
    float3 viewPosition,
    float2 uv,
    float3 normalView,
    float3 tangentView,
    float3 bitangentView,
    float4 vertexColor,
    bool frontFace)
{
  MainPartDissolveGlassMaterial result;
  float4 asg = tAsg.SampleBias(LinearWrapWrap_s, uv, cb_fMipBias);
  if (asg.x < 0.5)
    discard;
  result.normalView = DecodeMainPartTwoSidedNormal(
      uv, normalView, tangentView, bitangentView, frontFace);
  float inverseViewLength = rsqrt(dot(-viewPosition, -viewPosition));
  result.viewDirection = -viewPosition * inverseViewLength;

  float4 diffuse = tDif.SampleBias(LinearWrapWrap_s, uv, cb_fMipBias);
  diffuse.xyz = (diffuse.xyz - vertexColor.xyz) * diffuse.w
      + vertexColor.xyz;
  float2 lightCapUv = ComputeMainPartLightCapUv(
      viewPosition, result.viewDirection, result.normalView);
  float4 lightCap = tLightCap.Sample(LinearClampClamp_s, lightCapUv);
  float4 surface = (lightCap - diffuse) * lightCap.w + diffuse;
  result.diffuseColor = surface.xyz;
  result.coverage = vertexColor.w * asg.z;
  result.inverseViewLength = inverseViewLength;
  result.viewDistance = sqrt(dot(viewPosition, viewPosition));
  result.gloss = asg.y;
  result.reflectionScale = asg.w;
  result.glossExponent = asg.y * asg.y * 750.0 + 35.0;
  result.specularScale = asg.w * asg.y;
  return result;
}
#endif

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

#ifdef MAIN_PART_GLASS_SURFACE_STANDARD_LIGHTING
MainPartGlassLighting EvaluateMainPartStandardGlassDirectionalLighting(
    float3 viewPosition,
    MainPartDissolveGlassMaterial material)
{
  MainPartGlassLighting result;
  result.reflectedColor = 0.0;
  result.transmission = 0.0;
  if (cb_fDirectionalLightIntensity != 0.0)
  {
    float normalDotLight = dot(
        material.normalView, -cb_vDirectionalLightDirectionView.xyz);
    float halfLambert = normalDotLight * 0.5 + 0.5;
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
    float3 halfDirection = material.viewDirection
        - cb_vDirectionalLightDirectionView.xyz;
    halfDirection *= rsqrt(dot(halfDirection, halfDirection));
    float specular = dot(halfDirection, material.normalView) * 0.5 + 0.5;
    specular = exp2(log2(abs(specular)) * material.glossExponent);
    specular *= normalDotLight;
    result.specular = saturate(specular * material.specularScale);
  }
  else
  {
    result.directColor = 0.0;
    result.specular = 0.0;
  }
  return result;
}
#endif

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

#ifdef MAIN_PART_GLASS_SURFACE_UNRESPONSIVE
MainPartGlassSurfaceComposite ComposeMainPartUnresponsiveGlassSurface(
    float3 screenUv, float4 fogColor, bool frontFace,
    MainPartDissolveGlassMaterial material, MainPartGlassLighting lighting)
{
  MainPartGlassSurfaceComposite result;
  lighting.directColor = material.coverage * (1.0 - lighting.directColor)
      + lighting.directColor;
  float auxiliaryCoverage = min(0.5, 0.5 * material.coverage);
  float normalFacing = dot(material.viewDirection, material.normalView);
  float minimumFresnel = material.gloss * 0.5 + 0.00999999978;
  float grazing = 1.0 - normalFacing;
  float fresnel = grazing * grazing;
  fresnel *= fresnel;
  fresnel *= grazing;
  fresnel = (1.0 - minimumFresnel) * fresnel + minimumFresnel;
  float faceTransparency = frontFace
      ? cb_glass.fTransparencyFront : cb_glass.fTransparencyBack;
  float transparency = saturate(
      faceTransparency + lighting.specular + fresnel);
  float reflectionEnergy = lighting.specular + fresnel;
  float4 frame = tFrame.SampleLevel(
      LinearMirrorMirror_s, ClampMainPartFrameUv(screenUv.xy), 0);
  float3 glassColor = lighting.directColor * reflectionEnergy;
  glassColor = material.diffuseColor * lighting.directColor + glassColor;
  glassColor += lighting.reflectedColor;
  glassColor = (glassColor - frame.xyz) * transparency + frame.xyz;
  float fogStrength = 0.349999994 * auxiliaryCoverage;
  fogStrength *= 1.0 - min(1.0, 0.00999999978 * material.viewDistance);
  float largestChannel = max(abs(glassColor.x), abs(glassColor.y));
  largestChannel = max(largestChannel, abs(glassColor.z));
  fogStrength = (1.0 - fogStrength * largestChannel) * fogColor.w;
  result.color.xyz = (fogColor.xyz - glassColor) * fogStrength + glassColor;
  result.color.w = max(frame.w, transparency);
  result.auxiliary = float4(
      auxiliaryCoverage, 0.0, 0.0, result.color.w);
  return result;
}
#endif
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
#include "main_part_glass_clustered_lighting.hlsl"

void EvaluateMainPartGlassSurfaceMedium(
    float4 position, float3 viewPosition, float2 uv, float3 normalView,
    float3 tangentView, float3 bitangentView, float4 vertexColor,
    float3 screenUv, float4 fogColor, float cutoffOffset, uint frontFace,
    out float4 colorTarget, out float4 auxiliaryTarget)
{
  MainPartDissolveGlassMaterial material;
#ifdef MAIN_PART_GLASS_SURFACE_HAS_DISSOLVE
  material = EvaluateMainPartDissolveGlassMaterial(
      viewPosition, uv, normalView, tangentView, bitangentView,
      vertexColor, cutoffOffset, frontFace != 0);
#else
#ifdef MAIN_PART_GLASS_SURFACE_GEOMETRIC_NORMAL_ONLY
  material = EvaluateMainPartGlassMaterialGeometricNormal(
      viewPosition, uv, normalView, vertexColor, frontFace != 0);
#else
#ifdef MAIN_PART_GLASS_SURFACE_LIGHT_CAP
  material = EvaluateMainPartLightCapGlassMaterial(
      viewPosition, uv, normalView, tangentView, bitangentView,
      vertexColor, frontFace != 0);
#else
#ifdef MAIN_PART_GLASS_SURFACE_NO_CUTOUT
  material = EvaluateMainPartGlassMaterialNoCutout(
      viewPosition, uv, normalView, tangentView, bitangentView,
      vertexColor, frontFace != 0);
#else
  material = EvaluateMainPartGlassMaterial(
      viewPosition, uv, normalView, tangentView, bitangentView,
      vertexColor, frontFace != 0);
#endif
#endif
#endif
#endif

  MainPartGlassLighting lighting =
#ifdef MAIN_PART_GLASS_SURFACE_STANDARD_LIGHTING
      EvaluateMainPartStandardGlassDirectionalLighting(viewPosition, material);
#else
      EvaluateMainPartGlassDirectionalLighting(viewPosition, material);
#endif
  if (-viewPosition.z < cb_cluster.fClusterMaxFarTotal)
  {
    MainPartGlassClusterAddress cluster =
        ResolveMainPartGlassCluster(viewPosition, screenUv.xy);
    MainPartGlassLocalLighting local = EvaluateMainPartGlassLocalLights(
        cluster, viewPosition, material, lighting);
    lighting.directColor = local.maximumColor + local.additiveColor;
    lighting.specular = local.specular;
    lighting.transmission = local.transmission;
#ifdef MAIN_PART_GLASS_SURFACE_ENABLE_MULTI_PROBES
    lighting.reflectedColor =
        EvaluateMainPartGlassReflectionProbes(cluster, material)
        * material.reflectionScale;
#endif
  }

#ifndef MAIN_PART_GLASS_SURFACE_ENABLE_MULTI_PROBES
#ifdef MAIN_PART_GLASS_SURFACE_ENABLE_SINGLE_PROBE
  lighting.reflectedColor = EvaluateMainPartSingleReflection(material);
#else
  lighting.reflectedColor = float3(0.0, 0.0, 0.0);
#endif
#endif
#ifdef MAIN_PART_GLASS_SURFACE_OFF_AMBIENT
  lighting.reflectedColor = material.gloss * 0.119999997;
#endif

  MainPartGlassSurfaceComposite composite =
#ifdef MAIN_PART_GLASS_SURFACE_UNRESPONSIVE
      ComposeMainPartUnresponsiveGlassSurface(
          screenUv, fogColor, frontFace != 0, material, lighting);
#else
      ComposeMainPartDissolveGlassSurface(
          screenUv, fogColor, frontFace != 0, material, lighting);
#endif
  colorTarget = composite.color;
  auxiliaryTarget = composite.auxiliary;
}
#endif

#endif // MAIN_PART_GLASS_SURFACE_SHARED_INCLUDED
