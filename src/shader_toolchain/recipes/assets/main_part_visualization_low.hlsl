// Low-quality visualization response: depth stripes plus a normal-mapped rim.

float3 DecodeMainPartLowVisualizationNormal(float2 encodedNormal)
{
  float2 normalXY = encodedNormal * 1.99215686 - 1.0;
  float normalZ = sqrt(max(0.0, 1.0 - dot(normalXY, normalXY)));
  return float3(normalXY, normalZ);
}

float4 EvaluateMainPartLowVisualizationBehind(
    float3 viewPosition, float3 screenPosition, float sceneDepth)
{
  float stripe = sin(450.0 * (
      screenPosition.x * cb_fViewportAspect + screenPosition.y));
  stripe = abs(stripe) * abs(stripe);
  float stripeSquared = stripe * stripe;
  stripe *= stripeSquared;

  float distanceFade = abs(viewPosition.z)
      - (6.0 + cb_vNearFarViewCorner.x);
  distanceFade = saturate(
      cb_visualization.fBehindInvDepthDistance * distanceFade);

  float2 projectedDepth = float2(sceneDepth, screenPosition.z);
  projectedDepth += cb_xViewToProjection._m22;
  projectedDepth = cb_xViewToProjection._m23 / projectedDepth;
  float separation = projectedDepth.y - projectedDepth.x;
  separation -= cb_visualization.fBehindOffset;
  separation = saturate(
      cb_visualization.fInvBehindDistance * separation);

  float opacity = 0.899999976 * (1.0 - separation)
      * (1.0 - distanceFade) * stripe;
  return float4(cb_visualization.vBehindColor.xyz, opacity);
}

float4 EvaluateMainPartLowVisualizationVisible(
    float3 viewPosition, float3 normalView)
{
  float viewDistance = sqrt(dot(viewPosition, viewPosition));
  float fadeStart = cb_visualization.fFadeDistance
      + cb_vNearFarViewCorner.x;
  float distanceFade = saturate(viewDistance - fadeStart);
  float fadeRemaining = 1.0 - distanceFade;

  float3 directionToEye = -viewPosition;
  directionToEye *= rsqrt(dot(directionToEye, directionToEye));
  float rim = 1.0 - dot(directionToEye, normalView);
  float broadHighlight = 0.200000003 * fadeRemaining
      + max(0.00100000005, rim);
  broadHighlight *= broadHighlight;
  broadHighlight *= broadHighlight;
  broadHighlight *= broadHighlight;
  broadHighlight = min(1.0, broadHighlight);

  float saturation = max(0.0, rim * 0.300000012 + broadHighlight);
  saturation = min(cb_visualization.fMaxSaturation, saturation);
  float opacity = (cb_visualization.vColor.w + broadHighlight)
      * max(0.200000003, distanceFade);
  return float4(
      saturate(cb_visualization.vColor.xyz + saturation), opacity);
}

float4 EvaluateMainPartLowVisualization(
    float3 viewPosition, float3 normalView, float3 screenPosition)
{
  float sceneDepth = tDepth.Sample(PointClampClamp_s, screenPosition.xy).x;
  if (screenPosition.z + 4.99999987e-05 < sceneDepth)
    return EvaluateMainPartLowVisualizationBehind(
        viewPosition, screenPosition, sceneDepth);
  return EvaluateMainPartLowVisualizationVisible(viewPosition, normalView);
}
