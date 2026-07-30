#ifndef MAIN_PART_GLASS_CUSTOM_TILING_BEHIND_LOW_HLSL
#define MAIN_PART_GLASS_CUSTOM_TILING_BEHIND_LOW_HLSL

// Typed custom-tiled glass behind pass.  The detail-normal orientation is
// shared by quality permutations; this file supplies the low directional
// lighting and weighted behind-pass composition policy.

struct MainPartCustomTilingGlassMaterial
{
  float3 viewDirection;
  float3 normalView;
  float3 diffuseColor;
  float3 occludedDiffuseColor;
  float gloss;
  float coverage;
  float specularScale;
};

struct MainPartCustomTilingGlassLighting
{
  float3 color;
  float specular;
};

struct MainPartCustomTilingBehindComposite
{
  float3 weightedColor;
  float2 accumulation;
};

void RejectMainPartCustomTilingBehindOpaqueDepth(float3 screenUv)
{
  float opaqueDepth = tDepth.SampleLevel(
      PointClampClamp_s, screenUv.xy, 0).x;
  if (screenUv.z < opaqueDepth)
    discard;
}

float2 OrientMainPartCustomTilingDetailNormal(
    float2 detailNormal, float2 detailUv,
    float3 viewPosition, float3 normalView)
{
  // Recover the screen-space orientation of the secondary UV set.  The
  // polynomial atan approximation and its comparisons intentionally retain
  // the source order because the result is sensitive near degenerate UVs.
  float inverseNormalLength = rsqrt(dot(normalView, normalView));
  float4 normalizedNormal = normalView.yzzx * inverseNormalLength;
  float4 viewShuffle = -viewPosition.yzzx;
  float4 viewDx = ddx_coarse(viewShuffle.zwxz);
  float4 viewDy = ddy_coarse(viewShuffle.xyzw);
  float uvDx = ddx_coarse(detailUv.x);
  float uvDy = ddy_coarse(detailUv.x);

  viewDy.zw *= normalizedNormal.xz;
  viewDy.xy = viewDy.yx * normalizedNormal.wz - viewDy.wz;
  viewDx.zw *= normalizedNormal.zw;
  viewDx.xy = viewDx.yx * normalizedNormal.yx - viewDx.wz;
  float2 orientation = viewDx.xy * uvDy;
  orientation = viewDy.xy * uvDx + orientation;
  bool hasOrientation = dot(orientation.yx, 1.0) != 0.0;

  float minimumAxis = min(abs(orientation.x), abs(orientation.y));
  float maximumAxis = max(abs(orientation.x), abs(orientation.y));
  float ratio = minimumAxis / maximumAxis;
  float ratioSquared = ratio * ratio;
  float polynomial = ratioSquared * 0.0208350997 - 0.0851330012;
  polynomial = ratioSquared * polynomial + 0.180141002;
  polynomial = ratioSquared * polynomial - 0.330299497;
  polynomial = ratioSquared * polynomial + 0.999866009;
  float angle = ratio * polynomial;
  float complement = angle * -2.0 + 1.57079637;
  angle += abs(orientation.y) < abs(orientation.x) ? complement : 0.0;
  angle += orientation.y < -orientation.y ? -3.141593 : 0.0;
  bool negativeQuadrant = min(orientation.x, orientation.y)
      < -min(orientation.x, orientation.y);
  bool positiveAxis = max(orientation.x, orientation.y)
      >= -max(orientation.x, orientation.y);
  angle = positiveAxis && negativeQuadrant ? -angle : angle;

  float sine;
  float cosine;
  sincos(angle, sine, cosine);
  float2 rotated;
  rotated.x = dot(float2(cosine, -sine), detailNormal);
  rotated.y = dot(float2(sine, cosine), detailNormal);
  return hasOrientation ? rotated : detailNormal;
}

MainPartCustomTilingGlassMaterial EvaluateMainPartCustomTilingGlassMaterial(
    float3 viewPosition, float occlusion, float2 baseUv, float2 detailUv,
    float3 normalView, float3 tangentView, float3 bitangentView,
    float4 vertexColor, bool frontFace)
{
  MainPartCustomTilingGlassMaterial result;
  float inverseViewLength = rsqrt(dot(-viewPosition, -viewPosition));
  result.viewDirection = -viewPosition * inverseViewLength;

  float4 routedUv = vTextureTiling.yyzz
      * float4(detailUv, baseUv);
  float3 asg = tAsg.SampleBias(
      LinearWrapWrap_s, routedUv.xy, cb_fMipBias).yzw;
  result.gloss = asg.x;
  result.coverage = vertexColor.w * asg.y;
  result.specularScale = asg.z;

  float2 baseNormal = tNor.SampleBias(
      LinearWrapWrap_s, routedUv.zw, cb_fMipBias).xy;
  baseNormal = baseNormal * 1.99215686 - 1.0;
  float baseNormalZ = sqrt(max(0.0, 1.0 - dot(baseNormal, baseNormal)));

  float4 detailCoordinates = vTextureTiling.wwxx
      * detailUv.xyxy;
  float2 detailNormal = tNorD.SampleBias(
      LinearWrapWrap_s, detailCoordinates.xy, cb_fMipBias).xy;
  detailNormal = detailNormal * 1.99215686 - 1.0;
  detailNormal = OrientMainPartCustomTilingDetailNormal(
      detailNormal, detailUv, viewPosition, normalView);
  baseNormal += detailNormal;

  float3 mappedNormal = bitangentView * baseNormal.y;
  mappedNormal = tangentView * baseNormal.x + mappedNormal;
  mappedNormal = normalView * baseNormalZ + mappedNormal;
  mappedNormal *= rsqrt(dot(mappedNormal, mappedNormal));
  result.normalView = frontFace ? mappedNormal : -mappedNormal;
  result.normalView *= rsqrt(dot(result.normalView, result.normalView));

  float4 diffuse = tDif.SampleBias(
      LinearWrapWrap_s, detailCoordinates.zw, cb_fMipBias);
  result.diffuseColor = (diffuse.xyz - vertexColor.xyz) * diffuse.w
      + vertexColor.xyz;
  result.occludedDiffuseColor = occlusion * result.diffuseColor;
  return result;
}

MainPartCustomTilingGlassLighting
EvaluateMainPartCustomTilingLowDirectionalLighting(
    float3 viewPosition, MainPartCustomTilingGlassMaterial material)
{
  MainPartCustomTilingGlassLighting result;
  if (cb_fDirectionalLightIntensity != 0.0)
  {
    float viewDistance = sqrt(dot(viewPosition, viewPosition));
    float glossExponent = material.gloss * material.gloss;
    float specularStrength = material.specularScale * material.gloss;
    glossExponent = glossExponent * 750.0 + 35.0;
    float normalDotLight = dot(
        material.normalView, -cb_vDirectionalLightDirectionView.xyz);
    float halfLambert = normalDotLight * 0.5 + 0.5;
    float absoluteNormalDotLight = min(1.0, abs(normalDotLight));

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
    specular = log2(abs(specular));
    specular = glossExponent * specular;
    specular = exp2(specular);
    specular *= absoluteNormalDotLight;
    result.specular = saturate(specular * specularStrength);
  }
  else
  {
    result.color = 0.0;
    result.specular = 0.0;
  }
  return result;
}

MainPartCustomTilingBehindComposite ComposeMainPartCustomTilingBehind(
    float occlusion, float depth, bool frontFace,
    MainPartCustomTilingGlassMaterial material,
    MainPartCustomTilingGlassLighting lighting)
{
  MainPartCustomTilingBehindComposite result;
  float3 lightResponse = 1.0 - lighting.color;
  lightResponse = material.coverage * lightResponse + lighting.color;

  float normalFacing = dot(material.viewDirection, material.normalView);
  float edgeColor = 0.119999997 * material.gloss;
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

  float3 shadedColor = material.occludedDiffuseColor * lightResponse
      + edgeColor;
  float inverseLuminance = 1.0 - dot(
      shadedColor, float3(0.298999995, 0.587000012, 0.114));
  float weightScale = inverseLuminance * 0.5 + 0.100000001;
  transparency *= weightScale;
  float3 composedColor = lightResponse * reflectionEnergy + shadedColor;

  float3 channelDifferences =
      material.diffuseColor.xxy * occlusion
      - material.occludedDiffuseColor.zyz;
  float oitWeight = depth + abs(channelDifferences.x)
      + abs(channelDifferences.y) + abs(channelDifferences.z);
  float weightedAlpha = oitWeight * transparency;
  result.weightedColor = composedColor * weightedAlpha;
  result.accumulation = float2(
      transparency * weightedAlpha, weightedAlpha);
  return result;
}

void EvaluateMainPartCustomTilingBehindLow(
    float4 position, float3 viewPosition, float occlusion,
    float2 baseUv, float2 detailUv, float3 normalView,
    float3 tangentView, float3 bitangentView, float4 vertexColor,
    float3 screenUv, float4 fogColor, uint frontFace,
    out float3 colorTarget, out float2 accumulationTarget)
{
  RejectMainPartCustomTilingBehindOpaqueDepth(screenUv);
  MainPartCustomTilingGlassMaterial material =
      EvaluateMainPartCustomTilingGlassMaterial(
          viewPosition, occlusion, baseUv, detailUv,
          normalView, tangentView, bitangentView,
          vertexColor, frontFace != 0);
  MainPartCustomTilingGlassLighting lighting =
      EvaluateMainPartCustomTilingLowDirectionalLighting(
          viewPosition, material);
  MainPartCustomTilingBehindComposite composite =
      ComposeMainPartCustomTilingBehind(
          occlusion, screenUv.z, frontFace != 0, material, lighting);
  colorTarget = composite.weightedColor;
  accumulationTarget = composite.accumulation;
}

#endif // MAIN_PART_GLASS_CUSTOM_TILING_BEHIND_LOW_HLSL
