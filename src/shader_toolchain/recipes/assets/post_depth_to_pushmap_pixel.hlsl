#include "include/post_fxaa_abi.hlsl"
#include "include/perframe_abi.hlsl"

cbuffer CB_PARAMS : register(b0)
{
    struct
    {
        float2 vPrevUvOffset;
        float fPrevZ;
        float fMaxDepth;
        float fMaxDepthRcp;
        float fDt;
        float2 _padding;
    } cb_params : packoffset(c0);
}

SamplerState PointClampClamp_s : register(s1);
SamplerState LinearClampClamp_s : register(s6);
Texture2D<float> tDepth : register(t0);
Texture2D<float3> tPrevPushMap : register(t1);

float MaximumGatheredDepth(float2 uv)
{
    float4 gathered = tDepth.Gather(LinearClampClamp_s, uv);
    return max(max(gathered.x, gathered.y), max(gathered.z, gathered.w));
}

float2 AccumulateDepthDirection(
    float2 direction,
    float2 sampleOffset,
    float centerDepth,
    float2 gradient
)
{
    float depthDifference = abs(
        MaximumGatheredDepth(sampleOffset) - centerDepth
    );
    return gradient + direction * depthDifference;
}

float3 mainPS(
    float4 position : SV_Position,
    float2 uv : UV0,
    float2 unscaledUv : UNSCALED_UV0
) : SV_Target0
{
    float centerDepth = tDepth.SampleLevel(PointClampClamp_s, uv, 0.0).r;
    float2 texel = cb_vContainerPixelSize;
    float2 gradient = 0.0;
    gradient = AccumulateDepthDirection(
        float2(1.0, 0.0), uv + texel * float2(4.0, 0.0),
        centerDepth, gradient
    );
    gradient = AccumulateDepthDirection(
        float2(0.309017003, 0.951057017),
        uv + texel * float2(1.23606801, 3.80422807),
        centerDepth, gradient
    );
    gradient = AccumulateDepthDirection(
        float2(-0.809017003, 0.587785006),
        uv + texel * float2(-3.23606801, 2.35114002),
        centerDepth, gradient
    );
    gradient = AccumulateDepthDirection(
        float2(-0.809017003, -0.587785006),
        uv + texel * float2(-3.23606801, -2.35114002),
        centerDepth, gradient
    );
    gradient = AccumulateDepthDirection(
        float2(0.309017003, -0.951056004),
        uv + texel * float2(1.23606801, -3.80422401),
        centerDepth, gradient
    );

    float outputDepth = centerDepth;
    float2 previousUv = uv + cb_params.vPrevUvOffset;
    bool previousUvValid = all(previousUv > 0.0) && all(previousUv < 1.0);
    if (previousUvValid)
    {
        float3 previous = tPrevPushMap.SampleLevel(
            PointClampClamp_s, previousUv, 0.0
        );
        float2 previousDirection = previous.xy * 2.0 - 1.0;
        bool missingCurrentDepth = centerDepth == 0.0;
        float expansion = 0.200000003 * cb_fAvgDeltaTime;
        float2 expandedDirection = 0.0;
        if (dot(previousDirection, previousDirection) > expansion * expansion)
        {
            expandedDirection = previousDirection
                + sign(previousDirection) * expansion;
        }
        if (missingCurrentDepth)
        {
            previousDirection = expandedDirection;
        }

        float previousWorldDepth = (1.0 - previous.z) * cb_params.fMaxDepth
            + cb_params.fPrevZ - viewToWorld._m23;
        previousWorldDepth = min(
            cb_params.fMaxDepth, max(0.0, previousWorldDepth)
        );
        float encodedPreviousDepth = 1.0
            - previousWorldDepth * cb_params.fMaxDepthRcp;
        outputDepth = max(encodedPreviousDepth, centerDepth);
        gradient = previousDirection
            + gradient * (missingCurrentDepth ? 0.5 : 0.0);
    }

    gradient = min(1.0, max(-1.0, gradient));
    return float3(gradient * 0.5 + 0.5, outputDepth);
}
