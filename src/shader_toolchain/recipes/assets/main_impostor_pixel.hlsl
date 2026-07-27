#if defined(DEPTH)
SamplerState PointClampClamp_s : register(s1);
Texture2DArray<float4> taNormalMaterial : register(t1);

void mainPS(
    float4 position : SV_Position0,
    float4 atlasUv : TEXCOORD0,
    nointerpolation float atlasLayer : TEXCOORD1)
{
    float2 coverage = taNormalMaterial.SampleLevel(
        PointClampClamp_s, float3(atlasUv.xy, atlasLayer), 0.0).xy;
    if (coverage.x + coverage.y < 0.5)
        discard;
}
#else
SamplerState PointWrapWrap_s : register(s0);
SamplerState LinearClampClamp_s : register(s6);
Texture2DArray<float4> taDiffuse : register(t0);
Texture2DArray<float4> taNormalMaterial : register(t1);
Texture2D<float4> tDitherNoise : register(t14);

struct ImpostorGBuffer
{
    float4 color : SV_Target0;
    float2 normal : SV_Target1;
    float4 material : SV_Target2;
};

ImpostorGBuffer mainPS(
    float4 position : SV_Position0,
    float4 atlasUv : TEXCOORD0,
    nointerpolation float atlasLayer : TEXCOORD1,
    nointerpolation float facingSlice : TEXCOORD3,
    nointerpolation uint packedData : TEXCOORD6,
    linear noperspective centroid float4 screenUv : TEXCOORD2,
    nointerpolation float4 blendSlices : TEXCOORD4,
    nointerpolation float3 blendWeights : TEXCOORD5)
{
    float dither = tDitherNoise.SampleLevel(PointWrapWrap_s, screenUv.xy, 0.0).x;
    if ((float)(packedData & 255u) * (1.0 / 255.0) < dither)
        discard;

    float3 thresholds = dither * 0.2 + atlasUv.xyx;
    bool3 chooseNext = blendWeights < thresholds;
    float selectedSlice = chooseNext.x ? blendSlices.x : blendSlices.y;
    selectedSlice = chooseNext.y ? selectedSlice : blendSlices.z;
    if (selectedSlice == blendSlices.z)
        selectedSlice = chooseNext.z ? selectedSlice : blendSlices.w;

    float2 tiledUv = atlasUv.xy * (1.0 / 6.0);
    float scaledSlice = selectedSlice * (1.0 / 6.0);
    float sliceRow = floor(scaledSlice);
    float2 sampleUv = float2(frac(scaledSlice) + tiledUv.x,
                             sliceRow * (1.0 / 6.0) + tiledUv.y);
    float3 sampleCoordinate = float3(sampleUv, atlasLayer);
    float4 normalMaterial = taNormalMaterial.SampleLevel(
        LinearClampClamp_s, sampleCoordinate, 0.0);
    if (normalMaterial.x + normalMaterial.y < 0.5)
        discard;

    float3 packedColor = float3(
        (packedData >> 24u) & 255u,
        (packedData >> 16u) & 255u,
        (packedData >> 8u) & 255u) * (1.0 / 255.0);

    float sineAngle;
    float cosineAngle;
    sincos(facingSlice, sineAngle, cosineAngle);
    float2 encodedNormal = normalMaterial.xy * 2.0 - 1.0;
    float foldedZ = 1.0 - abs(encodedNormal.x);
    foldedZ -= abs(encodedNormal.y);
    float correction = saturate(-foldedZ);
    encodedNormal += (encodedNormal >= 0.0) ? -correction : correction;
    float3 normal = normalize(float3(encodedNormal, foldedZ));
    float2 rotated;
    rotated.x = dot(float2(cosineAngle, -sineAngle), normal.xy);
    rotated.y = dot(float2(sineAngle, cosineAngle), normal.xy);

    float4 diffuse = taDiffuse.SampleLevel(
        LinearClampClamp_s, sampleCoordinate, 0.0);
    ImpostorGBuffer output;
    precise float3 colorDifference = diffuse.rgb - packedColor;
    output.color.rgb = mad(diffuse.a, colorDifference, packedColor);
    output.color.a = 0.0;

    float3 octahedralAxes = float3(normal.z, rotated.x, rotated.y);
    float normalization = abs(rotated.x) + abs(rotated.y);
    normalization += abs(normal.z);
    float3 octahedral = octahedralAxes / normalization;
    float2 folded = (1.0 - abs(octahedral.zy))
        * ((octahedral.yz >= 0.0) ? 1.0 : -1.0);
    float2 octahedralUv = octahedral.x >= 0.0 ? octahedral.yz : folded;
    output.normal = octahedralUv * 0.5 + 0.5;
    output.material = float4(normalMaterial.zw, 0.0, 0.0);
    return output;
}
#endif
