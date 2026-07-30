// Basic textured laser behind-pass with animated volumetric fog.

struct MainPartBasicLaserBehindResult
{
  float3 color;
  float2 glowAndAlpha;
};

MainPartBasicLaserBehindResult EvaluateMainPartBasicLaserBehind(
    float3 viewPosition,
    float2 uv0,
    float4 vertexColor,
    float3 screenUv,
    float laserMask,
    float textureIntensity)
{
  MainPartBasicLaserBehindResult result;

  float3 worldPosition = viewToWorld._m01_m11_m21 * viewPosition.y;
  worldPosition = viewToWorld._m00_m10_m20 * viewPosition.x
      + worldPosition;
  worldPosition = viewToWorld._m02_m12_m22 * viewPosition.z
      + worldPosition;
  worldPosition = viewToWorld._m03_m13_m23 + worldPosition;

  float3 fogUv = cb_fTime * cb_laser.fFogScrollSpeed + worldPosition;
  fogUv *= cb_laser.fFogScaleRCP;
  float fogNoise = tLaserFog.SampleLevel(
      LinearWrapWrap_s, fogUv, 0).x;
  float fogLoop = frac(cb_fTime * cb_laser.fFogLoopSpeed + fogNoise) - 0.5;
  float fogShape = (1.0 - cb_laser.fFogMin)
      + dot(abs(fogLoop.xx), cb_laser.fFogMin);
  float intensity = saturate(
      textureIntensity - fogShape * cb_laser.fFogOpacity);

  float fade = cb_laser.fFadeRange + uv0.y - cb_laser.fFadeValue;
  fade = saturate(fade / cb_laser.fFadeRange);
  float4 laserColor = cb_laser.vBaseColor
      + intensity * (cb_laser.vHighlightColor - cb_laser.vBaseColor);
  float3 shadedColor = vertexColor.xyz * laserColor.xyz;
  float alpha = laserMask * laserColor.w * fade;

  float3 channelDifference = laserColor.xxy * vertexColor.xxy
      - shadedColor.zyz;
  float glowMetric = abs(channelDifference.x) + abs(channelDifference.y);
  glowMetric += abs(channelDifference.z);
  glowMetric = (screenUv.z + glowMetric) * alpha;

  result.color = shadedColor * glowMetric;
  result.glowAndAlpha = float2(alpha * glowMetric, glowMetric);
  return result;
}
