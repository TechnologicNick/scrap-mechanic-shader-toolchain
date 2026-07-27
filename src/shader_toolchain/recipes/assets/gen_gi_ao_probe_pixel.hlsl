#include "include/perframe_abi.hlsl"

cbuffer CB_PARAMS : register(b0)
{
    struct
    {
        float fIndex;
        float3 _padding;
    } cb_param : packoffset(c0);
}

SamplerState PointClampClamp_s : register(s1);
TextureCubeArray<float4> taCubes : register(t0);

struct ProbeResult
{
    float4 irradianceAndOcclusion : SV_Target0;
    float ambientOcclusion : SV_Target1;
};

float3 DecodeOctahedralDirection(float2 uv)
{
    float2 projected = uv * 2.0 - 1.0;
    float vertical = 1.0 - abs(projected.x) - abs(projected.y);
    float fold = saturate(-vertical);
    projected += float2(
        projected.x >= 0.0 ? -fold : fold,
        projected.y >= 0.0 ? -fold : fold
    );
    return normalize(float3(projected.x, vertical, projected.y));
}

void BuildHemisphereBasis(float3 normal, out float3 tangentX, out float3 tangentY)
{
    float hemisphereSign = normal.y >= 0.0 ? 1.0 : -1.0;
    float denominator = -1.0 / (normal.y + hemisphereSign);
    tangentX = float3(
        normal.x * normal.z * denominator,
        -normal.z,
        normal.z * normal.z * denominator + hemisphereSign
    );
    tangentY = float3(
        1.0 + hemisphereSign * normal.x * normal.x * denominator,
        -hemisphereSign * normal.x,
        hemisphereSign * normal.x * normal.z * denominator
    );
}

ProbeResult mainPS(
    float4 position : SV_Position,
    float2 uv : UNSCALED_UV0
)
{
    float3 normal = DecodeOctahedralDirection(uv);
    float3 tangentX;
    float3 tangentY;
    BuildHemisphereBasis(normal, tangentX, tangentY);

    float minimumColorScale = cb_fTodFactor * 0.5 + 0.5;
    float colorScaleRange = cb_fTodFactor * 0.5 + 6.0;
    float minimumSampleWeight = cb_fTodFactor * cb_fTodFactor * -0.5 + 0.5;
    float3 weightedColorSum = 0.0;
    float weightedOcclusionSum = 0.0;
    float sampleWeightSum = 0.0;
    float occlusionSum = 0.0;

    [loop]
    for (uint sampleIndex = 0; sampleIndex < 1024; ++sampleIndex)
    {
        float angle = 2.39996314 * float(sampleIndex);
        float cosine = sqrt((float(sampleIndex) + 0.5) * 0.0009765625);
        float radial = sqrt(mad(
            -(float(sampleIndex) + 0.5), 0.0009765625, 1.0
        ));
        float sineAngle;
        float cosineAngle;
        sincos(angle, sineAngle, cosineAngle);
        float3 tangentContribution = tangentX * (sineAngle * radial);
        tangentContribution = mad(
            tangentY, cosineAngle * radial, tangentContribution
        );
        float3 sampleDirection = mad(normal, cosine, tangentContribution);
        sampleDirection = normalize(sampleDirection);

        float4 sample = taCubes.SampleLevel(
            PointClampClamp_s,
            float4(sampleDirection, cb_param.fIndex),
            0.0
        );
        float colorVariation = dot(
            abs(sample.rgb - sample.gbr),
            float3(0.333333343, 0.333333343, 0.333333343)
        );
        colorVariation = min(1.0, colorVariation * 1.33333337);
        float3 scaledColor = sample.rgb
            * (minimumColorScale + colorVariation * colorScaleRange);

        float encodedOcclusion = sample.a * sample.a * 127.5 + 0.5;
        float openness = 1.0 - min(1.0, encodedOcclusion * 0.0078125);
        weightedOcclusionSum += encodedOcclusion * openness;
        float sampleWeight = max(openness * openness, minimumSampleWeight);
        sampleWeightSum += sampleWeight;
        weightedColorSum += scaledColor * sampleWeight;
        occlusionSum += encodedOcclusion;
    }

    float3 irradiance = weightedColorSum * 0.0009765625;
    float weightedOcclusion = weightedOcclusionSum / sampleWeightSum;
    float2 accumulatedOcclusion = saturate(
        float2(0.000122070312, 0.0000305175781) * occlusionSum
    );
    float colorVisibility = 1.0
        - (1.0 - accumulatedOcclusion.x) * (1.0 - accumulatedOcclusion.x);

    ProbeResult output;
    output.ambientOcclusion = 1.0 - accumulatedOcclusion.y;
    output.irradianceAndOcclusion.rgb = irradiance * colorVisibility * 0.5;
    output.irradianceAndOcclusion.a = sqrt(
        (weightedOcclusion - 0.5) * 0.00784313772
    );
    return output;
}
