float4 EvaluateMainPartVisualizationBehind(
    float3 viewPosition, float3 screenUv, float opaqueDepth)
{
  float stripe = sin(450.0 * (
      screenUv.x * cb_fViewportAspect + screenUv.y));
  stripe = abs(stripe) * abs(stripe);
  float stripeSquared = stripe * stripe;
  stripe *= stripeSquared;

  float depthFade = abs(viewPosition.z)
      - (6.0 + cb_vNearFarViewCorner.x);
  depthFade = saturate(
      cb_visualization.fBehindInvDepthDistance * depthFade);
  float projectedDepth = cb_xViewToProjection._m23
      / (cb_xViewToProjection._m22 + opaqueDepth);
  float separation = screenUv.z - projectedDepth
      - cb_visualization.fBehindOffset;
  separation = saturate(
      cb_visualization.fInvBehindDistance * separation);
  separation = (1.0 - separation) * (1.0 - depthFade) * stripe;
  return float4(
      cb_visualization.vBehindColor.xyz, 0.899999976 * separation);
}

float4 EvaluateMainPartVisualizationVisible(
    float3 viewPosition, float3 normalView, bool frontFace)
{
  float3 normal = frontFace ? normalView : -normalView;
  normal *= rsqrt(dot(normal, normal));

  float worldPositionZ = viewToWorld._m21 * viewPosition.y;
  worldPositionZ = viewToWorld._m20 * viewPosition.x + worldPositionZ;
  worldPositionZ = viewToWorld._m22 * viewPosition.z + worldPositionZ;
  worldPositionZ = viewToWorld._m23 + worldPositionZ;
  float worldNormalZ = viewToWorld._m21 * normal.y;
  worldNormalZ = viewToWorld._m20 * normal.x + worldNormalZ;
  worldNormalZ = viewToWorld._m22 * normal.z + worldNormalZ;

  float pulsePosition = cb_visualization.fPulseDir * worldPositionZ;
  pulsePosition = pulsePosition * 0.571428597 + 0.600000024 * cb_fTime;
  pulsePosition += abs(worldNormalZ);
  pulsePosition = frac(pulsePosition);
  float pulseEdge = 1.0 - min(1.0, 8.0 * pulsePosition);
  pulsePosition = pulseEdge * abs(worldNormalZ) + pulsePosition;
  float pulse = 1.0 - pulsePosition * cb_visualization.fPulse;
  float pulseHighlight = exp2(
      35.0 * log2(max(0.00100000005, pulse)));

  float viewDistance = sqrt(dot(viewPosition, viewPosition));
  float fadeStart = cb_visualization.fFadeDistance
      + cb_vNearFarViewCorner.x;
  float distanceFade = saturate(viewDistance - fadeStart);
  float inverseDistanceFade = 1.0 - distanceFade;

  float inverseViewLength = rsqrt(dot(-viewPosition, -viewPosition));
  float3 viewDirection = -viewPosition * inverseViewLength;
  float inverseFacing = 1.0 - dot(viewDirection, normal);
  float fresnelBase = max(0.00100000005, inverseFacing);
  float fresnel = inverseDistanceFade * 0.200000003 + fresnelBase;
  fresnel *= fresnel;
  fresnel *= fresnel;
  fresnel *= fresnel;
  fresnel = min(1.0, fresnel);

  float3 highlightDirection = viewDirection
      + cb_vDirectionalLightDirectionView.xyz;
  highlightDirection *= rsqrt(dot(highlightDirection, highlightDirection));
  float directional = max(0.00100000005,
      dot(highlightDirection, normal));
  directional = exp2(120.0 * log2(directional));

  float saturation = inverseFacing * 0.300000012 + fresnel;
  saturation += directional;
  saturation += pulseHighlight * cb_visualization.fPulse;
  saturation = min(
      cb_visualization.fMaxSaturation, max(0.0, saturation));
  float opacityFade = max(0.200000003, distanceFade) * pulse;

  float4 result;
  result.xyz = saturate(cb_visualization.vColor.xyz + saturation);
  result.w = (cb_visualization.vColor.w + fresnel + directional)
      * opacityFade;
  return result;
}

void EvaluateMainPartVisualizationDepth(
    float4 position, float3 viewPosition, float2 uv, float3 normalView,
    float4 vertexColor, float3 screenUv, uint frontFace,
    out float4 colorTarget)
{
  float opaqueDepth = tDepth.Sample(PointClampClamp_s, screenUv.xy).x;
  bool isBehind = 4.99999987e-05 + screenUv.z < opaqueDepth;
  colorTarget = isBehind
      ? EvaluateMainPartVisualizationBehind(
          viewPosition, screenUv, opaqueDepth)
      : EvaluateMainPartVisualizationVisible(
          viewPosition, normalView, frontFace != 0);
}
