#include "include/perframe_abi.hlsl"

SamplerState PointClampClamp_s : register(s1);
SamplerState LinearWrapClamp_s : register(s4);
Texture2D<float4> tSkyColorMap : register(t0);
Texture2D<float4> tLightColorMap : register(t1);
Texture2DArray<float4> tSky : register(t2);
Texture2DArray<float4> tDetail : register(t3);

float3 DetailLighting(float3 detail)
{
    float luminance = dot(detail, float3(0.299, 0.587, 0.114));
    return tLightColorMap.Sample(
        LinearWrapClamp_s, float2(cb_fTimeOfDay, luminance * 0.5 + 0.5)
    ).rgb;
}

float4 ComposeSkyFace(float2 uv, float layer)
{
    float skyCoordinate = tSky.Sample(
        PointClampClamp_s, float3(uv, layer)
    ).r;
    float4 detail = tDetail.Sample(
        PointClampClamp_s, float3(uv, layer)
    );
    float3 sky = tSkyColorMap.Sample(
        LinearWrapClamp_s, float2(cb_fTimeOfDay, skyCoordinate)
    ).rgb;
    float3 litDetail = detail.rgb * DetailLighting(detail.rgb);
    return float4(sky + detail.a * (litDetail - sky), 1.0);
}

float4 ComposeGroundFace(float2 uv)
{
    float3 detail = tDetail.Sample(
        PointClampClamp_s, float3(uv, 3.0)
    ).rgb;
    return float4(detail * DetailLighting(detail), 1.0);
}

struct CubeFaces
{
    float4 positiveX : SV_Target0;
    float4 negativeX : SV_Target1;
    float4 positiveY : SV_Target2;
    float4 negativeY : SV_Target3;
    float4 positiveZ : SV_Target4;
    float4 negativeZ : SV_Target5;
};

CubeFaces mainPS(float4 position : SV_Position, float2 uv : UV0)
{
    CubeFaces output;
    output.positiveX = ComposeSkyFace(uv, 0.0);
    output.negativeX = ComposeSkyFace(uv, 1.0);
    output.positiveY = ComposeSkyFace(uv, 2.0);
    output.negativeY = ComposeGroundFace(uv);
    output.positiveZ = ComposeSkyFace(uv, 4.0);
    output.negativeZ = ComposeSkyFace(uv, 5.0);
    return output;
}
