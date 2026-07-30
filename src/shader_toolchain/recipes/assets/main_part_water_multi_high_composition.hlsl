#ifndef MAIN_PART_WATER_MULTI_HIGH_COMPOSITION_HLSL
#define MAIN_PART_WATER_MULTI_HIGH_COMPOSITION_HLSL

struct MainPartMultiWaterCompositeInput
{
  float3 viewPosition;
  float2 screenUv;
  float4 fogColor;
  float3 reflection;
  float3 directLight;
  float3 diffuseColor;
  float2 normalViewXY;
  float2 viewDirectionXY;
  float normalDotView;
  float viewDistance;
  float reflectionStrength;
  float fresnel;
  float surfaceBlend;
};

struct MainPartMultiWaterForwardOutput
{
  float4 color;
  float4 gForward;
};

MainPartMultiWaterForwardOutput ComposeMainPartMultiWater(
    MainPartMultiWaterCompositeInput input)
{
  float3 indirect = tIndirect.SampleLevel(
      PointClampClamp_s, input.screenUv, 0).xyz;
  float luminance = dot(indirect, float3(0.298999995,0.587000012,0.114));
  indirect *= 1.13;
  indirect *= luminance * 0.200000003 + 1.39999998;
  float indirectMean = dot(indirect, float3(0.333333343,0.333333343,0.333333343));
  float2 distanceShape = (float2(1.5,-6) + input.viewDistance)
      * float2(0.00999999978,0.166666672);
  float indirectDistanceWeight = min(1.0, distanceShape.y) * 1.25
      + saturate(distanceShape.x);
  float3 weightedIndirect = indirect * indirectDistanceWeight;
  float indirectBlend = 4.0 * indirectMean * indirectMean;
  float3 reflection = input.reflection
      + indirectBlend * (indirect * indirectDistanceWeight - input.reflection);

  float3 directDiffuse = input.directLight * input.diffuseColor;
  float3 litSurface = directDiffuse
      + input.reflectionStrength * (reflection - directDiffuse);
  litSurface += input.directLight * input.fresnel;

  if (input.surfaceBlend > 0.00100000005)
  {
    float refractionCurve = 1.0 - input.normalDotView * input.normalDotView;
    refractionCurve = sqrt(1.0 - refractionCurve * 0.565323055);
    refractionCurve = input.normalDotView * -0.751879692 - refractionCurve;
    float2 refractionOffset = refractionCurve * input.normalViewXY;
    refractionOffset = input.viewDirectionXY * 0.751879692 + refractionOffset;
    float projectionScale = 0.100000001 * cb_fProjectionScale
        / max(9.99999997e-07, -input.viewPosition.z);
    refractionOffset *= projectionScale;
    refractionOffset *= cb_vContainerPixelSize.xy;
    float2 frameUv = refractionOffset * cb_vRenderScale.xy + input.screenUv;
    float3 frame = tFrame.Sample(LinearClampClamp_s, frameUv).xyz;
    litSurface = frame + input.surfaceBlend * (litSurface - frame);
  }

  float indirectScale = dot(weightedIndirect, float3(0.333333343,0.333333343,0.333333343));
  indirectScale = 3.0 * indirectScale * max(0.125, input.surfaceBlend);
  float3 color = litSurface
      + indirectScale * (indirect * indirectDistanceWeight - litSurface);
  color = color + input.fogColor.w * (input.fogColor.xyz - color);

  MainPartMultiWaterForwardOutput result;
  result.color = float4(color, 1.0);
  result.gForward = float4(0,0,0,1);
  return result;
}

#endif
