#include "include/post_composition_projection_abi.hlsl"
#include "include/post_composition_perframe_abi.hlsl"

#if defined(PS_UNDER_WATER_FOG)
SamplerState PointWrapWrap : register(s0);
SamplerState LinearWrapWrap : register(s3);
#endif
#if defined(PS_REFLECTION_SINGLE)
SamplerState LinearMirrorMirror : register(s11);
#endif

Texture2D<float4> diffuseTexture : register(t0);
#if !defined(PS_REFLECTION_OFF) || defined(PS_UNDER_WATER_FOG)
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
#if defined(PS_UNDER_WATER_FOG)
Texture2D<float2> waterNormalTexture : register(t8);
Texture2D<float> waterHeightTexture : register(t9);
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

FogState EvaluateFog(float distance, float worldHeight, uint fogIndex)
{
    float distanceFog = saturate(cb_fogs[fogIndex].cb_fFogInvRange
        * (distance - cb_fogs[fogIndex].cb_fFogStart));
    distanceFog = 1.0 - distanceFog;
    distanceFog = 1.0 - exp2(log2(distanceFog)
        * max(9.99999975e-5, cb_fogs[fogIndex].cb_fFogFalloff));
    float4 distanceColor = cb_fogs[fogIndex].cb_vFogStartColor
        + distanceFog * (cb_fogs[fogIndex].cb_vFogEndColor
                       - cb_fogs[fogIndex].cb_vFogStartColor);
    float distanceAmount = distanceColor.w
        * saturate(cb_fogs[fogIndex].cb_fFogInvFade * distance);

    float vertical = saturate(cb_fogs[fogIndex].cb_fVerticalFogInvRange
        * (worldHeight - cb_fogs[fogIndex].cb_fVerticalFogStart));
    vertical = 1.0 - vertical;
    vertical = 1.0 - exp2(log2(vertical)
        * max(0.00999999978, cb_fogs[fogIndex].cb_fVerticalFogFalloff));
    float4 verticalColor = cb_fogs[fogIndex].cb_vVerticalFogStartColor
        + vertical * (cb_fogs[fogIndex].cb_vVerticalFogEndColor
                    - cb_fogs[fogIndex].cb_vVerticalFogStartColor);
    float inverseVerticalFade = 1.0
        - saturate(cb_fogs[fogIndex].cb_fVerticalFogInvFade * distance);
    float verticalAmount = verticalColor.w
        * (1.0 - inverseVerticalFade * inverseVerticalFade);

    FogState fog;
    fog.color = distanceColor.xyz
        + verticalAmount * (verticalColor.xyz - distanceColor.xyz);
    fog.amount = verticalAmount
        + distanceFog * (distanceAmount - verticalAmount);
    return fog;
}

#if defined(PS_UNDER_WATER_FOG)
float3 ViewPositionToWorld(float3 viewPosition)
{
    float3 world = viewToWorld._m01_m11_m21 * viewPosition.y;
    world = viewToWorld._m00_m10_m20 * viewPosition.x + world;
    world = viewToWorld._m02_m12_m22 * viewPosition.z + world;
    return viewToWorld._m03_m13_m23 + world;
}

float3 EvaluateWaterCaustics(uint2 pixel, float3 worldPosition,
                             float waterHeight, float3 directLight)
{
    float3 viewNormal = DecodeOctahedralNormal(
        normalTexture.Load(int3(pixel, 0)));
    float3 worldNormal = viewToWorld._m01_m11_m21 * viewNormal.y;
    worldNormal = viewToWorld._m00_m10_m20 * viewNormal.x + worldNormal;
    worldNormal = viewToWorld._m02_m12_m22 * viewNormal.z + worldNormal;
    worldNormal *= rsqrt(dot(worldNormal, worldNormal));

    float lightDistance = 0.0;
    if (cb_vDirectionalLightToWaterWorld.z > 1.1920929e-7)
        lightDistance = (waterHeight - worldPosition.z)
            / cb_vDirectionalLightToWaterWorld.z;
    float curvedDistance = min(0.25 * lightDistance * lightDistance,
        lightDistance);
    float2 waterUv = cb_vWaterScroll + worldPosition.xy
        + cb_vDirectionalLightToWaterWorld.xy * curvedDistance;

    float4 bands = saturate(float4(0.100000001, 0.0500000007,
        0.00499999989, 0.25) * lightDistance);
    float wholeBand = floor(lightDistance * 0.25);
    float3 bandWindow = float3(-2.0, 1.0, -1.0) + wholeBand;
    bandWindow.xz = 1.0 - saturate(bandWindow.xz * 0.00999999978);
    float firstScale = max(0.100000001,
        1.25 - bandWindow.x * wholeBand * 0.300000012);
    float secondScale = max(0.100000001,
        1.25 - bandWindow.y * bandWindow.z * 0.300000012);
    float mip = 2.0 * (1.0 - bands.x);
    waterUv /= cb_fWaterMapPatchSize;
    float2 firstNormal = waterNormalTexture.SampleLevel(
        LinearWrapWrap, waterUv * firstScale, mip);
    float2 secondNormal = waterNormalTexture.SampleLevel(
        LinearWrapWrap, waterUv * secondScale, mip);
    float blend = (lightDistance - wholeBand * 4.0) * 0.25;
    float2 waterNormal = firstNormal
        + blend * (secondNormal - firstNormal);
    waterNormal = waterNormal * 2.0 - 1.0;
    float shape = 1.0 - min(1.0, abs(dot(waterNormal, 1.0)));
    shape = exp2(log2(shape) * (2.0 - bands.y));
    shape *= (1.0 - bands.z)
        * (cb_fDirectionalLightIntensity * 0.0500000119 + 0.25);
    float facing = saturate(dot(worldNormal,
        -cb_vDirectionalLightDirectionWorld) * 0.600000024 + 0.400000006);
    return directLight * (shape * facing);
}
#endif

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
    float worldHeight = ViewPositionToWorldHeight(viewPosition);
    float3 litColor = directLight
        + EvaluateReflection(pixel, viewPosition, material, diffuseAlpha);

    uint materialFlags = ((uint)(material.w * 255.0 + 0.5)) & 7;
#if defined(PS_CASCADE)
    float ao = CascadeOcclusion(pixel, materialFlags);
    if (materialFlags != 1)
        litColor *= ao;
#endif

#if defined(PS_UNDER_WATER_FOG)
    float3 worldPosition = ViewPositionToWorld(viewPosition);
    float waterHeight = waterHeightTexture.SampleLevel(PointWrapWrap,
        worldPosition.xy / cb_fWaterMapPatchSize, 0.0)
        * cb_fWaterHeightScale + cb_fWaterSurface;
    bool belowWaterSurface = worldPosition.z < waterHeight;
    if (belowWaterSurface)
    {
        float causticScale = 1.0;
#if defined(PS_CASCADE)
        causticScale = max(0.300000012,
            cascadeAoTexture.Load(int3(pixel, 0)).y);
#endif
        litColor += causticScale * EvaluateWaterCaustics(
            pixel, worldPosition, waterHeight, directLight);
    }
    uint fogIndex = belowWaterSurface ? 1 : 0;
#else
    uint fogIndex = 0;
#endif
    FogState fog = EvaluateFog(distance, worldHeight, fogIndex);
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
