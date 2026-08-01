#ifndef MAIN_PART_LIGHT_CAP_INCLUDED
#define MAIN_PART_LIGHT_CAP_INCLUDED

float2 ComputeMainPartLightCapUv(
    float3 viewPosition,
    float3 viewDirection,
    float3 normalView)
{
  // Reconstruct the source view-aligned light-cap basis. Its explicit
  // products preserve the recovered operation order near the view pole.
  float inversePoleDistance = rcp(
      -viewPosition.z * rsqrt(dot(-viewPosition, -viewPosition)) + 1.0);
  float3 viewProducts = viewDirection.yyz * viewDirection.zyz;
  viewProducts.xy *= inversePoleDistance;
  float basisMiddle = -viewProducts.z * inversePoleDistance + 1.0;

  float2 negativeViewYz = -viewDirection.yz;
  float2 foldedProducts = viewProducts.yx * float2(-1.0, 1.0)
      + float2(1.0, 0.0);
  float3 lightCapX = float3(
      foldedProducts.x, foldedProducts.y, negativeViewYz.x);
  float3 lightCapY = float3(
      foldedProducts.y, basisMiddle, negativeViewYz.y);
  return float2(dot(lightCapX, normalView), dot(lightCapY, normalView))
      * 0.493999988 + 0.5;
}

#endif
