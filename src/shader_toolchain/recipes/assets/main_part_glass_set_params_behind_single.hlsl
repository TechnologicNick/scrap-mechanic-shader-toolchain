#ifndef MAIN_PART_GLASS_SET_PARAMS_BEHIND_SINGLE_HLSL
#define MAIN_PART_GLASS_SET_PARAMS_BEHIND_SINGLE_HLSL

// Typed low-quality set-parameter glass behind pass.

struct MainPartSetParamsGlassMaterial
{
  float3 viewDirection;
  float3 normalView;
  float3 diffuseColor;
  float gloss;
  float specularScale;
  float glow;
};

struct MainPartSetParamsGlassLighting
{
  float3 color;
  float specular;
};

struct MainPartSetParamsBehindComposite
{
  float3 weightedColor;
  float2 accumulation;
};

struct MainPartSetParamsReflections
{
  float3 fallback;
  float3 single;
};

void RejectMainPartSetParamsBehindOpaqueDepth(float3 screenUv)
{
  float opaqueDepth = tDepth.SampleLevel(
      PointClampClamp_s, screenUv.xy, 0).x;
  if (screenUv.z < opaqueDepth)
    discard;
}

float2 EncodeMainPartSetParamsReflectionDirection(float3 direction)
{
  float inverseL1 = rcp(max(9.99999975e-05,
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

MainPartSetParamsGlassMaterial EvaluateMainPartSetParamsGlassMaterial(
    float3 viewPosition, float3 normalView, bool frontFace)
{
  MainPartSetParamsGlassMaterial result;
  result.viewDirection = -viewPosition
      * rsqrt(dot(-viewPosition, -viewPosition));
  result.normalView = frontFace ? normalView : -normalView;
  result.normalView *= rsqrt(dot(result.normalView, result.normalView));
  result.diffuseColor = cb_offset.vDiffuse.xyz;
  result.gloss = cb_offset.fGloss;
  result.specularScale = cb_offset.fSpecular;
  result.glow = cb_offset.fGlow;
  return result;
}

MainPartSetParamsGlassLighting EvaluateMainPartSetParamsDirectionalLighting(
    float3 viewPosition, MainPartSetParamsGlassMaterial material)
{
  MainPartSetParamsGlassLighting result;
  if (cb_fDirectionalLightIntensity != 0.0)
  {
    float viewDistance = sqrt(dot(viewPosition, viewPosition));
    float glossExponent = material.gloss * material.gloss;
    float specularStrength = material.specularScale * material.gloss;
    glossExponent = glossExponent * 750.0 + 35.0;
    float normalDotLight = dot(
        material.normalView, -cb_vDirectionalLightDirectionView.xyz);
    float halfLambert = normalDotLight * 0.5 + 0.5;
    float transmission = max(0.0, normalDotLight);
    transmission = transmission * cb_glass.fTransmissionRange
        + cb_glass.fTransmissionBase;
    transmission = min(1.0, transmission);

    float distanceShape = min(1.0, 0.00400000019 * viewDistance);
    distanceShape = 1.0 - distanceShape;
    distanceShape *= distanceShape;
    distanceShape = distanceShape * 0.200000018 + 0.400000006;
    float2 shapeRange = float2(1.0, 1.20000005) - distanceShape;
    float shapedLight = saturate(halfLambert - distanceShape);
    shapedLight /= shapeRange.x;
    shapedLight *= shapedLight;
    distanceShape = shapedLight * shapeRange.y + distanceShape;

    float3 mappedLight = tLightColorMap.SampleLevel(
        LinearWrapClamp_s,
        float2(cb_fTimeOfDay, saturate(halfLambert)), 0).xyz;
    mappedLight = (mappedLight - cb_vDirectionalShadowColor.xyz)
        * halfLambert + cb_vDirectionalShadowColor.xyz;
    distanceShape *= cb_fDirectionalLightMapMul;
    result.color = mappedLight * distanceShape
        * cb_fDirectionalLightIntensity;

    float3 halfDirection = material.viewDirection
        - cb_vDirectionalLightDirectionView.xyz;
    halfDirection *= rsqrt(dot(halfDirection, halfDirection));
    float specular = dot(halfDirection, material.normalView) * 0.5 + 0.5;
    specular = exp2(glossExponent * log2(abs(specular)));
    specular *= transmission;
    result.specular = saturate(specular * specularStrength);
  }
  else
  {
    result.color = 0.0;
    result.specular = 0.0;
  }
  return result;
}

MainPartSetParamsReflections EvaluateMainPartSetParamsSingleReflection(
    MainPartSetParamsGlassMaterial material)
{
  MainPartSetParamsReflections result;
  result.fallback = 0.0;
  if (cb_fDirectionalLightIntensity == 0.0)
  {
    float3 worldNormal = viewToWorld._m01_m11_m21 * material.normalView.y;
    worldNormal = viewToWorld._m00_m10_m20 * material.normalView.x
        + worldNormal;
    worldNormal = viewToWorld._m02_m12_m22 * material.normalView.z
        + worldNormal;
    result.fallback = taReflection.SampleLevel(
        LinearMirrorMirror_s,
        float3(EncodeMainPartSetParamsReflectionDirection(worldNormal), 0.0),
        5.0).xyz;
  }

  float normalDotView = dot(-material.viewDirection, material.normalView);
  float3 reflectionView = material.normalView * (-2.0 * normalDotView)
      - material.viewDirection;
  float3 reflectionWorld = viewToWorld._m01_m11_m21 * reflectionView.y;
  reflectionWorld = viewToWorld._m00_m10_m20 * reflectionView.x
      + reflectionWorld;
  reflectionWorld = viewToWorld._m02_m12_m22 * reflectionView.z
      + reflectionWorld;
  float roughness = max(0.00999999978, 1.0 - material.gloss);
  roughness = rsqrt(roughness);
  roughness = 1.0 / roughness;
  float lod = 5.0 * roughness;
  result.single = taReflection.SampleLevel(
      LinearMirrorMirror_s,
      float3(EncodeMainPartSetParamsReflectionDirection(reflectionWorld), 0.0),
      lod).xyz;
  result.single *= material.specularScale;
  return result;
}

MainPartSetParamsBehindComposite ComposeMainPartSetParamsBehind(
    float depth, bool frontFace, MainPartSetParamsGlassMaterial material,
    MainPartSetParamsGlassLighting lighting,
    MainPartSetParamsReflections reflections)
{
  MainPartSetParamsBehindComposite result;
  float3 environment = lighting.color + reflections.fallback;
  environment = material.glow * (1.0 - environment) + environment;

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

  float3 composedColor = material.gloss * reflections.single;
  composedColor = material.diffuseColor * environment + composedColor;
  composedColor += environment * reflectionEnergy;
  float3 channelDifferences = material.diffuseColor.xxy
      - material.diffuseColor.zyz;
  float oitWeight = depth + abs(channelDifferences.x)
      + abs(channelDifferences.y) + abs(channelDifferences.z);
  float weightedAlpha = oitWeight * transparency;
  result.weightedColor = composedColor * weightedAlpha;
  result.accumulation = float2(
      weightedAlpha * transparency, weightedAlpha);
  return result;
}

void EvaluateMainPartSetParamsBehindSingle(
    float4 position, float3 viewPosition, float2 uv,
    float3 normalView, float4 vertexColor, float3 screenUv,
    float4 fogColor, uint frontFace,
    out float3 colorTarget, out float2 accumulationTarget)
{
  RejectMainPartSetParamsBehindOpaqueDepth(screenUv);
  MainPartSetParamsGlassMaterial material =
      EvaluateMainPartSetParamsGlassMaterial(
          viewPosition, normalView, frontFace != 0);
  MainPartSetParamsGlassLighting lighting =
      EvaluateMainPartSetParamsDirectionalLighting(viewPosition, material);
  MainPartSetParamsReflections reflections =
      EvaluateMainPartSetParamsSingleReflection(material);
  MainPartSetParamsBehindComposite composite = ComposeMainPartSetParamsBehind(
      screenUv.z, frontFace != 0, material, lighting, reflections);
  colorTarget = composite.weightedColor;
  accumulationTarget = composite.accumulation;
}

#endif // MAIN_PART_GLASS_SET_PARAMS_BEHIND_SINGLE_HLSL
