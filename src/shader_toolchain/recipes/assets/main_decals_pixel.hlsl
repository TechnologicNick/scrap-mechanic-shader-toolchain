#include "include/post_fxaa_abi.hlsl"
#include "include/decals_abi.hlsl"

#if defined(PS_DIFFUSE_OUTPUT) || defined(PS_MATERIAL_OUTPUT) || defined(PS_NORMAL_OUTPUT)
SamplerState LinearClampClamp_s : register(s6);
#endif
Texture2D<float> tDepth : register(t0);
#if defined(PS_NORMAL_OUTPUT)
Texture2D<float2> tGbufferNormal : register(t1);
Texture2DArray<float2> tNormalAtlas : register(t3);
#endif
#if defined(PS_DIFFUSE_OUTPUT) || defined(PS_MATERIAL_OUTPUT)
Texture2DArray<float4> tDiffuseAtlas : register(t2);
#endif
#if defined(PS_SAMPLE_AGS) || defined(PS_MATERIAL_OUTPUT)
Texture2DArray<float3> tAgsAtlas : register(t4);
#endif

float DepthToViewDistance(float depth)
{
    return cb_xViewToProjection._m23
        / (cb_xViewToProjection._m22 + depth);
}

float2 ScreenToNdc(float2 uv)
{
    float2 orientedUv = mad(uv, float2(1.0, -1.0), float2(0.0, 1.0));
    return mad(orientedUv, 2.0, -1.0);
}

float3 ReconstructViewPosition(float2 uv, float viewDistance)
{
    float2 corner = cb_vNearFarViewCorner.zw * ScreenToNdc(uv);
#if defined(ORTHO)
    return float3(corner + cb_vViewTranslate, -viewDistance);
#else
    return float3(corner * viewDistance, -viewDistance);
#endif
}

float3 ViewToDecal(float3 viewPosition, uint decalIndex)
{
    float4 homogeneous = float4(viewPosition, 1.0);
    return float3(
        dot(cb_arrDecals[decalIndex].Row0Inv, homogeneous),
        dot(cb_arrDecals[decalIndex].Row1Inv, homogeneous),
        dot(cb_arrDecals[decalIndex].Row2Inv, homogeneous));
}

float2 AtlasUv(float2 localPosition, uint decalIndex)
{
    return mad(localPosition + 0.5,
               cb_arrDecals[decalIndex].vUvRegion.zw,
               cb_arrDecals[decalIndex].vUvRegion.xy);
}

float3 DecodeOctahedral(float2 encoded)
{
    float normalZ = 1.0 - abs(encoded.x);
    normalZ -= abs(encoded.y);
    float correction = saturate(-normalZ);
    float2 corrected = encoded
        + (encoded >= 0.0 ? -correction.xx : correction.xx);
    // The decal tangent frame carries axes as (z, x, y) until encoding.
    float3 axisNormal = float3(normalZ, corrected);
    return axisNormal * rsqrt(dot(axisNormal, axisNormal));
}

float2 EncodeOctahedral(float3 normal)
{
    normal *= rsqrt(dot(normal, normal));
    // Match the shipped reduction tree; changing this associative order is
    // enough to move the packed normal by several ULPs near diagonal edges.
    float l1Length = mad(abs(normal.z), 1.0, abs(normal.y));
    l1Length = abs(normal.x) + l1Length;
    normal /= l1Length;
    float2 folded = (1.0 - abs(normal.zy))
        * (normal.yz >= 0.0 ? 1.0 : -1.0);
    return (normal.x >= 0.0 ? normal.yz : folded) * 0.5 + 0.5;
}

float3 ApplyDecalNormal(
    float3 viewPosition, float2 atlasUv, float2 sampledNormal,
    float2 encodedBaseNormal)
{
    float3 baseNormal = DecodeOctahedral(encodedBaseNormal);
    float3 derivativePosition = -viewPosition.yzx;
    float3 positionDy = ddy_coarse(derivativePosition);
    float3 positionDx = ddx_coarse(derivativePosition.zxy);
    float3 tangentProduct = positionDy * baseNormal.yzx;
    float3 tangent = mad(positionDy.zxy, baseNormal.zxy, -tangentProduct);
    float3 bitangentProduct = positionDx * baseNormal.zxy;
    float3 bitangent = mad(baseNormal.yzx, positionDx.yzx, -bitangentProduct);
    float2 uvDy = ddy_coarse(atlasUv);
    float2 uvDx = ddx_coarse(atlasUv);
    float3 axisX = mad(tangent, uvDx.x, bitangent * uvDy.x);
    float3 axisY = mad(tangent, uvDx.y, bitangent * uvDy.y);
    float inverseScale = rsqrt(max(dot(axisX, axisX), dot(axisY, axisY)));
    axisX *= inverseScale;
    axisY *= inverseScale;
    axisY *= sampledNormal.y;
    float3 perturbation = mad(sampledNormal.x, axisX, axisY);
    float normalZ = sqrt(max(0.0, 1.0 - dot(sampledNormal, sampledNormal)));
    return mad(normalZ, baseNormal, perturbation);
}

// The same tangent-frame reconstruction with explicit intermediate products.
// FXC otherwise contracts the two derivative axes differently from the
// shipped program near degenerate frames.
float2 EncodeDecalNormal(
    float3 viewPosition, float2 atlasUv, float2 sampledNormal,
    float2 encodedBaseNormal)
{
    float3 baseNormal = DecodeOctahedral(encodedBaseNormal);
    float3 derivativePosition = -viewPosition.yzx;
    float3 positionDy = ddy_coarse(derivativePosition);
    float3 positionDx = ddx_coarse(derivativePosition.zxy);

    float3 tangentProduct = baseNormal.yzx * positionDy;
    float3 tangent = mad(positionDy.zxy, baseNormal.zxy, -tangentProduct);
    float3 bitangentProduct = baseNormal.zxy * positionDx;
    float3 bitangent = mad(baseNormal.yzx, positionDx.yzx, -bitangentProduct);

    float2 uvDy = ddy_coarse(atlasUv);
    float2 uvDx = ddx_coarse(atlasUv);
    precise float3 bitangentAlongX = uvDy.x * bitangent;
    precise float3 bitangentAlongY = uvDy.y * bitangent;
    float3 normalAxisY = mad(tangent, uvDx.y, bitangentAlongY);
    float3 normalAxisX = mad(tangent, uvDx.x, bitangentAlongX);

    float inverseScale = rsqrt(max(
        dot(normalAxisX, normalAxisX),
        dot(normalAxisY, normalAxisY)
    ));
    normalAxisY *= inverseScale;
    normalAxisX *= inverseScale;
    precise float3 weightedAxisY = sampledNormal.y * normalAxisY;
    float3 perturbation = mad(sampledNormal.x, normalAxisX, weightedAxisY);

    float normalZ = sqrt(max(0.0, 1.0 - dot(sampledNormal, sampledNormal)));
    float3 blendedNormal = mad(normalZ, baseNormal, perturbation);
    blendedNormal *= rsqrt(dot(blendedNormal, blendedNormal));

    float l1Length = abs(blendedNormal.z) + abs(blendedNormal.y);
    l1Length = abs(blendedNormal.x) + l1Length;
    blendedNormal /= l1Length;
    float2 folded = 1.0 - abs(blendedNormal.zy);
    float2 foldSign = blendedNormal.yz >= 0.0 ? 1.0 : -1.0;
    folded *= foldSign;
    float2 encoded = blendedNormal.x >= 0.0
        ? blendedNormal.yz : folded;
    return mad(encoded, 0.5, 0.5);
}

#if defined(PS_DIFFUSE_OUTPUT) || defined(PS_MATERIAL_OUTPUT) || defined(PS_NORMAL_OUTPUT)
struct DecalOutput
{
#if defined(PS_DIFFUSE_OUTPUT)
    float4 diffuse : SV_Target0;
#endif
#if defined(PS_NORMAL_OUTPUT)
    float2 normal : SV_Target1;
#endif
#if defined(PS_MATERIAL_OUTPUT)
    float4 material : SV_Target2;
#endif
};

DecalOutput mainPS(
    float4 position : SV_Position0,
    linear noperspective centroid float2 screenUv : TEXCOORD0,
    nointerpolation uint decalIndex : INDEX0)
{
    DecalOutput output = (DecalOutput)0;
    uint2 pixel = (uint2)(screenUv * (float2)cb_vuViewportSize);
    float viewDistance = DepthToViewDistance(tDepth.Load(int3(pixel, 0)));
    float3 viewPosition = ReconstructViewPosition(screenUv, viewDistance);
    float3 localPosition = ViewToDecal(viewPosition, decalIndex);
    if (any(0.5 - abs(localPosition) < 0.0))
        discard;

    float2 atlasUv = AtlasUv(localPosition.xy, decalIndex);
    float2 neighborScreenUv = screenUv + cb_vContainerPixelSize;
    float3 neighborViewPosition = ReconstructViewPosition(
        neighborScreenUv, viewDistance);
    float2 neighborLocal = ViewToDecal(neighborViewPosition, decalIndex).xy;
    float2 atlasDelta = (AtlasUv(neighborLocal, decalIndex) - atlasUv) * 2048.0;
    float mip = mad(0.5, log2(dot(atlasDelta, atlasDelta)), cb_fMipBias);
    uint4 textureAndColor = cb_arrDecals[decalIndex].vArrayIndicesColor;

#if defined(PS_DIFFUSE_OUTPUT) || defined(PS_MATERIAL_OUTPUT)
    float4 tint = float4(
        textureAndColor.w & 255,
        (textureAndColor.w >> 8) & 255,
        (textureAndColor.w >> 16) & 255,
        textureAndColor.w >> 24) * 0.00392156886;
    float4 diffuse = tint * tDiffuseAtlas.SampleLevel(
        LinearClampClamp_s, float3(atlasUv, textureAndColor.x), mip);
#endif
#if defined(PS_SAMPLE_AGS) || defined(PS_MATERIAL_OUTPUT)
    float3 ags = tAgsAtlas.SampleLevel(
        LinearClampClamp_s, float3(atlasUv, textureAndColor.z), mip);
#endif
#if defined(PS_DIFFUSE_OUTPUT)
    output.diffuse = diffuse;
    #if defined(PS_SAMPLE_AGS) || defined(PS_MATERIAL_OUTPUT)
    output.diffuse.rgb *= ags.x;
    #endif
#endif
#if defined(PS_MATERIAL_OUTPUT)
    output.material = float4(ags.z * ags.x, ags.y * ags.x, 0.0, diffuse.a);
#endif
#if defined(PS_NORMAL_OUTPUT)
    float2 sampledNormal = tNormalAtlas.SampleLevel(
        LinearClampClamp_s, float3(atlasUv, textureAndColor.y), mip)
        * 1.99215686 - 1.0;
    float2 baseNormal = tGbufferNormal.Load(int3(pixel, 0)) * 2.0 - 1.0;
    output.normal = EncodeDecalNormal(
        viewPosition, atlasUv, sampledNormal, baseNormal);
#endif
    return output;
}
#else
void mainPS(
    float4 position : SV_Position0,
    linear noperspective centroid float2 screenUv : TEXCOORD0,
    nointerpolation uint decalIndex : INDEX0)
{
    uint2 pixel = (uint2)(screenUv * (float2)cb_vuViewportSize);
    float viewDistance = DepthToViewDistance(tDepth.Load(int3(pixel, 0)));
    float3 localPosition = ViewToDecal(
        ReconstructViewPosition(screenUv, viewDistance), decalIndex);
    if (any(0.5 - abs(localPosition) < 0.0))
        discard;
}
#endif
