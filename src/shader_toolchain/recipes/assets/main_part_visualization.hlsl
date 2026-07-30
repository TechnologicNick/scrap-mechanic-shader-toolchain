#ifndef MAIN_PART_VISUALIZATION_HLSL
#define MAIN_PART_VISUALIZATION_HLSL

// Shared material-independent core for full-quality visualization passes.
// Material permutations decode opacity and a view-space normal before entering
// this evaluator; dissolve, glass, texture-array, and instanced-color frontends
// can therefore reuse the depth/pulse response independently.

float3 DecodeMainPartVisualizationNormal(float2 encodedNormal)
{
  float2 normalXY = encodedNormal * 1.99215686 - 1.0;
  float normalZ = sqrt(max(0.0, 1.0 - dot(normalXY, normalXY)));
  return float3(normalXY, normalZ);
}

float4 EvaluateMainPartVisualizationBehind(
    float3 viewPosition,
    float3 screenPosition,
    float sceneDepth)
{
  float stripe = sin(450.0 * (
      screenPosition.x * cb_fViewportAspect + screenPosition.y));
  stripe = abs(stripe) * abs(stripe);
  float stripeSquared = stripe * stripe;
  stripe *= stripeSquared;

  float distanceFade = abs(viewPosition.z) - (
      6.0 + cb_vNearFarViewCorner.x);
  distanceFade = saturate(
      cb_visualization.fBehindInvDepthDistance * distanceFade);

  float2 projectedDepth = float2(sceneDepth, screenPosition.z);
  projectedDepth += cb_xViewToProjection._m22;
  projectedDepth = cb_xViewToProjection._m23 / projectedDepth;
  float separation = projectedDepth.y - projectedDepth.x;
  separation -= cb_visualization.fBehindOffset;
  separation = saturate(
      cb_visualization.fInvBehindDistance * separation);

  float opacity = 0.9 * (1.0 - separation) *
      (1.0 - distanceFade) * stripe;
  return float4(cb_visualization.vBehindColor.xyz, opacity);
}

float4 EvaluateMainPartVisualizationVisible(
    float3 viewPosition,
    float3 normalView)
{
  float worldPositionZ = dot(viewToWorld._m20_m21_m22, viewPosition);
  worldPositionZ += viewToWorld._m23;
  float worldNormalZ = dot(viewToWorld._m20_m21_m22, normalView);

  float pulseCoordinate = cb_visualization.fPulseDir * worldPositionZ;
  pulseCoordinate = pulseCoordinate * 0.571428597 + 0.600000024 * cb_fTime;
  pulseCoordinate += abs(worldNormalZ);
  pulseCoordinate = frac(pulseCoordinate);
  float pulseLeadingEdge = min(1.0, 8.0 * pulseCoordinate);
  pulseLeadingEdge = 1.0 - pulseLeadingEdge;
  pulseCoordinate = pulseLeadingEdge * abs(worldNormalZ) + pulseCoordinate;
  pulseCoordinate = 1.0 - pulseCoordinate * cb_visualization.fPulse;

  float pulseHighlight = exp2(
      35.0 * log2(max(0.00100000005, pulseCoordinate)));

  float viewDistance = sqrt(dot(viewPosition, viewPosition));
  float fadeStart = cb_visualization.fFadeDistance + cb_vNearFarViewCorner.x;
  float distanceFade = saturate(viewDistance - fadeStart);
  float fadeRemaining = 1.0 - distanceFade;

  float3 directionToEye = normalize(-viewPosition);
  float rim = 1.0 - dot(directionToEye, normalView);
  float stableRim = max(0.00100000005, rim);
  float broadHighlight = 0.200000003 * fadeRemaining + stableRim;
  broadHighlight *= broadHighlight;
  broadHighlight *= broadHighlight;
  broadHighlight *= broadHighlight;
  broadHighlight = min(1.0, broadHighlight);

  float3 halfVector = normalize(
      directionToEye + cb_vDirectionalLightDirectionView);
  float sharpHighlight = dot(halfVector, normalView);
  sharpHighlight = exp2(
      120.0 * log2(max(0.00100000005, sharpHighlight)));

  float saturation = rim * 0.300000012 + broadHighlight;
  saturation += sharpHighlight;
  saturation += pulseHighlight * cb_visualization.fPulse;
  saturation = min(
      cb_visualization.fMaxSaturation, max(0.0, saturation));

  float distanceOpacity = max(0.200000003, distanceFade) * pulseCoordinate;
  float3 color = saturate(cb_visualization.vColor.xyz + saturation);
  float opacity = (
      cb_visualization.vColor.w + broadHighlight + sharpHighlight) *
      distanceOpacity;
  return float4(color, opacity);
}

float4 EvaluateMainPartVisualization(
    float3 viewPosition,
    float3 normalView,
    float3 screenPosition)
{
  float sceneDepth = tDepth.Sample(PointClampClamp_s, screenPosition.xy).x;
  if (screenPosition.z + 4.99999987e-05 < sceneDepth)
    return EvaluateMainPartVisualizationBehind(
        viewPosition, screenPosition, sceneDepth);
  return EvaluateMainPartVisualizationVisible(viewPosition, normalView);
}

#endif // MAIN_PART_VISUALIZATION_HLSL
