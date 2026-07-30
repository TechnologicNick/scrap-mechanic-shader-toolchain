// Textured laser behind-pass with depth rejection, highlights, fog, and glow.

struct MainPartLaserBehindResult
{
  float3 color;
  float2 glowAndAlpha;
};

MainPartLaserBehindResult EvaluateMainPartLaserBehind(
    float3 viewPosition,
    float2 uv0,
    float3 normalViewInput,
    float4 vertexColor,
    float3 screenUv,
    uint frontFace,
    float laserMask,
    float textureIntensity,
    float sampledDepth)
{
  MainPartLaserBehindResult result;

  float intensity = textureIntensity;
  float3 normalView = frontFace != 0 ? normalViewInput : -normalViewInput;
  normalView *= rsqrt(dot(normalView, normalView));
  float3 directionToEye = -viewPosition;
  directionToEye *= rsqrt(dot(directionToEye, directionToEye));
  float fresnel = max(0.0, 1.0 - abs(dot(normalView, directionToEye)));
  fresnel = cb_laser.fFresnelIntensity * fresnel;
  fresnel = exp2(cb_laser.fFresnelExponent * log2(abs(fresnel)));
  intensity += fresnel;

  // Convert sampled and fragment device depths through the projection terms
  // before evaluating the thin intersection band.
  float2 projectedDepth = cb_xViewToProjection._m22_m22
      + float2(sampledDepth, screenUv.z);
  projectedDepth = cb_xViewToProjection._m23_m23 / projectedDepth;
  float intersection = projectedDepth.x - projectedDepth.y;
  intersection = max(
      0.0, 1.0 - abs(intersection / cb_laser.fIntersectHeight));
  intensity = mad(intersection, cb_laser.fIntersectIntensity, intensity);

  // The packed swizzle produces [worldZ, worldX, worldY, worldZ]. Preserve it
  // because scan lines consume x while fog consumes yzw.
  float4 worldCoordinates = viewToWorld._m21_m01_m11_m21
      * viewPosition.y;
  worldCoordinates = viewToWorld._m20_m00_m10_m20
      * viewPosition.x + worldCoordinates;
  worldCoordinates = viewToWorld._m22_m02_m12_m22
      * viewPosition.z + worldCoordinates;
  worldCoordinates = viewToWorld._m23_m03_m13_m23 + worldCoordinates;

  float2 scanCoordinate = cb_fTime * cb_laser.fScanLineSpeed1
      + worldCoordinates.xx;
  float scanLine1 = max(
      0.0, sin(cb_laser.fScanLineFrequency1 * scanCoordinate.x));
  float scanLine2 = frac(
      cb_laser.fScanLineFrequency2 * scanCoordinate.y);
  scanLine2 *= cb_laser.fScanLineIntensity2;
  intensity += mad(
      scanLine1, cb_laser.fScanLineIntensity1, scanLine2);

  float3 fogUv = cb_fTime * cb_laser.fFogScrollSpeed
      + worldCoordinates.yzw;
  fogUv *= cb_laser.fFogScaleRCP;
  float fogNoise = tLaserFog.SampleLevel(
      LinearWrapWrap_s, fogUv, 0).x;
  float fogLoop = frac(
      cb_fTime * cb_laser.fFogLoopSpeed + fogNoise) - 0.5;
  float fogShape = (1.0 - cb_laser.fFogMin)
      + dot(abs(fogLoop.xx), cb_laser.fFogMin);
  intensity = saturate(intensity - fogShape * cb_laser.fFogOpacity);

  float fade = cb_laser.fFadeRange + uv0.y - cb_laser.fFadeValue;
  fade = saturate(fade / cb_laser.fFadeRange);
  float4 laserColor = cb_laser.vBaseColor
      + intensity * (cb_laser.vHighlightColor - cb_laser.vBaseColor);
  float3 shadedColor = vertexColor.xyz * laserColor.xyz;
  float alpha = laserMask * laserColor.w * fade;

  // This is not luminance: the original path measures three cross-channel
  // differences, adds device depth, and uses the result as a glow multiplier.
  float3 channelDifference = laserColor.xxy * vertexColor.xxy
      - shadedColor.zyz;
  float glowMetric = abs(channelDifference.x)
      + abs(channelDifference.y) + abs(channelDifference.z);
  glowMetric = (screenUv.z + glowMetric) * alpha;

  result.color = shadedColor * glowMetric;
  result.glowAndAlpha = float2(alpha * glowMetric, glowMetric);
  return result;
}
