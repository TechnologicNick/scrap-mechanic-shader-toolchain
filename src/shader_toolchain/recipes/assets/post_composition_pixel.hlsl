#include "include/post_composition_projection_abi.hlsl"
#include "include/post_composition_perframe_abi.hlsl"

#if defined(PS_REFLECTION_SINGLE)
SamplerState LinearMirrorMirror : register(s11);
#endif

Texture2D<float4> diffuseTexture : register(t0);
#if !defined(PS_REFLECTION_OFF)
Texture2D<float2> normalTexture : register(t1);
#endif
Texture2D<float4> materialTexture : register(t2);
Texture2D<float> depthTexture : register(t3);
Texture2D<float3> directLightTexture : register(t4);
#if defined(PS_REFLECTION_MULTI)
Texture2D<float3> indirectLightTexture : register(t5);
#elif defined(PS_REFLECTION_SINGLE)
Texture2DArray<float4> reflectionTexture : register(t7);
#endif
#if defined(PS_CASCADE)
Texture2D<float2> cascadeAoTexture : register(t10);
#endif

struct CompositionInput
{
    float4 position : SV_Position0;
    float2 uv : UNSCALED_UV0;
};

struct CompositionOutput
{
    float3 color : SV_Target0;
    float depthHistory : SV_Target1;
};

float3 DecodeOctahedralNormal(float2 encoded)
{
    encoded = encoded * 2.0 - 1.0;
    float3 normal;
    normal.z = 1.0 - abs(encoded.x) - abs(encoded.y);
    float fold = saturate(-normal.z);
    normal.xy = encoded + (encoded >= 0.0 ? -fold : fold);
    return normal * rsqrt(dot(normal, normal));
}

float2 EncodeReflectionOctahedron(float3 direction)
{
    direction.xy /= max(9.99999975e-5,
        abs(direction.x) + abs(direction.y) + abs(direction.z));
    float2 folded = 1.0 - abs(direction.yx);
    folded = direction.xy < 0.0 ? -folded : folded;
    float2 octahedral = direction.z <= 0.0 ? folded : direction.xy;
    octahedral += float2(-2.0, 2.0);
    if (max(abs(octahedral.x), abs(octahedral.y)) >= 1.0)
        octahedral = -octahedral;
    return octahedral * 0.5 + 0.5;
}

float3 ReconstructViewPosition(float2 uv, float depth)
{
    float2 clip = uv * float2(1.0, -1.0) + float2(0.0, 1.0);
    clip = clip * 2.0 - 1.0;
#if defined(ORTHO)
    return float3(cb_vNearFarViewCorner.zw * clip + cb_vViewTranslate, -depth);
#else
    return float3(cb_vNearFarViewCorner.zw * clip * depth, -depth);
#endif
}

float ViewPositionToWorldHeight(float3 viewPosition)
{
    float height = viewToWorld._m21 * viewPosition.y;
    height = viewToWorld._m20 * viewPosition.x + height;
    height = viewToWorld._m22 * viewPosition.z + height;
    return viewToWorld._m23 + height;
}

struct FogState
{
    float3 color;
    float amount;
};

FogState EvaluateFog(float distance, float worldHeight)
{
    float vertical = saturate(cb_fogs[0].cb_fVerticalFogInvRange
        * (worldHeight - cb_fogs[0].cb_fVerticalFogStart));
    vertical = 1.0 - vertical;
    vertical = 1.0 - exp2(log2(vertical)
        * max(0.00999999978, cb_fogs[0].cb_fVerticalFogFalloff));
    float4 verticalColor = cb_fogs[0].cb_vVerticalFogStartColor
        + vertical * (cb_fogs[0].cb_vVerticalFogEndColor
                    - cb_fogs[0].cb_vVerticalFogStartColor);
    float verticalAmount = 1.0
        - saturate(cb_fogs[0].cb_fVerticalFogInvFade * distance);
    verticalAmount = verticalColor.w
        * (1.0 - verticalAmount * verticalAmount);

    float distanceFog = saturate(cb_fogs[0].cb_fFogInvRange
        * (distance - cb_fogs[0].cb_fFogStart));
    distanceFog = 1.0 - distanceFog;
    distanceFog = 1.0 - exp2(log2(distanceFog)
        * max(9.99999975e-5, cb_fogs[0].cb_fFogFalloff));
    float4 distanceColor = cb_fogs[0].cb_vFogStartColor
        + distanceFog * (cb_fogs[0].cb_vFogEndColor
                       - cb_fogs[0].cb_vFogStartColor);
    float distanceAmount = distanceColor.w
        * saturate(cb_fogs[0].cb_fFogInvFade * distance);

    FogState fog;
    fog.amount = verticalAmount
        + distanceFog * (distanceAmount - verticalAmount);
    fog.color = distanceColor.xyz
        + verticalAmount * (verticalColor.xyz - distanceColor.xyz);
    return fog;
}

float CascadeOcclusion(uint2 pixel, uint materialFlags)
{
#if defined(PS_CASCADE)
    float2 cascade = cascadeAoTexture.Load(int3(pixel, 0));
    float farAo = min(1.0, max(0.300000012, cascade.y));
    float materialScale = (materialFlags == 1 || materialFlags == 2)
        ? 1.25 : 1.0;
    return saturate(cascade.x * (1.0 - farAo * materialScale)
        + farAo * materialScale);
#else
    return 1.0;
#endif
}

float3 EvaluateReflection(uint2 pixel, float3 viewPosition,
                          float4 material, float diffuseAlpha)
{
#if defined(PS_REFLECTION_OFF)
    return material.x * (1.0 - diffuseAlpha) * 0.125;
#else
    float3 normal = DecodeOctahedralNormal(
        normalTexture.Load(int3(pixel, 0)));
#if defined(PS_REFLECTION_MULTI)
    if (material.w >= 0.941176474)
        return 0.0;
    float3 reflection = indirectLightTexture.Load(int3(pixel, 0));
#if defined(PS_CASCADE)
    float daylightFloor = (1.0 - cb_fTodFactor) * 0.25 + 0.75;
    float cascade = cascadeAoTexture.Load(int3(pixel, 0)).y;
    reflection *= saturate(cascade * (1.0 - daylightFloor) + daylightFloor);
#endif
    float upward = normal.z * 0.5 + 0.5;
    upward *= upward;
    upward *= upward;
    upward *= upward;
    return reflection * (upward * 0.5 + 0.75) * (1.0 - diffuseAlpha);
#else
    float3 viewDirection = -viewPosition
        * rsqrt(dot(viewPosition, viewPosition));
    float3 reflectedView = -viewDirection
        - normal * (2.0 * dot(-viewDirection, normal));
    float3 reflectedWorld = viewToWorld._m01_m11_m21 * reflectedView.y;
    reflectedWorld = viewToWorld._m00_m10_m20
        * reflectedView.x + reflectedWorld;
    reflectedWorld = viewToWorld._m02_m12_m22
        * reflectedView.z + reflectedWorld;
    float2 reflectionUv = EncodeReflectionOctahedron(reflectedWorld);
    float lod = 5.0 * sqrt(max(0.00999999978, 1.0 - material.y));
    float3 reflection = reflectionTexture.SampleLevel(
        LinearMirrorMirror, float3(reflectionUv, 0.0), lod).xyz * material.x;
#if defined(PS_CASCADE)
    float daylightFloor = (1.0 - cb_fTodFactor) * 0.25 + 0.75;
    float cascade = cascadeAoTexture.Load(int3(pixel, 0)).y;
    reflection *= saturate(cascade * (1.0 - daylightFloor) + daylightFloor);
#endif
    return reflection * (1.0 - diffuseAlpha);
#endif
#endif
}

CompositionOutput mainPS(CompositionInput input)
{
    uint2 pixel = (uint2)(input.uv * float2(cb_vuViewportSize));
    float4 material = materialTexture.Load(int3(pixel, 0));
    float diffuseAlpha = diffuseTexture.Load(int3(pixel, 0)).w;
    float3 directLight = directLightTexture.Load(int3(pixel, 0));
    float depth = depthTexture.Load(int3(pixel, 0));
    float3 viewPosition = ReconstructViewPosition(input.uv, depth);
    float distance = sqrt(dot(viewPosition, viewPosition));
    float3 litColor = directLight
        + EvaluateReflection(pixel, viewPosition, material, diffuseAlpha);

    uint materialFlags = ((uint)(material.w * 255.0 + 0.5)) & 7;
#if defined(PS_CASCADE)
    float ao = CascadeOcclusion(pixel, materialFlags);
    if (materialFlags != 1)
        litColor *= ao;
#endif

    FogState fog = EvaluateFog(distance,
        ViewPositionToWorldHeight(viewPosition));
    float luminancePeak = max(abs(litColor.x),
        max(abs(litColor.y), abs(litColor.z)));
    float distanceExposure = 1.0 - min(1.0, distance * 0.00999999978);
    distanceExposure *= diffuseAlpha * 0.349999994;
    distanceExposure = 1.0 - distanceExposure * luminancePeak;
    float fogBlend = fog.amount * distanceExposure;

    CompositionOutput output;
    output.color = litColor + fogBlend * (fog.color - litColor);
    output.depthHistory = min(0.5, diffuseAlpha * 0.5);
    return output;
}
