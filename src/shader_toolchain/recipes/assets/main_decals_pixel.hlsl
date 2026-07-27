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

// Instruction-ordered form of the tangent-frame blend.  The temporary axis
// layout mirrors the shipped shader so derivative and normalization rounding
// remain stable across the legacy HLSL compiler.
float2 EncodeDecalNormalExact(
    float3 viewPosition, float2 atlasUv, float2 sampledNormal,
    float2 encodedBaseNormal)
{
    float4 r0, r1, r2, r3, r4, r5;
    r0.xy = sampledNormal;
    r1.xy = encodedBaseNormal;
    r4.xyz = -viewPosition.yzx;
    r3.xy = atlasUv;
    r0.z = 1.0 - abs(r1.x);
    r2.x = r0.z - abs(r1.y);
    r0.z = saturate(-r2.x);
    r1.zw = r1.xy >= 0.0;
    r0.zw = r1.zw ? -r0.zz : r0.zz;
    r2.yz = r0.zw + r1.xy;
    r0.z = dot(r2.xyz, r2.xyz);
    r0.z = rsqrt(r0.z);
    r1.xyz = r2.xyz * r0.zzz;
    r2.xyz = ddy_coarse(r4.xyz);
    r4.xyz = ddx_coarse(r4.zxy);
    r5.xyz = r1.yzx * r2.xyz;
    r2.xyz = mad(r2.zxy, r1.zxy, -r5.xyz);
    r5.xyz = r1.zxy * r4.xyz;
    r4.xyz = mad(r1.yzx, r4.yzx, -r5.xyz);
    r0.zw = ddy_coarse(r3.xy);
    r3.xy = ddx_coarse(r3.xy);
    precise float3 weightedBitangentX = r0.z * r4.xyz;
    precise float3 weightedBitangentY = r0.w * r4.xyz;
    r3.yzw = mad(r2.xyz, r3.y, weightedBitangentY);
    r2.xyz = mad(r2.xyz, r3.x, weightedBitangentX);
    r0.z = dot(r2.xyz, r2.xyz);
    r0.w = dot(r3.yzw, r3.yzw);
    r0.z = max(r0.w, r0.z);
    r0.z = rsqrt(r0.z);
    r3.xyz = r3.yzw * r0.zzz;
    r2.xyz = r2.xyz * r0.zzz;
    precise float3 weightedAxisY = r0.y * r3.xyz;
    r2.xyz = mad(r0.x, r2.xyz, weightedAxisY);
    r0.x = 1.0 - dot(r0.xy, r0.xy);
    r0.x = sqrt(max(0.0, r0.x));
    r0.xyz = mad(r0.x, r1.xyz, r2.xyz);
    r0.w = rsqrt(dot(r0.xyz, r0.xyz));
    r0.xyz *= r0.w;
    r0.w = abs(r0.z) + abs(r0.y);
    r0.w = abs(r0.x) + r0.w;
    r0.xyz /= r0.w;
    r1.xy = 1.0 - abs(r0.zy);
    r2.xyz = r0.xyz >= 0.0;
    r0.xw = r2.yz ? 1.0 : -1.0;
    r0.xw *= r1.xy;
    r0.xy = r2.x ? r0.yz : r0.xw;
    return mad(r0.xy, 0.5, 0.5);
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
    output.normal = EncodeDecalNormalExact(
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
