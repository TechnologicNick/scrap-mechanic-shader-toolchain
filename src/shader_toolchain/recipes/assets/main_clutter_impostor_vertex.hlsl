#include "include/post_fxaa_abi.hlsl"
#include "include/clutter_impostor_abi.hlsl"

uint HashInstance(uint value)
{
    value = value * 0x2c9277b5u + 0xac564b05u;
    value ^= value >> ((value >> 28) + 4);
    value *= 0x108ef2d9u;
    value ^= value >> 22;
    return value >> 16;
}

float SimplexNoise(float2 position)
{
    const float2 skew = float2(0.366025418, 0.366025418);
    const float2 unskew = float2(0.211324871, 0.211324871);
    float2 cell = floor(1.5 * position + dot(1.5 * position, skew));
    float2 wrappedCell = cell - floor(cell / 289.0) * 289.0;
    float2 local = 1.5 * position - cell + dot(cell, unskew);
    float2 corner = local.y < local.x ? float2(1.0, 0.0) : float2(0.0, 1.0);

    float3 permutationY = wrappedCell.y + float3(0.0, corner.y, 1.0);
    permutationY = frac((permutationY * permutationY * 34.0 + permutationY) / 289.0) * 289.0;
    float3 permutation = wrappedCell.x + permutationY + float3(0.0, corner.x, 1.0);
    permutation = frac((permutation * permutation * 34.0 + permutation) / 289.0) * 289.0;

    float3 gradient = frac(permutation / 41.0) * 2.0 - 1.0;
    float3 gradientCell = floor(gradient + 0.5);
    float3 gradientX = gradient - gradientCell;
    float3 gradientY = abs(gradient) - 0.5;
    float3 normalization = 1.79284286 - 0.853734732
        * (gradientX * gradientX + gradientY * gradientY);

    float4 otherCorners = local.xyxy
        + float4(0.211324871, 0.211324871, -0.577350259, -0.577350259);
    otherCorners.xy -= corner;
    float3 attenuation = max(0.0, 0.5 - float3(
        dot(local, local),
        dot(otherCorners.xy, otherCorners.xy),
        dot(otherCorners.zw, otherCorners.zw)));
    attenuation *= attenuation;
    attenuation *= attenuation;

    float3 cornerGradient;
    cornerGradient.x = dot(float2(gradientX.x, gradientY.x), local);
    cornerGradient.y = dot(float2(gradientX.y, gradientY.y), otherCorners.xy);
    cornerGradient.z = dot(float2(gradientX.z, gradientY.z), otherCorners.zw);
    return dot(attenuation * normalization, cornerGradient);
}

float3 DecodePackedNormal(float2 packedNormal)
{
    float2 encoded = packedNormal * 2.0 - 1.0;
    float z = 1.0 - abs(encoded.x) - abs(encoded.y);
    float fold = saturate(-z);
    encoded += float2(encoded.x >= 0.0 ? -fold : fold,
                      encoded.y >= 0.0 ? -fold : fold);
    return normalize(float3(encoded, z));
}

void mainVS(
    float2 worldPositionXY : WORLD_POSITION_XY0,
    float4 packedNormalPositionZ : WORLD_NORMAL_POSITION_Z0,
    uint colorAndSlot : COLOR_INDEX0,
    uint vertexId : SV_VertexID0,
    out float4 position : SV_Position0,
    out float depthFade : TEXCOORD0,
    out float3 viewNormal : TEXCOORD1,
    out float2 texcoord : TEXCOORD2,
    out float3 tint : TEXCOORD3,
    out uint4 slice : TEXCOORD4)
{
    static const float4 quad[4] =
    {
        float4(-1.0, 2.0, 0.0, 1.0),
        float4(-1.0, 0.0, 0.0, 0.0),
        float4( 1.0, 2.0, 1.0, 1.0),
        float4( 1.0, 0.0, 1.0, 0.0),
    };

    uint slot = colorAndSlot & 255u;
    float randomScale = 3.05180438e-05 * float(HashInstance(uint(packedNormalPositionZ.w)));
    float scaleVariance = vecClutterSlots[slot].fScaleVariance;
    float scale = (1.0 - scaleVariance) + scaleVariance * randomScale;
    float2 corner = quad[vertexId].xy * vecClutterSlots[slot].vSize * scale;

    float3 worldPosition = float3(worldPositionXY, packedNormalPositionZ.x);
    float3 viewDirection = normalize(viewToWorld._m13_m23_m03 - worldPosition.yzx);
    float3 billboardX = normalize(float3(viewDirection.x, -viewDirection.z, 0.0));
    float3 billboardY = normalize(cross(billboardX, viewDirection));
    float3 billboardOffset = billboardX * corner.x + billboardY * corner.y;
    float3 expandedPosition = worldPosition + billboardOffset;

    float noise = SimplexNoise(worldPositionXY);
    float denominator = 78.0 * noise + 0.600000024;
    float tintNoise = 10.3999996 * noise + 0.959999979;

    float3 worldNormal = DecodePackedNormal(packedNormalPositionZ.yz);
    float3 packedTint = float3(
        (colorAndSlot >> 24) & 255u,
        (colorAndSlot >> 16) & 255u,
        (colorAndSlot >> 8) & 255u) * 0.00392156886;

    position = mul(worldToViewProjection, float4(expandedPosition, 1.0));
    depthFade = abs(billboardOffset.z) / denominator;
    viewNormal = mul((float3x3)worldToView, worldNormal);
    texcoord = quad[vertexId].zw;
    tint = packedTint * tintNoise;
    slice.w = slot;
}
