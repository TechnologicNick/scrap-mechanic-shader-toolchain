static const float CASCADE_PACK_SCALE = 65535.0;
static const float2 CASCADE_PERIMETER_OFFSETS[8] = {
  float2(-1.0, -1.0), float2( 0.0, -1.0),
  float2( 1.0, -1.0), float2(-1.0,  0.0),
  float2( 1.0,  0.0), float2(-1.0,  1.0),
  float2( 0.0,  1.0), float2( 1.0,  1.0)
};
struct CascadeQuad {
  float3 sample0, sample1, sample2, sample3;
};
struct CascadeContribution {
  float3 indirect;
  float weight;
};
struct CascadeFilterContext {
  float3 centerPosition;
  float depthScale;
  float3 planeScale;
  float rejectionDistance, inverseFalloffDistance;
};
struct CascadeFilterGrid {
  float2 centerUv, tapSpacing, renderScale, uvLimit, farViewCorner;
};
struct CascadeAccumulator {
  float3 indirect;
  float weight;
};
float GatherMinimumCascadeDepth(
    Texture2D<float2> cascadeTexture, SamplerState pointSampler,
    float2 uv, float depthScale) {
  float4 depths = cascadeTexture.GatherGreen(pointSampler, uv);
  depths = depths * depths;
  depths = depths * depthScale
         + float4(0.100000001, 0.100000001,
                  0.100000001, 0.100000001);
  float2 pairMinimum = min(depths.xz, depths.yw);
  return min(pairMinimum.x, pairMinimum.y);
}
float3 ReconstructCascadeViewPosition(float2 uv, float depth, float2 farViewCorner) {
  float2 viewRay = uv * float2(1.0, -1.0) + float2(0.0, 1.0);
  viewRay = viewRay * float2(2.0, 2.0) + float2(-1.0, -1.0);
  viewRay = farViewCorner * viewRay;
  return float3(viewRay * depth, -depth);
}
float3 DecodeCascadeNormal(float2 encoded) {
  encoded = encoded * float2(2.0, 2.0) + float2(-1.0, -1.0);
  float z = 1.0 + -abs(encoded.x) + -abs(encoded.y);
  float correction = saturate(-z);
  float2 signs = encoded >= float2(0.0, 0.0);
  signs = signs ? -correction.xx : correction.xx;
  float3 normal = float3(encoded + signs, z);
  return normal * rsqrt(dot(normal, normal));
}
// The red cascade channel is a normalized 16-bit word.  Its upper six bits
// contain a fourth-root luminance and the remaining 5:5 bits contain signed
// square-root YCoCg chroma.  Keeping the multiply sequence explicit preserves
// the rounding behavior of the recovered Shader Model 5 programs.
float DecodeCascadeLuminance(uint packedIndirect) {
  float luminance = float((packedIndirect >> 10) & 63) * 0.0158730168;
  luminance = luminance * luminance;
  luminance = luminance * luminance;
  return 64.0 * luminance;
}
float DecodeCascadeChroma(uint encodedChroma) {
  float chroma = float(encodedChroma & 31) * 0.0666666701 - 1.0;
  return chroma * abs(chroma);
}
float3 DecodeCascadeIndirect(uint packedIndirect) {
  // SM_COVERAGE_CANARY: packed_decode
  float luminance = DecodeCascadeLuminance(packedIndirect);
  float chromaGreen = DecodeCascadeChroma(packedIndirect);
  float chromaOrange = DecodeCascadeChroma(packedIndirect >> 5);
  float greenFactor = chromaGreen * 2.0 + 1.0;
  float redFactor = -chromaGreen * 2.0
                  + (chromaOrange * 2.0 + 1.0);
  float blueFactor = 1.0
                   + (-chromaGreen * 2.0
                   + -(chromaOrange + chromaOrange));
  return max(float3(0.0, 0.0, 0.0),
             float3(redFactor, greenFactor, blueFactor) * luminance);
}
CascadeQuad DecodeCascadeQuad(uint4 packedIndirect) {
  CascadeQuad quad;
  quad.sample0 = DecodeCascadeIndirect(packedIndirect.x);
  quad.sample1 = DecodeCascadeIndirect(packedIndirect.y);
  quad.sample2 = DecodeCascadeIndirect(packedIndirect.z);
  quad.sample3 = DecodeCascadeIndirect(packedIndirect.w);
  return quad;
}
float3 GatherCascadeCenterIndirect(
    Texture2D<float2> cascadeTexture, SamplerState linearSampler, float2 uv) {
  float4 encoded = cascadeTexture.Gather(linearSampler, uv);
  encoded = encoded.wzyx * float4(
      CASCADE_PACK_SCALE, CASCADE_PACK_SCALE,
      CASCADE_PACK_SCALE, CASCADE_PACK_SCALE) + float4(0.5, 0.5, 0.5, 0.5);
  CascadeQuad quad = DecodeCascadeQuad((uint4)encoded);
  float3 indirect = quad.sample0 + quad.sample1;
  indirect = indirect + quad.sample2;
  return indirect + quad.sample3;
}
CascadeContribution ResolveCascadeContribution(uint4 packedIndirect, float4 rawWeights) {
  CascadeQuad quad = DecodeCascadeQuad(packedIndirect);
  float4 weights = float4(0.25, 0.25, 0.25, 0.25) * rawWeights;
  CascadeContribution result;
  // SM_COVERAGE_CANARY: cascade_contribution
  result.weight = weights.x + weights.y;
  result.weight = rawWeights.z * 0.25 + result.weight;
  result.weight = rawWeights.w * 0.25 + result.weight;
  // Preserve the recovered lane and accumulation order exactly.
  result.indirect = weights.yyy * quad.sample1;
  result.indirect = quad.sample0 * weights.xxx + result.indirect;
  result.indirect = quad.sample2 * weights.zzz + result.indirect;
  result.indirect = quad.sample3 * weights.www + result.indirect;
  return result;
}
void AccumulateCascadeContribution(
    inout float accumulatedWeight, inout float3 accumulatedIndirect,
    CascadeContribution contribution) {
  // SM_COVERAGE_CANARY: cascade_accumulate
  accumulatedWeight = accumulatedWeight + contribution.weight;
  accumulatedIndirect = contribution.indirect + accumulatedIndirect;
}
float EncodeCascadeIndirect(float3 indirect) {
  // SM_COVERAGE_CANARY: packed_encode
  float chromaOrange = indirect.x + -indirect.z;
  float redBlueAverage = chromaOrange * 0.5 + indirect.z;
  float chromaGreen = indirect.y + -redBlueAverage;
  float luminance = chromaGreen * 0.5 + redBlueAverage;
  float encodedLuminance = saturate(0.015625 * luminance);
  encodedLuminance = sqrt(encodedLuminance);
  encodedLuminance = sqrt(encodedLuminance);
  encodedLuminance = encodedLuminance * 63.0 + 0.5;
  float inverseLuminance = rcp(max(0.00999999978, luminance));
  float2 chroma = float2(chromaOrange, chromaGreen) * inverseLuminance;
  float2 inverseMagnitude = rsqrt(max(
      float2(9.99999975e-05, 9.99999975e-05),
      float2(4.0, 4.0) * abs(chroma)));
  chroma = inverseMagnitude * chroma;
  chroma = min(float2(30.0, 30.0), max(
      float2(0.0, 0.0), chroma * float2(15.0, 15.0)
                            + float2(15.5, 15.5)));
  uint3 encoded = (uint3)float3(chroma.x, encodedLuminance, chroma.y);
  uint packedIndirect = (encoded.x << 5) + encoded.y * 1024 + encoded.z;
  return float(packedIndirect) * 1.52590219e-05;
}
float ComputeCascadeRangeScale(float3 indirect, float depth) {
  float maximumIndirect = max(indirect.x, indirect.y);
  maximumIndirect = max(maximumIndirect, indirect.z);
  float compressedScale = saturate(0.0833333358 * depth);
  compressedScale = compressedScale * 0.189999998 + 0.800000012;
  return maximumIndirect > 1.0 ? compressedScale : 1.0;
}
float4 ComputeCascadeBilateralWeights(
    float4 deltaX, float4 deltaY, float4 deltaZ,
    float planeScaleX, float planeScaleY, float planeScaleZ,
    float rejectionDistance, float inverseFalloffDistance) {
  // SM_COVERAGE_CANARY: bilateral_weights
  float4 sampleDistance = deltaY * deltaY;
  sampleDistance = deltaX * deltaX + sampleDistance;
  sampleDistance = deltaZ * deltaZ + sampleDistance;
  sampleDistance = sqrt(sampleDistance);
  float4 accepted = rejectionDistance >= sampleDistance;
  accepted = accepted ? float4(1.0, 1.0, 1.0, 1.0) : 0.0;
  float4 inverseDistance = rcp(max(
      float4(0.00100000005, 0.00100000005,
             0.00100000005, 0.00100000005), sampleDistance));
  deltaX = inverseDistance * deltaX;
  deltaY = inverseDistance * deltaY;
  deltaY = deltaY * planeScaleY;
  deltaX = deltaX * planeScaleX + deltaY;
  deltaZ = inverseDistance * deltaZ;
  float4 planeWeight = saturate(deltaZ * planeScaleZ + deltaX);
  planeWeight = float4(1.0, 1.0, 1.0, 1.0) + -planeWeight;
  float4 distanceWeight = sampleDistance * inverseFalloffDistance;
  distanceWeight = min(float4(1.0, 1.0, 1.0, 1.0), distanceWeight);
  distanceWeight = float4(1.0, 1.0, 1.0, 1.0) + -distanceWeight;
  planeWeight = -planeWeight * planeWeight
              + float4(1.0, 1.0, 1.0, 1.0);
  distanceWeight = distanceWeight * distanceWeight;
  return distanceWeight * planeWeight * accepted;
}
CascadeContribution GatherCascadeNeighborhood(
    Texture2D<float2> cascadeTexture, SamplerState pointSampler,
    float2 uv, float4 viewRayX, float4 viewRayY,
    CascadeFilterContext context) {
  float4 encodedIndirect = cascadeTexture.Gather(pointSampler, uv);
  float4 depth = cascadeTexture.GatherGreen(pointSampler, uv);
  depth = depth * depth;
  depth = depth * context.depthScale
        + float4(0.100000001, 0.100000001,
                 0.100000001, 0.100000001);
  float4 deltaX = viewRayX * depth + -context.centerPosition.xxxx;
  float4 deltaY = viewRayY * depth + -context.centerPosition.yyyy;
  float4 deltaZ = -depth + -context.centerPosition.zzzz;
  float4 weights = ComputeCascadeBilateralWeights(
      deltaX, deltaY, deltaZ,
      context.planeScale.x, context.planeScale.y, context.planeScale.z,
      context.rejectionDistance, context.inverseFalloffDistance);
  encodedIndirect = encodedIndirect * float4(
      CASCADE_PACK_SCALE, CASCADE_PACK_SCALE,
      CASCADE_PACK_SCALE, CASCADE_PACK_SCALE) + float4(0.5, 0.5, 0.5, 0.5);
  return ResolveCascadeContribution((uint4)encodedIndirect, weights);
}
CascadeAccumulator FilterCascadePerimeter(
    Texture2D<float2> cascadeTexture, SamplerState pointSampler,
    CascadeFilterGrid grid, CascadeFilterContext context,
    float initialWeight, float3 initialIndirect) {
  CascadeAccumulator result;
  result.weight = initialWeight;
  result.indirect = initialIndirect;
  // SM_COVERAGE_CANARY: cascade_perimeter
  [unroll]
  for (uint tapIndex = 0; tapIndex < 8; ++tapIndex)
  {
    float2 unscaledUv = grid.tapSpacing * CASCADE_PERIMETER_OFFSETS[tapIndex]
                      + grid.centerUv;
    float2 sampleUv = min(grid.uvLimit, grid.renderScale * unscaledUv);
    float2 viewRay = unscaledUv * float2(1.0, -1.0) + float2(0.0, 1.0);
    viewRay = viewRay * float2(2.0, 2.0) + float2(-1.0, -1.0);
    viewRay = grid.farViewCorner * viewRay;
    CascadeContribution contribution = GatherCascadeNeighborhood(
        cascadeTexture, pointSampler, sampleUv,
        viewRay.xxxx, viewRay.yyyy, context);
    AccumulateCascadeContribution(result.weight, result.indirect, contribution);
  }
  return result;
}
