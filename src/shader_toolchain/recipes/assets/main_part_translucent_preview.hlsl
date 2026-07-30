// Shared semantic model for flow-mapped translucent part previews.

struct MainPartFlowMaterial
{
  float4 diffuse;
  float3 asg;
};

float3 NormalizeMainPartPreviewDirection(float3 direction)
{
  return direction * rsqrt(dot(direction, direction));
}

float MainPartViewDepth(float deviceDepth)
{
  return cb_xViewToProjection._m23 / (cb_xViewToProjection._m22 + deviceDepth);
}

float ComputeMainPartTranslucentThickness(
    float3 viewPosition,
    float3 normalView,
    float3 viewDirection,
    float3 screenPosition)
{
  float3 refractionDirection = normalize(
      viewDirection - 2.0 * dot(viewDirection, normalView) * normalView);
  float2 refractedUv = screenPosition.xy
      + translucent.fRefraction * refractionDirection.xy * screenPosition.z
      * (1.0 - cb_xViewToProjection._m33);
  float sampledDepth = tDepth.Sample(LinearClampClamp_s, refractedUv).x;

  float orthographicDistance = cb_vInverseCameraRange.y
      * (screenPosition.z - sampledDepth);
  float perspectiveDistance = MainPartViewDepth(sampledDepth)
      - MainPartViewDepth(screenPosition.z);
  float thicknessDistance = (1.0 - cb_xViewToProjection._m33) != 0.0
      ? perspectiveDistance : orthographicDistance;
  thicknessDistance += translucent.fPush * (normalView.z - 1.0);
  return saturate(translucent.fThicknessFactor * thicknessDistance);
}

MainPartFlowMaterial SampleMainPartFlowMaterial(float2 uv)
{
  float2 flow = tFlowMap.Sample(LinearWrapWrap_s, uv).xy * 2.0 - 1.0;
  float phaseA = frac(cb_flow_map.fFlowSpeed * cb_fTime);
  float phaseB = frac(cb_flow_map.fFlowSpeed * cb_fTime + 0.5);
  float blend = 1.0 - abs(1.0 - 2.0 * phaseB);
  float2 uvA = uv - flow * phaseA;
  float2 uvB = uv - flow * phaseB;

  MainPartFlowMaterial material;
  float4 diffuseA = tDif.SampleBias(LinearWrapWrap_s, uvA, cb_fMipBias);
  float4 diffuseB = tDif.SampleBias(LinearWrapWrap_s, uvB, cb_fMipBias);
  float3 asgA = tAsg.SampleBias(
      LinearWrapWrap_s, vTextureTiling.yy * uvA, cb_fMipBias).yzw;
  float3 asgB = tAsg.SampleBias(
      LinearWrapWrap_s, vTextureTiling.yy * uvB, cb_fMipBias).yzw;
  material.diffuse = lerp(diffuseA, diffuseB, blend);
  material.asg = lerp(asgA, asgB, blend);
  return material;
}

float2 EncodeMainPartReflectionDirection(float3 direction)
{
  direction /= max(0.0001, abs(direction.x) + abs(direction.y) + abs(direction.z));
  float2 encoded = direction.xy;
  if (direction.z <= 0.0)
  {
    float2 folded = (1.0 - abs(encoded.yx));
    encoded = encoded < 0.0 ? -folded : folded;
  }
  encoded += float2(-2.0, 2.0);
  if (max(abs(encoded.x), abs(encoded.y)) >= 1.0)
    encoded = -encoded;
  return encoded * 0.5 + 0.5;
}

float3 SampleMainPartPreviewReflection(
    float3 viewDirection,
    float3 normalView,
    float viewFacing,
    float reflectionStrength)
{
  float3 incidentView = -viewDirection;
  float3 reflectedView = incidentView
      - 2.0 * dot(incidentView, normalView) * normalView;
  float3 reflectedWorld =
      viewToWorld._m00_m10_m20 * reflectedView.x
      + viewToWorld._m01_m11_m21 * reflectedView.y
      + viewToWorld._m02_m12_m22 * reflectedView.z;
  float2 reflectionUv = EncodeMainPartReflectionDirection(reflectedWorld);
  float mip = 5.0 * sqrt(max(0.01, 1.0 - viewFacing));
  return taReflection.SampleLevel(
      LinearMirrorMirror_s, float3(reflectionUv, 0.0), mip).xyz
      * reflectionStrength;
}

float3 EvaluateMainPartPreviewLight(float3 normalView)
{
  float3 lightView =
      worldToView._m00_m10_m20 * -0.22941573
      + worldToView._m01_m11_m21 * -0.688247204
      + worldToView._m02_m12_m22 * 0.688247204;
  lightView = NormalizeMainPartPreviewDirection(lightView);
  float normalDotLight = dot(normalView, lightView);
  float wrappedLight = saturate(normalDotLight * 0.5 + 0.5);
  float lightCurve = 2.49005985
      * saturate(normalDotLight * 0.5 - 0.0984032154);
  lightCurve = (lightCurve * lightCurve * 0.601596773 + 0.598403215)
      * cb_fDirectionalLightMapMul;
  float3 mappedLight = tLightColorMap.SampleLevel(
      LinearWrapClamp_s, float2(cb_fTimeOfDay, wrappedLight), 0).xyz;
  return lerp(cb_vDirectionalShadowColor, mappedLight, wrappedLight) * lightCurve;
}

float4 EvaluateMainPartTranslucentPreview(
    float3 viewPosition,
    float2 uv,
    float3 normal,
    float4 vertexColor,
    float3 screenPosition)
{
  float3 viewDirection = NormalizeMainPartPreviewDirection(-viewPosition);
  float3 normalView = NormalizeMainPartPreviewDirection(normal);
  float viewFacing = abs(dot(viewDirection, normalView));
  float thickness = ComputeMainPartTranslucentThickness(
      viewPosition, normalView, viewDirection, screenPosition);
  float4 transmission = tTranslucentMap.Sample(
      LinearClampClamp_s, float2(viewFacing, 1.0 - thickness));
  MainPartFlowMaterial material = SampleMainPartFlowMaterial(uv);
  float4 surface = material.diffuse + transmission;
  float3 baseColor = lerp(vertexColor.rgb, surface.rgb, surface.a);
  float3 reflection = SampleMainPartPreviewReflection(
      viewDirection, normalView, viewFacing, material.asg.z);
  float3 litColor = baseColor * EvaluateMainPartPreviewLight(normalView)
      + reflection;
  float3 color = lerp(litColor, baseColor, vertexColor.a * material.asg.y);
  float luminance = dot(color, float3(0.298999995, 0.587000012, 0.114));
  return float4(1.13 * color * (0.2 * luminance + 1.39999998), 1.0);
}
