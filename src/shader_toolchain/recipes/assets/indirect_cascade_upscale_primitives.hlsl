static const float UPSCALE_DEPTH_RANGE = 499.899994;
static const float UPSCALE_NEAR_DEPTH = 0.100000001;

struct UpscaleMaterialResponse
{
  float edgeResponse;
  float backgroundResponse;
  float tapRadiusScale;
};

struct UpscaledAoSss
{
  float ao;
  float4 sss;
};

struct AoSssAccumulator
{
  float coherentWeight;
  float coherentAo;
  float4 coherentSss;
  float fallbackWeight;
  float fallbackAo;
  float4 fallbackSss;
};

struct UpscaleCascadeSelection
{
  float3 coordinate;
  float2 centeredCoordinate;
  uint index;
};

struct UpscaleCascadeShadow
{
  float visibility;
  float boundaryDistance;
};

struct UpscaleTemporalResult
{
  float ao;
  float cascadeVisibility;
  float4 sss;
};

UpscaleMaterialResponse EvaluateUpscaleMaterial(float2 material)
{
  // The G-buffer channels shape edge response and the adaptive filter radius.
  float shapedResponse = 1.0 + -material.y;
  shapedResponse = log2(abs(shapedResponse));
  shapedResponse = 0.75 * shapedResponse;
  shapedResponse = exp2(shapedResponse);
  shapedResponse = 1.0 + -shapedResponse;
  float edgeResponse = shapedResponse * material.x;
  edgeResponse = saturate(3.5999999 * edgeResponse);
  edgeResponse = -0.150000006 + edgeResponse;
  edgeResponse = max(0.0, edgeResponse);
  edgeResponse = 1.42857146 * edgeResponse;
  edgeResponse = min(1.0, edgeResponse);

  UpscaleMaterialResponse response;
  response.edgeResponse = edgeResponse;
  response.backgroundResponse = 1.0 + -edgeResponse;
  response.tapRadiusScale =
      response.backgroundResponse * response.backgroundResponse;
  response.tapRadiusScale = response.tapRadiusScale * response.tapRadiusScale;
  return response;
}

float LinearizeUpscaleDepth(
    float deviceDepth, float projectionScale, float projectionBias)
{
  return projectionBias / (projectionScale + deviceDepth);
}

float3 TransformUpscalePosition(float4x4 matrixValue, float3 position)
{
  float3 transformed = matrixValue._m01_m11_m21 * position.y;
  transformed = matrixValue._m00_m10_m20 * position.x + transformed;
  transformed = matrixValue._m02_m12_m22 * position.z + transformed;
  return matrixValue._m03_m13_m23 + transformed;
}

bool IsInsideUpscaleCascade(float3 coordinate, float extent)
{
  return all(abs(coordinate - 0.5) <= extent.xxx);
}

UpscaleCascadeSelection SelectUpscaleCascade(
    float3 worldPosition,
    float4x4 cascade0,
    float4x4 cascade1,
    float4x4 cascade2,
    float4x4 cascade3)
{
  UpscaleCascadeSelection result;
  float3 coordinate0 = TransformUpscalePosition(cascade0, worldPosition);
  if (IsInsideUpscaleCascade(coordinate0, 0.5))
  {
    result.coordinate = coordinate0;
    result.centeredCoordinate = abs(coordinate0.xy - 0.5);
    result.index = 0;
    return result;
  }

  float3 coordinate1 = TransformUpscalePosition(cascade1, worldPosition);
  if (IsInsideUpscaleCascade(coordinate1, 0.5))
  {
    result.coordinate = coordinate1;
    result.centeredCoordinate = abs(coordinate1.xy - 0.5);
    result.index = 1;
    return result;
  }

  float3 coordinate2 = TransformUpscalePosition(cascade2, worldPosition);
  if (IsInsideUpscaleCascade(coordinate2, 0.5))
  {
    result.coordinate = coordinate2;
    result.centeredCoordinate = abs(coordinate2.xy - 0.5);
    result.index = 2;
    return result;
  }

  float3 coordinate3 = TransformUpscalePosition(cascade3, worldPosition);
  result.coordinate = coordinate3;
  result.centeredCoordinate = abs(coordinate3.xy - 0.5);
  result.index = IsInsideUpscaleCascade(coordinate3, 1.0) ? 3u : 4u;
  return result;
}

float3 ProjectUpscalePosition(float4x4 matrixValue, float3 position)
{
  float3 projected = matrixValue._m01_m11_m31 * position.y;
  projected = matrixValue._m00_m10_m30 * position.x + projected;
  projected = matrixValue._m02_m12_m32 * position.z + projected;
  return matrixValue._m03_m13_m33 + projected;
}

float4 SwizzleUpscaleSss(float4 value, uint4 channelMap)
{
  return float4(
      value[channelMap.x], value[channelMap.y],
      value[channelMap.z], value[channelMap.w]);
}

float ReadUpscaleVolatility(
    Texture2D<float> volatilityTexture, SamplerState linearSampler, float2 uv)
{
  float4 negative = volatilityTexture.Gather(linearSampler, uv) < 0.0;
  int2 pairs = (int2)negative.zw | (int2)negative.xy;
  bool forcedHistory = bool(pairs.y | pairs.x);
  float volatility = volatilityTexture.SampleLevel(linearSampler, uv, 0.0);
  return forcedHistory ? -1.0 : volatility;
}

UpscaleCascadeShadow SampleUpscaleMediumCascade(
    Texture2DArray<float4> cascadeTexture,
    SamplerComparisonState shadowSampler,
    float3 cascadeCoordinate,
    uint cascadeIndex,
    float cameraRangeFade,
    float cascadeSplit,
    float2 cascadeSize,
    float2 cascadePixelSize)
{
  // The medium path is an optimized fractional 17-weight PCF footprint.
  // Keep the recovered accumulation order: changing the association of these
  // products and sums measurably changes comparison-filter results.
  float4 normalGatherState = 0.0;
  float4 indirectGatherState = 0.0;
  float4 aoGatherState = 0.0;
  float4 subsurfaceGatherState = 0.0;
  float4 edgeRejectionState = 0.0;
  float4 bilateralWeightState = 0.0;
  float4 temporalRejectionState = 0.0;
  float4 weightedIndirectState = 0.0;

  normalGatherState.xyz = cascadeCoordinate;
  indirectGatherState.xy = abs(cascadeCoordinate.xy - 0.5);
  indirectGatherState.z = cascadeIndex;
  aoGatherState.z = cascadeIndex;

  float boundaryDistance = max(
      indirectGatherState.x, indirectGatherState.y);
  boundaryDistance = boundaryDistance + boundaryDistance;
  normalGatherState.w = cascadeSplit;
  normalGatherState.w = -normalGatherState.z * normalGatherState.w + 1.0;
  boundaryDistance = max(normalGatherState.w, boundaryDistance);
  boundaryDistance = 1.0 + -boundaryDistance;

  normalGatherState.w = aoGatherState.z * 2.0 + 1.0;
  normalGatherState.w = normalGatherState.w * cameraRangeFade;
  normalGatherState.z =
      normalGatherState.w * 5.99999985e-05 + normalGatherState.z;
  normalGatherState.xy =
      cascadeSize.yx * normalGatherState.yx + float2(0.5, 0.5);
  indirectGatherState.xy = floor(normalGatherState.yx);
  normalGatherState.xy = -indirectGatherState.yx + normalGatherState.xy;
  aoGatherState.xy = cascadePixelSize.xy * indirectGatherState.xy;

  indirectGatherState.xyw = cascadeTexture.GatherCmp(
      shadowSampler, aoGatherState.xyz, normalGatherState.z,
      int2(-2, -2)).xyz;
  subsurfaceGatherState.xy = float2(1.0, 1.0) + -normalGatherState.xy;
  normalGatherState.w = 0.5 * normalGatherState.y;
  edgeRejectionState.xyz = normalGatherState.yyy
      * float3(-0.5, -0.5, 0.5) + float3(0.5, 1.0, 0.5);
  bilateralWeightState.xyz =
      edgeRejectionState.xxy * indirectGatherState.wyy;

  temporalRejectionState = cascadeTexture.GatherCmp(
      shadowSampler, aoGatherState.xyz, normalGatherState.z, int2(0, -2));
  weightedIndirectState =
      temporalRejectionState.wzxy * edgeRejectionState.yzyz;
  indirectGatherState.yw = weightedIndirectState.xz + weightedIndirectState.yw;
  indirectGatherState.y = subsurfaceGatherState.x * indirectGatherState.y;
  indirectGatherState.y =
      subsurfaceGatherState.x * bilateralWeightState.x + indirectGatherState.y;
  indirectGatherState.w = indirectGatherState.w * normalGatherState.x;
  indirectGatherState.w =
      normalGatherState.x * bilateralWeightState.y + indirectGatherState.w;

  bilateralWeightState.xyw = cascadeTexture.GatherCmp(
      shadowSampler, aoGatherState.xyz, normalGatherState.z,
      int2(2, -2)).xyw;
  subsurfaceGatherState.zw = bilateralWeightState.wx * normalGatherState.ww;
  indirectGatherState.y =
      subsurfaceGatherState.x * subsurfaceGatherState.z + indirectGatherState.y;
  indirectGatherState.w =
      normalGatherState.x * subsurfaceGatherState.w + indirectGatherState.w;

  weightedIndirectState = cascadeTexture.GatherCmp(
      shadowSampler, aoGatherState.xyz, normalGatherState.z, int2(-2, 0));
  subsurfaceGatherState.yz = weightedIndirectState.wx
      * subsurfaceGatherState.yy + weightedIndirectState.zy;
  indirectGatherState.y =
      subsurfaceGatherState.x * subsurfaceGatherState.y + indirectGatherState.y;
  indirectGatherState.w =
      normalGatherState.x * subsurfaceGatherState.z + indirectGatherState.w;
  aoGatherState.w = -normalGatherState.y * 0.5 + 0.5;
  indirectGatherState.x =
      indirectGatherState.x * aoGatherState.w + bilateralWeightState.z;
  subsurfaceGatherState.yz =
      weightedIndirectState.zy * edgeRejectionState.yy;
  subsurfaceGatherState.yz = weightedIndirectState.wx * aoGatherState.ww
      + subsurfaceGatherState.yz;

  weightedIndirectState = cascadeTexture.GatherCmp(
      shadowSampler, aoGatherState.xyz, normalGatherState.z);
  bilateralWeightState.zw = weightedIndirectState.xw + weightedIndirectState.yz;
  indirectGatherState.y =
      subsurfaceGatherState.x * bilateralWeightState.w + indirectGatherState.y;
  subsurfaceGatherState.w = bilateralWeightState.w * normalGatherState.x;
  indirectGatherState.w =
      normalGatherState.x * bilateralWeightState.z + indirectGatherState.w;
  edgeRejectionState.w = temporalRejectionState.x + temporalRejectionState.y;
  edgeRejectionState.w = edgeRejectionState.w * subsurfaceGatherState.x;
  indirectGatherState.x =
      subsurfaceGatherState.x * indirectGatherState.x + edgeRejectionState.w;
  subsurfaceGatherState.y =
      normalGatherState.x * subsurfaceGatherState.y + subsurfaceGatherState.w;

  temporalRejectionState = cascadeTexture.GatherCmp(
      shadowSampler, aoGatherState.xyz, normalGatherState.z, int2(2, 0));
  weightedIndirectState.xy = temporalRejectionState.zy * normalGatherState.yy;
  temporalRejectionState.yz = temporalRejectionState.zy
      * normalGatherState.yy + temporalRejectionState.wx;
  indirectGatherState.y =
      subsurfaceGatherState.x * temporalRejectionState.y + indirectGatherState.y;
  indirectGatherState.w =
      normalGatherState.x * temporalRejectionState.z + indirectGatherState.w;
  subsurfaceGatherState.w = bilateralWeightState.y * normalGatherState.y;
  subsurfaceGatherState.w = 0.5 * subsurfaceGatherState.w;
  subsurfaceGatherState.w = bilateralWeightState.x * edgeRejectionState.z
      + subsurfaceGatherState.w;
  indirectGatherState.x =
      subsurfaceGatherState.x * subsurfaceGatherState.w + indirectGatherState.x;
  bilateralWeightState.xy = 0.5 * weightedIndirectState.xy;
  bilateralWeightState.xy = temporalRejectionState.wx * edgeRejectionState.zz
      + bilateralWeightState.xy;
  subsurfaceGatherState.y =
      normalGatherState.x * bilateralWeightState.x + subsurfaceGatherState.y;

  temporalRejectionState.xyz = cascadeTexture.GatherCmp(
      shadowSampler, aoGatherState.xyz, normalGatherState.z,
      int2(-2, 2)).yzw;
  temporalRejectionState.xyw =
      temporalRejectionState.yxy * edgeRejectionState.xxy;
  indirectGatherState.y =
      subsurfaceGatherState.x * temporalRejectionState.x + indirectGatherState.y;
  indirectGatherState.w =
      normalGatherState.x * temporalRejectionState.y + indirectGatherState.w;
  indirectGatherState.x =
      subsurfaceGatherState.x * subsurfaceGatherState.z + indirectGatherState.x;
  aoGatherState.w =
      temporalRejectionState.z * aoGatherState.w + temporalRejectionState.w;
  aoGatherState.w = normalGatherState.x * aoGatherState.w
      + subsurfaceGatherState.y;

  temporalRejectionState = cascadeTexture.GatherCmp(
      shadowSampler, aoGatherState.xyz, normalGatherState.z, int2(0, 2));
  weightedIndirectState =
      temporalRejectionState.wzxy * edgeRejectionState.yzyz;
  subsurfaceGatherState.yz = weightedIndirectState.xz + weightedIndirectState.yw;
  indirectGatherState.y =
      subsurfaceGatherState.x * subsurfaceGatherState.y + indirectGatherState.y;
  indirectGatherState.w =
      normalGatherState.x * subsurfaceGatherState.z + indirectGatherState.w;
  indirectGatherState.x =
      subsurfaceGatherState.x * bilateralWeightState.z + indirectGatherState.x;
  subsurfaceGatherState.y = temporalRejectionState.w + temporalRejectionState.z;
  aoGatherState.w =
      normalGatherState.x * subsurfaceGatherState.y + aoGatherState.w;

  aoGatherState.xyz = cascadeTexture.GatherCmp(
      shadowSampler, aoGatherState.xyz, normalGatherState.z,
      int2(2, 2)).xzw;
  normalGatherState.yzw = aoGatherState.yzx * normalGatherState.yww;
  temporalRejectionState.x =
      subsurfaceGatherState.x * normalGatherState.z + indirectGatherState.y;
  temporalRejectionState.y =
      normalGatherState.x * normalGatherState.w + indirectGatherState.w;
  temporalRejectionState.z =
      subsurfaceGatherState.x * bilateralWeightState.y + indirectGatherState.x;
  normalGatherState.y = 0.5 * normalGatherState.y;
  normalGatherState.y =
      aoGatherState.z * edgeRejectionState.z + normalGatherState.y;
  temporalRejectionState.w =
      normalGatherState.x * normalGatherState.y + aoGatherState.w;
  normalGatherState.x = dot(
      temporalRejectionState, float4(1.0, 1.0, 1.0, 1.0));

  UpscaleCascadeShadow result;
  result.visibility = 0.0588235296 * normalGatherState.x;
  result.boundaryDistance = boundaryDistance;
  return result;
}

UpscaleCascadeShadow SampleUpscaleLowCascade(
    Texture2DArray<float4> cascadeTexture,
    SamplerComparisonState shadowSampler,
    float3 cascadeCoordinate,
    uint cascadeIndex,
    float cameraRangeFade,
    float cascadeSplit,
    float2 cascadeSize,
    float2 cascadePixelSize)
{
  // Four comparison gathers form the recovered seven-weight low PCF kernel.
  float4 normalGatherState = 0.0;
  float4 indirectGatherState = 0.0;
  float4 aoGatherState = 0.0;
  float4 subsurfaceGatherState = 0.0;
  float4 edgeRejectionState = 0.0;
  float4 bilateralWeightState = 0.0;
  float4 temporalRejectionState = 0.0;

  normalGatherState.xyz = cascadeCoordinate;
  indirectGatherState.xy = abs(cascadeCoordinate.xy - 0.5);
  aoGatherState.z = cascadeIndex;
  float boundaryDistance = max(
      indirectGatherState.x, indirectGatherState.y);
  boundaryDistance = boundaryDistance + boundaryDistance;
  normalGatherState.w = cascadeSplit;
  normalGatherState.w = -normalGatherState.z * normalGatherState.w + 1.0;
  boundaryDistance = max(normalGatherState.w, boundaryDistance);
  boundaryDistance = 1.0 + -boundaryDistance;

  normalGatherState.w = aoGatherState.z * 2.0 + 1.0;
  normalGatherState.w = normalGatherState.w * cameraRangeFade;
  normalGatherState.z =
      normalGatherState.w * 5.99999985e-05 + normalGatherState.z;
  normalGatherState.xy =
      cascadeSize.yx * normalGatherState.yx + float2(0.5, 0.5);
  indirectGatherState.xy = floor(normalGatherState.yx);
  normalGatherState.xy = -indirectGatherState.yx + normalGatherState.xy;
  aoGatherState.xy = cascadePixelSize.xy * indirectGatherState.xy;

  subsurfaceGatherState = cascadeTexture.GatherCmp(
      shadowSampler, aoGatherState.xyz, normalGatherState.z,
      int2(-1, -1));
  indirectGatherState.xy = float2(1.0, 1.0) + -normalGatherState.xy;
  normalGatherState.w = -normalGatherState.y * 0.5 + 0.5;
  edgeRejectionState.xy = normalGatherState.yy * float2(-0.5, 0.5)
      + float2(1.0, 0.5);
  edgeRejectionState.zw = edgeRejectionState.xx * subsurfaceGatherState.zy;
  subsurfaceGatherState.zw = subsurfaceGatherState.wx * normalGatherState.ww
      + edgeRejectionState.zw;

  bilateralWeightState = cascadeTexture.GatherCmp(
      shadowSampler, aoGatherState.xyz, normalGatherState.z,
      int2(1, -1));
  edgeRejectionState.zw = bilateralWeightState.zy * normalGatherState.yy;
  edgeRejectionState.zw = 0.5 * edgeRejectionState.zw;
  edgeRejectionState.zw = bilateralWeightState.wx * edgeRejectionState.yy
      + edgeRejectionState.zw;
  indirectGatherState.w = edgeRejectionState.z * indirectGatherState.x;
  indirectGatherState.w = indirectGatherState.x * subsurfaceGatherState.z
      + indirectGatherState.w;
  aoGatherState.w = edgeRejectionState.w * normalGatherState.x;
  aoGatherState.w = normalGatherState.x * subsurfaceGatherState.w
      + aoGatherState.w;

  temporalRejectionState = cascadeTexture.GatherCmp(
      shadowSampler, aoGatherState.xyz, normalGatherState.z,
      int2(-1, 1));
  subsurfaceGatherState.zw = temporalRejectionState.zy * edgeRejectionState.xx;
  subsurfaceGatherState.zw = temporalRejectionState.wx * normalGatherState.ww
      + subsurfaceGatherState.zw;
  normalGatherState.w = indirectGatherState.x * subsurfaceGatherState.z
      + indirectGatherState.w;
  indirectGatherState.w = normalGatherState.x * subsurfaceGatherState.w
      + aoGatherState.w;
  aoGatherState.w = subsurfaceGatherState.x * indirectGatherState.y
      + subsurfaceGatherState.y;
  indirectGatherState.y = temporalRejectionState.w * indirectGatherState.y
      + temporalRejectionState.z;

  subsurfaceGatherState = cascadeTexture.GatherCmp(
      shadowSampler, aoGatherState.xyz, normalGatherState.z,
      int2(1, 1));
  aoGatherState.xy = subsurfaceGatherState.zy * normalGatherState.yy;
  aoGatherState.xy = 0.5 * aoGatherState.xy;
  aoGatherState.xy = subsurfaceGatherState.wx * edgeRejectionState.yy
      + aoGatherState.xy;
  edgeRejectionState.x = indirectGatherState.x * aoGatherState.x
      + normalGatherState.w;
  edgeRejectionState.y = normalGatherState.x * aoGatherState.y
      + indirectGatherState.w;
  normalGatherState.z = bilateralWeightState.y * normalGatherState.y
      + bilateralWeightState.x;
  normalGatherState.z = indirectGatherState.x * normalGatherState.z;
  edgeRejectionState.z = indirectGatherState.x * aoGatherState.w
      + normalGatherState.z;
  normalGatherState.y = subsurfaceGatherState.z * normalGatherState.y
      + subsurfaceGatherState.w;
  normalGatherState.y = normalGatherState.x * normalGatherState.y;
  edgeRejectionState.w = normalGatherState.x * indirectGatherState.y
      + normalGatherState.y;
  normalGatherState.x = dot(
      edgeRejectionState, float4(1.0, 1.0, 1.0, 1.0));

  UpscaleCascadeShadow result;
  result.visibility = 0.142857149 * normalGatherState.x;
  result.boundaryDistance = boundaryDistance;
  return result;
}

float3 SelectNextUpscaleCascadeCoordinate(
    float3 worldPosition,
    uint cascadeIndex,
    float4x4 cascade1,
    float4x4 cascade2,
    float4x4 cascade3)
{
  if (cascadeIndex == 0u)
    return TransformUpscalePosition(cascade1, worldPosition);
  if (cascadeIndex == 1u)
    return TransformUpscalePosition(cascade2, worldPosition);
  return TransformUpscalePosition(cascade3, worldPosition);
}

float EvaluateUpscaleMediumCascadeShadow(
    Texture2DArray<float4> cascadeTexture,
    SamplerComparisonState shadowSampler,
    UpscaleCascadeSelection selection,
    float3 worldPosition,
    float cameraRangeFade,
    float4 cascadeSplits,
    float2 cascadeSize,
    float2 cascadePixelSize,
    float4x4 cascade1,
    float4x4 cascade2,
    float4x4 cascade3)
{
  if (selection.index > 3u)
    return 1.0;

  uint cascadeIndex = selection.index;
  UpscaleCascadeShadow primary = SampleUpscaleMediumCascade(
      cascadeTexture, shadowSampler, selection.coordinate, cascadeIndex,
      cameraRangeFade, cascadeSplits[cascadeIndex], cascadeSize,
      cascadePixelSize);

  float blendWidth = 0.109999999 * float(cascadeIndex + 1u);
  if (primary.boundaryDistance >= blendWidth)
    return primary.visibility;

  float blend = saturate(primary.boundaryDistance / blendWidth);
  float outerVisibility = 1.0;
  if (cascadeIndex != 3u)
  {
    float3 outerCoordinate = SelectNextUpscaleCascadeCoordinate(
        worldPosition, cascadeIndex, cascade1, cascade2, cascade3);
    UpscaleCascadeShadow outer = SampleUpscaleMediumCascade(
        cascadeTexture, shadowSampler, outerCoordinate, cascadeIndex + 1u,
        cameraRangeFade, cascadeSplits[cascadeIndex + 1u], cascadeSize,
        cascadePixelSize);
    outerVisibility = outer.visibility;
  }

  float difference = primary.visibility + -outerVisibility;
  return blend * difference + outerVisibility;
}

float EvaluateUpscaleLowCascadeShadow(
    Texture2DArray<float4> cascadeTexture,
    SamplerComparisonState shadowSampler,
    UpscaleCascadeSelection selection,
    float3 worldPosition,
    float cameraRangeFade,
    float4 cascadeSplits,
    float2 cascadeSize,
    float2 cascadePixelSize,
    float4x4 cascade1,
    float4x4 cascade2,
    float4x4 cascade3)
{
  if (selection.index > 3u)
    return 1.0;

  uint cascadeIndex = selection.index;
  UpscaleCascadeShadow primary = SampleUpscaleLowCascade(
      cascadeTexture, shadowSampler, selection.coordinate, cascadeIndex,
      cameraRangeFade, cascadeSplits[cascadeIndex], cascadeSize,
      cascadePixelSize);
  float blendWidth = 0.109999999 * float(cascadeIndex + 1u);
  if (primary.boundaryDistance >= blendWidth)
    return primary.visibility;

  float blend = saturate(primary.boundaryDistance / blendWidth);
  float outerVisibility = 1.0;
  if (cascadeIndex != 3u)
  {
    float3 outerCoordinate = SelectNextUpscaleCascadeCoordinate(
        worldPosition, cascadeIndex, cascade1, cascade2, cascade3);
    UpscaleCascadeShadow outer = SampleUpscaleLowCascade(
        cascadeTexture, shadowSampler, outerCoordinate, cascadeIndex + 1u,
        cameraRangeFade, cascadeSplits[cascadeIndex + 1u], cascadeSize,
        cascadePixelSize);
    outerVisibility = outer.visibility;
  }
  float difference = primary.visibility + -outerVisibility;
  return blend * difference + outerVisibility;
}

float ApplyUpscaleDirectionalFacing(
    float shadowVisibility, float3 normal, float3 lightDirectionView)
{
  float facing = dot(normal, -lightDirectionView);
  facing = 0.400000006 + facing;
  facing = saturate(1.66666663 * facing);
  float smoothFactor = facing * -2.0 + 3.0;
  facing = facing * facing;
  facing = smoothFactor * facing;
  return saturate(shadowVisibility * facing);
}

float ComposeUpscaleAo(
    float spatialAo,
    float sssOcclusion,
    float cascadeVisibility,
    float viewDepth)
{
  float shadowedSss = min(sssOcclusion, cascadeVisibility);
  float depthResponse = -4.0 + viewDepth;
  depthResponse = saturate(0.00100000005 * depthResponse);
  depthResponse = depthResponse * 0.25 + 0.075000003;
  depthResponse = 0.5 * depthResponse;
  float missingShadow = 1.0 + -cascadeVisibility;
  float missingShadowedSss = 1.0 + -shadowedSss;
  float shadowResponse = depthResponse * missingShadow + depthResponse;
  return -missingShadowedSss * shadowResponse + spatialAo;
}

UpscaleTemporalResult ResolveUpscaleTemporal(
    Texture2D<float2> temporalAoTexture,
    Texture2D<float4> temporalSssTexture,
    Texture2D<float> volatilityTexture,
    SamplerState linearSampler,
    float2 currentUv,
    float viewDepth,
    float3 viewPosition,
    float3 worldPosition,
    float spatialAo,
    float4 currentSss,
    float sssComplement,
    float sssOcclusion,
    float cascadeVisibility,
    float4x4 previousWorldToProjection,
    float3 previousCameraPosition,
    float3 currentCameraPosition,
    float2 previousRenderScale,
    float2 previousUvLimit,
    float renderScaleStability,
    float frameRateScale,
    uint4 sssChannelMap)
{
  UpscaleTemporalResult result;
  result.ao = ComposeUpscaleAo(
      spatialAo, sssOcclusion, cascadeVisibility, viewDepth);
  result.cascadeVisibility = cascadeVisibility;
  result.sss = currentSss;

  float3 previousClip = ProjectUpscalePosition(
      previousWorldToProjection, worldPosition);
  float2 insidePrevious = abs(previousClip.xy) < previousClip.zz;
  if (!(insidePrevious.x && insidePrevious.y))
    return result;

  float viewDistance = dot(viewPosition, viewPosition);
  viewDistance = sqrt(viewDistance);
  float2 previousNdc = previousClip.xy / previousClip.zz;
  float2 previousUv = previousNdc * float2(0.5, -0.5)
      + float2(0.5, 0.5);
  previousUv = previousRenderScale * previousUv;

  float nearDepthWeight = -0.800000012 + viewDepth;
  nearDepthWeight = saturate(4.0 * nearDepthWeight);
  nearDepthWeight = nearDepthWeight * 0.200000003 + 0.800000012;
  float viewDistanceWeight = -2.0 + viewDistance;
  viewDistanceWeight = saturate(0.5 * viewDistanceWeight);
  viewDistanceWeight = 1.0 + -viewDistanceWeight;

  float3 cameraDelta =
      -previousCameraPosition + currentCameraPosition;
  float cameraMotion = dot(cameraDelta, cameraDelta);
  cameraMotion = sqrt(cameraMotion);
  float motionScale = max(0.00999999978, viewDepth);
  motionScale = log2(motionScale);
  motionScale = 1.5 * motionScale;
  motionScale = exp2(motionScale);
  motionScale = 0.00499999989 * motionScale;
  motionScale = max(0.00999999978, motionScale);
  float cameraStability = cameraMotion / motionScale;
  cameraStability = min(1.0, cameraStability);
  cameraStability = 1.0 + -cameraStability;

  float volatility = ReadUpscaleVolatility(
      volatilityTexture, linearSampler, currentUv);
  float reprojectionStability = 1.0 + -abs(volatility);
  bool forcedCurrentPixel = volatility < 0.0;
  float lostStability = 1.0 + -reprojectionStability;
  float nearDepthInstability = -nearDepthWeight * 0.600000024 + 1.0;
  float forcedStability = lostStability * nearDepthInstability;
  if (forcedCurrentPixel)
  {
    previousUv = currentUv;
    reprojectionStability = forcedStability;
  }
  reprojectionStability = renderScaleStability * reprojectionStability;
  previousUv = min(previousUvLimit, previousUv);

  float2 previousAo = temporalAoTexture.SampleLevel(
      linearSampler, previousUv, 0.0);
  float4 previousSss = SwizzleUpscaleSss(
      temporalSssTexture.SampleLevel(linearSampler, previousUv, 0.0),
      sssChannelMap);

  float2 historyResponse = saturate(
      float2(0.100000001, 0.5) * viewDepth.xx);
  historyResponse = historyResponse * float2(0.139999986, 0.139999986)
      + float2(0.0699999928, 0.0);
  historyResponse = frameRateScale * historyResponse
      + float2(0.75, 0.819999993);

  float motionResponse = cameraStability * 0.600000024 + 0.400000006;
  float cascadeHistoryScale = historyResponse.y * motionResponse;
  float stableMotionResponse = forcedCurrentPixel ? 1.0 : motionResponse;
  float aoHistoryWeight = historyResponse.x * stableMotionResponse;
  float stabilityFloor = reprojectionStability * 0.875 + 0.125;
  aoHistoryWeight = stabilityFloor * aoHistoryWeight;
  aoHistoryWeight = aoHistoryWeight * nearDepthWeight;

  float2 currentAo = float2(result.ao, cascadeVisibility);
  float2 historyDelta = -previousAo + currentAo;
  float2 historyAccepted = abs(historyDelta) < float2(0.5, 0.75);
  float2 aboveMinimum = currentAo >= float2(0.0500000007, 0.25);
  historyAccepted = historyAccepted ? aboveMinimum : 0.0;
  float2 belowMaximum = currentAo < float2(0.949999988, 0.75);
  historyAccepted = historyAccepted ? belowMaximum : 0.0;

  float acceptedAoWeight = historyAccepted.x ? aoHistoryWeight : 0.0;
  float forcedMask = forcedCurrentPixel ? -1.0 : 0.0;
  float cascadeCoefficient = historyAccepted.y
      ? -0.180000007 : 0.819999993;
  float cascadeHistoryWeight =
      viewDistanceWeight * cascadeCoefficient + forcedMask;
  cascadeHistoryScale = cascadeHistoryScale * cascadeHistoryWeight;

  float sssSurfaceWeight = 9.99999975e-05 < sssComplement
      ? 0.959999979 : 0.5;
  float sssHistoryWeight = sssSurfaceWeight * stableMotionResponse;
  sssHistoryWeight = sssHistoryWeight * stabilityFloor;
  float sssSpatialStability = min(nearDepthWeight, viewDistanceWeight);
  sssHistoryWeight = sssHistoryWeight * sssSpatialStability;

  float4 sssDelta = previousSss + -currentSss;
  result.sss = sssHistoryWeight * sssDelta + currentSss;
  float2 previousDelta = previousAo + -currentAo;
  result.cascadeVisibility =
      cascadeHistoryScale * previousDelta.y + cascadeVisibility;
  result.ao = acceptedAoWeight * previousDelta.x + result.ao;
  return result;
}

UpscaleTemporalResult ResolveUpscaleTemporalWithoutCascadeHistory(
    Texture2D<float2> temporalAoTexture,
    Texture2D<float4> temporalSssTexture,
    Texture2D<float> volatilityTexture,
    SamplerState linearSampler,
    float2 currentUv,
    float viewDepth,
    float3 viewPosition,
    float3 worldPosition,
    float spatialAo,
    float4 currentSss,
    float sssComplement,
    float sssOcclusion,
    float cascadeVisibility,
    float4x4 previousWorldToProjection,
    float3 previousCameraPosition,
    float3 currentCameraPosition,
    float2 previousRenderScale,
    float2 previousUvLimit,
    float renderScaleStability,
    float frameRateScale,
    uint4 sssChannelMap)
{
  UpscaleTemporalResult result;
  result.ao = ComposeUpscaleAo(
      spatialAo, sssOcclusion, cascadeVisibility, viewDepth);
  result.cascadeVisibility = cascadeVisibility;
  result.sss = currentSss;

  float3 previousClip = ProjectUpscalePosition(
      previousWorldToProjection, worldPosition);
  float2 insidePrevious = abs(previousClip.xy) < previousClip.zz;
  if (!(insidePrevious.x && insidePrevious.y))
    return result;

  float viewDistance = dot(viewPosition, viewPosition);
  viewDistance = sqrt(viewDistance);
  float2 previousNdc = previousClip.xy / previousClip.zz;
  float2 previousUv = previousNdc * float2(0.5, -0.5)
      + float2(0.5, 0.5);
  previousUv = previousRenderScale * previousUv;

  float nearDepthWeight = -0.800000012 + viewDepth;
  nearDepthWeight = saturate(4.0 * nearDepthWeight);
  nearDepthWeight = nearDepthWeight * 0.200000003 + 0.800000012;
  float viewDistanceWeight = -2.0 + viewDistance;
  viewDistanceWeight = saturate(0.5 * viewDistanceWeight);
  viewDistanceWeight = 1.0 + -viewDistanceWeight;

  float3 cameraDelta = -previousCameraPosition + currentCameraPosition;
  float cameraMotion = dot(cameraDelta, cameraDelta);
  cameraMotion = sqrt(cameraMotion);
  float motionScale = max(0.00999999978, viewDepth);
  motionScale = log2(motionScale);
  motionScale = 1.5 * motionScale;
  motionScale = exp2(motionScale);
  motionScale = 0.00499999989 * motionScale;
  motionScale = max(0.00999999978, motionScale);
  float cameraStability = cameraMotion / motionScale;
  cameraStability = min(1.0, cameraStability);
  cameraStability = 1.0 + -cameraStability;

  float volatility = ReadUpscaleVolatility(
      volatilityTexture, linearSampler, currentUv);
  float reprojectionStability = 1.0 + -abs(volatility);
  bool forcedCurrentPixel = volatility < 0.0;
  float lostStability = 1.0 + -reprojectionStability;
  float nearDepthInstability = -nearDepthWeight * 0.600000024 + 1.0;
  float forcedStability = lostStability * nearDepthInstability;
  if (forcedCurrentPixel)
  {
    previousUv = currentUv;
    reprojectionStability = forcedStability;
  }
  reprojectionStability = renderScaleStability * reprojectionStability;
  previousUv = min(previousUvLimit, previousUv);

  float previousAo = temporalAoTexture.SampleLevel(
      linearSampler, previousUv, 0.0).x;
  float4 previousSss = SwizzleUpscaleSss(
      temporalSssTexture.SampleLevel(linearSampler, previousUv, 0.0),
      sssChannelMap);

  float historyResponse = saturate(0.100000001 * viewDepth);
  historyResponse = historyResponse * 0.139999986 + 0.0699999928;
  historyResponse = frameRateScale * historyResponse + 0.75;
  float stableMotionResponse = forcedCurrentPixel ? 1.0 : cameraStability;
  float aoHistoryWeight = historyResponse * stableMotionResponse;
  float stabilityFloor = reprojectionStability * 0.875 + 0.125;
  aoHistoryWeight = aoHistoryWeight * stabilityFloor;
  aoHistoryWeight = aoHistoryWeight * nearDepthWeight;

  float aoDifference = -previousAo + result.ao;
  bool aoAccepted = abs(aoDifference) < 0.5;
  aoAccepted = result.ao >= 0.0500000007 ? aoAccepted : false;
  aoAccepted = result.ao < 0.949999988 ? aoAccepted : false;
  float acceptedAoWeight = aoAccepted ? aoHistoryWeight : 0.0;

  float sssSurfaceWeight = 9.99999975e-05 < sssComplement
      ? 0.959999979 : 0.5;
  float sssHistoryWeight = sssSurfaceWeight * stableMotionResponse;
  sssHistoryWeight = sssHistoryWeight * stabilityFloor;
  float sssSpatialStability = min(nearDepthWeight, viewDistanceWeight);
  sssHistoryWeight = sssHistoryWeight * sssSpatialStability;

  float4 sssDelta = previousSss + -currentSss;
  result.sss = sssHistoryWeight * sssDelta + currentSss;
  float previousAoDelta = previousAo + -result.ao;
  result.ao = acceptedAoWeight * previousAoDelta + result.ao;
  return result;
}

float3 DecodeUpscaleNormal(float2 encoded)
{
  // The normal buffer uses the usual signed octahedral projection.
  encoded = encoded * float2(2.0, 2.0) + float2(-1.0, -1.0);
  float z = 1.0 + -abs(encoded.x) + -abs(encoded.y);
  float fold = saturate(-z);
  float2 correction = encoded >= float2(0.0, 0.0);
  correction = correction ? -fold.xx : fold.xx;
  float3 normal = float3(encoded + correction, z);
  return normal * rsqrt(dot(normal, normal));
}

float4 GatherUpscaleDepthError(
    Texture2D<float> depthTexture, SamplerState linearSampler,
    float2 uv, float centerDepth)
{
  // AO depth is sqrt-normalized over the recovered 0.1 .. 500 range.
  float4 gatheredDepth = depthTexture.Gather(linearSampler, uv);
  gatheredDepth = gatheredDepth * gatheredDepth;
  gatheredDepth = gatheredDepth * float4(
      UPSCALE_DEPTH_RANGE, UPSCALE_DEPTH_RANGE,
      UPSCALE_DEPTH_RANGE, UPSCALE_DEPTH_RANGE)
      + float4(
          UPSCALE_NEAR_DEPTH, UPSCALE_NEAR_DEPTH,
          UPSCALE_NEAR_DEPTH, UPSCALE_NEAR_DEPTH);
  float4 depthError = gatheredDepth + -centerDepth.xxxx;
  return depthError * depthError;
}

float ComputeUpscaleGaussianWeight(
    float4 squaredDepthError, float inverseThreshold)
{
  float meanSquaredError = dot(
      squaredDepthError, float4(0.25, 0.25, 0.25, 0.25));
  float exponent = -meanSquaredError * inverseThreshold;
  exponent = 1.44269502 * exponent;
  return exp2(exponent);
}

float ComputeUpscaleCoverageWeight(
    float4 squaredDepthError, float threshold, float responseExponent)
{
  float4 coverage = squaredDepthError / threshold.xxxx;
  coverage = float4(1.0, 1.0, 1.0, 1.0) + -coverage;
  coverage = max(float4(0.0, 0.0, 0.0, 0.0), coverage);
  float meanCoverage = dot(coverage, float4(0.25, 0.25, 0.25, 0.25));
  meanCoverage = log2(meanCoverage);
  meanCoverage = meanCoverage * responseExponent;
  return exp2(meanCoverage);
}

void AccumulateAoSssFootprint(
    Texture2D<float> depthTexture,
    Texture2D<float4> aoTexture,
    Texture2D<float4> sssTexture,
    SamplerState linearSampler,
    int2 samplePixel,
    float coherentBias,
    float centerDepth,
    float threshold,
    float inverseThreshold,
    float responseExponent,
    float edgeResponse,
    float2 targetSize,
    float2 renderScale,
    float2 containerPixelSize,
    float2 inverseSourceScale,
    float2 sourceUvLimit,
    inout AoSssAccumulator accumulator)
{
  if (!all(samplePixel > int2(0, 0)) || !all(samplePixel < (int2)targetSize))
    return;

  float2 gatherUv = float2(samplePixel) / targetSize;
  float2 halfPixel = 0.5 * renderScale * containerPixelSize;
  gatherUv = gatherUv * renderScale + halfPixel;
  float4 depthError = GatherUpscaleDepthError(
      depthTexture, linearSampler, gatherUv, centerDepth);
  float4 accepted = depthError < threshold.xxxx;
  accepted = accepted ? float4(1.0, 1.0, 1.0, 1.0) : 0.0;
  float acceptedCount = dot(accepted, float4(1.0, 1.0, 1.0, 1.0));

  float2 sourceUv = min(sourceUvLimit, inverseSourceScale * gatherUv);
  float ao = aoTexture.SampleLevel(linearSampler, sourceUv, 0.0).w;
  float4 sss = sssTexture.SampleLevel(linearSampler, sourceUv, 0.0);
  if (acceptedCount <= 3.0)
  {
    float weight = acceptedCount * 0.25 + 0.00999999978;
    accumulator.fallbackWeight = weight + accumulator.fallbackWeight;
    accumulator.fallbackAo = ao * weight + accumulator.fallbackAo;
    accumulator.fallbackSss = sss * weight + accumulator.fallbackSss;
    return;
  }

  float gaussian = ComputeUpscaleGaussianWeight(depthError, inverseThreshold);
  float adjusted = edgeResponse * (coherentBias - gaussian) + gaussian;
  float coverage = ComputeUpscaleCoverageWeight(
      depthError, threshold, responseExponent);
  float weight = adjusted * coverage;
  accumulator.coherentAo = ao * weight + accumulator.coherentAo;
  accumulator.coherentWeight = adjusted * coverage + accumulator.coherentWeight;
  accumulator.coherentSss = sss * weight + accumulator.coherentSss;
}

UpscaledAoSss FilterAoSssCross(
    Texture2D<float> depthTexture,
    Texture2D<float4> aoTexture,
    Texture2D<float4> sssTexture,
    Texture2D<float4> materialTexture,
    SamplerState linearSampler,
    int2 pixel,
    float centerDepth,
    float2 targetSize,
    float2 renderScale,
    float2 containerPixelSize,
    float2 inverseSourceScale,
    float2 sourceUvLimit,
    float resolutionScale,
    uint frameIndex,
    float frameRateScale)
{
  UpscaledAoSss result;
  if (centerDepth >= UPSCALE_DEPTH_RANGE)
  {
    result.ao = 1.0;
    result.sss = 0.0;
    return result;
  }

  UpscaleMaterialResponse material = EvaluateUpscaleMaterial(
      materialTexture.Load(int3(pixel, 0)).xy);
  float threshold = centerDepth * centerDepth;
  threshold *= resolutionScale * -0.0199999996 + 0.0299999993;
  threshold = max(0.00999999978, threshold);
  threshold = min(0.5, threshold);
  threshold = threshold * threshold;
  float inverseThreshold = rcp(threshold);
  float responseExponent = resolutionScale * 8.0 + 4.0;

  bool highResolution = 0.0 < resolutionScale;
  float jitterEnabled = highResolution ? 1.0 : 0.0;
  uint phaseCount = (uint)(material.edgeResponse * -2.0 + 3.0);
  uint baseStride = highResolution ? 2u : 1u;
  float depthJitter = 1.0 - saturate(0.25 * centerDepth);
  uint phase = asuint(frameIndex) % phaseCount;
  float jitter = depthJitter * float(phase);
  jitter = frameRateScale * jitter;
  uint stride = (uint)(jitter * jitterEnabled + float(baseStride));
  float radiusScale = resolutionScale * material.tapRadiusScale;
  radiusScale = radiusScale * 4.0 + 1.0;
  uint radius = (uint)(float(stride) * radiusScale);

  AoSssAccumulator accumulated;
  accumulated.coherentWeight = 0.0;
  accumulated.coherentAo = 0.0;
  accumulated.coherentSss = 0.0;
  accumulated.fallbackWeight = 0.0;
  accumulated.fallbackAo = 0.0;
  accumulated.fallbackSss = 0.0;

  AccumulateAoSssFootprint(depthTexture, aoTexture, sssTexture, linearSampler,
      pixel + int2(0, -int(radius)), 0.125, centerDepth, threshold,
      inverseThreshold, responseExponent, material.edgeResponse, targetSize,
      renderScale, containerPixelSize, inverseSourceScale, sourceUvLimit,
      accumulated);
  AccumulateAoSssFootprint(depthTexture, aoTexture, sssTexture, linearSampler,
      pixel + int2(-int(radius), 0), 0.125, centerDepth, threshold,
      inverseThreshold, responseExponent, material.edgeResponse, targetSize,
      renderScale, containerPixelSize, inverseSourceScale, sourceUvLimit,
      accumulated);
  AccumulateAoSssFootprint(depthTexture, aoTexture, sssTexture, linearSampler,
      pixel, 0.5, centerDepth, threshold, inverseThreshold, responseExponent,
      material.edgeResponse, targetSize, renderScale, containerPixelSize,
      inverseSourceScale, sourceUvLimit, accumulated);
  AccumulateAoSssFootprint(depthTexture, aoTexture, sssTexture, linearSampler,
      pixel + int2(int(radius), 0), 0.125, centerDepth, threshold,
      inverseThreshold, responseExponent, material.edgeResponse, targetSize,
      renderScale, containerPixelSize, inverseSourceScale, sourceUvLimit,
      accumulated);
  AccumulateAoSssFootprint(depthTexture, aoTexture, sssTexture, linearSampler,
      pixel + int2(0, int(radius)), 0.125, centerDepth, threshold,
      inverseThreshold, responseExponent, material.edgeResponse, targetSize,
      renderScale, containerPixelSize, inverseSourceScale, sourceUvLimit,
      accumulated);

  bool hasCoherent = 0.0 < accumulated.coherentWeight;
  float fallbackAo = material.edgeResponse * 0.0399999991
      < accumulated.fallbackWeight
      ? accumulated.fallbackAo / accumulated.fallbackWeight : 1.0;
  result.ao = hasCoherent
      ? accumulated.coherentAo / accumulated.coherentWeight : fallbackAo;
  float4 fallbackSss = 0.0 < accumulated.fallbackWeight
      ? accumulated.fallbackSss / accumulated.fallbackWeight : 0.0;
  result.sss = hasCoherent
      ? accumulated.coherentSss / accumulated.coherentWeight : fallbackSss;
  return result;
}
