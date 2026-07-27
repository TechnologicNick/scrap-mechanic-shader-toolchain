static const float CASCADE_MIN_DEPTH = 0.100000001;
static const float CASCADE_FAR_DEPTH = 800.0;
static const float CASCADE_PACK_SCALE = 65535.0;

struct CascadeSample
{
  float3 indirect;
  float depth;
};

float DecodeCascadeDepth(float encodedDepth, float maximumDepth)
{
  float decodedDepth = encodedDepth * encodedDepth;
  return decodedDepth * (maximumDepth - CASCADE_MIN_DEPTH)
       + CASCADE_MIN_DEPTH;
}

float EncodeCascadeDepth(float depth, float maximumDepth)
{
  float normalizedDepth = saturate(
      (depth - CASCADE_MIN_DEPTH) / (maximumDepth - CASCADE_MIN_DEPTH));
  return sqrt(normalizedDepth);
}

// The red cascade channel is a normalized 16-bit word.  Its upper six bits
// contain a fourth-root luminance and the remaining 5:5 bits contain signed
// square-root YCoCg chroma.  Keeping the multiply sequence explicit preserves
// the rounding behavior of the recovered Shader Model 5 programs.
float DecodeCascadeLuminance(uint packedIndirect)
{
  float luminance = float((packedIndirect >> 10) & 63) * 0.0158730168;
  luminance = luminance * luminance;
  luminance = luminance * luminance;
  return 64.0 * luminance;
}

float DecodeCascadeChroma(uint encodedChroma)
{
  float chroma = float(encodedChroma & 31) * 0.0666666701 - 1.0;
  return chroma * abs(chroma);
}

float3 DecodeCascadeIndirect(uint packedIndirect)
{
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

float EncodeCascadeIndirect(float3 indirect)
{
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

uint CascadePackedWord(float encodedIndirect)
{
  return (uint)(encodedIndirect * CASCADE_PACK_SCALE + 0.5);
}

float4 ComputeCascadeBilateralWeights(
    float4 deltaX,
    float4 deltaY,
    float4 deltaZ,
    float planeScaleX,
    float planeScaleY,
    float planeScaleZ,
    float rejectionDistance,
    float inverseFalloffDistance)
{
  // SM_COVERAGE_CANARY: bilateral_weights
  float4 sampleDistance = deltaY * deltaY;
  sampleDistance = deltaX * deltaX + sampleDistance;
  sampleDistance = deltaZ * deltaZ + sampleDistance;
  sampleDistance = sqrt(sampleDistance);

  float4 accepted = rejectionDistance >= sampleDistance;
  accepted = accepted ? float4(1.0, 1.0, 1.0, 1.0) : 0.0;
  float4 inverseDistance = rcp(max(
      float4(0.00100000005, 0.00100000005,
             0.00100000005, 0.00100000005),
      sampleDistance));

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

float3 ReconstructCascadeViewPosition(
    float2 uv,
    float depth,
    float2 farViewCorner)
{
  float2 clipPosition = uv * float2(2.0, -2.0) + float2(-1.0, 1.0);
  float3 viewRay = float3(farViewCorner * clipPosition, -1.0);
  return viewRay * depth;
}
