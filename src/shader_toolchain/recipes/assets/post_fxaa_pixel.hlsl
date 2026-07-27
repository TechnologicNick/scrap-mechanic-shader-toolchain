SamplerState LinearClampClamp : register(s6);
Texture2D<float4> inputColor : register(t0);

static const float3 LUMA_WEIGHTS = float3(0.299, 0.587, 0.114);
static const float FXAA_REDUCE_MIN = 1.0 / 128.0;
static const float FXAA_REDUCE_MUL = 1.0 / 8.0;
static const float FXAA_SPAN_MAX = 8.0;

float4 SampleInput(float2 uv)
{
    return inputColor.SampleLevel(LinearClampClamp, min(cb_vUvLimit, uv), 0.0);
}

float Luminance(float3 color)
{
    return dot(color, LUMA_WEIGHTS);
}

float4 mainPS(float4 position : SV_Position0, float4 interpolatedUv : UV0)
    : SV_Target0
{
    float2 pixelSize = cb_vContainerPixelSize;
    float2 centerUv = interpolatedUv.xy;
    float2 northWestUv = interpolatedUv.zw;

    float3 northWest = SampleInput(northWestUv).rgb;
    float3 northEast = SampleInput(northWestUv + float2(pixelSize.x, 0.0)).rgb;
    float3 southWest = SampleInput(northWestUv + float2(0.0, pixelSize.y)).rgb;
    float3 southEast = SampleInput(northWestUv + pixelSize).rgb;
    float4 center = SampleInput(centerUv);

    float lumaNorthWest = Luminance(northWest);
    float lumaNorthEast = Luminance(northEast);
    float lumaSouthWest = Luminance(southWest);
    float lumaSouthEast = Luminance(southEast);
    float lumaCenter = Luminance(center.rgb);

    float lumaMinimum = min(
        lumaCenter,
        min(min(lumaNorthWest, lumaNorthEast), min(lumaSouthWest, lumaSouthEast))
    );
    float lumaMaximum = max(
        lumaCenter,
        max(max(lumaNorthWest, lumaNorthEast), max(lumaSouthWest, lumaSouthEast))
    );

    float2 edgeDirection;
    edgeDirection.x = -(
        (lumaNorthWest + lumaNorthEast) - (lumaSouthWest + lumaSouthEast)
    );
    edgeDirection.y = (
        (lumaNorthWest + lumaSouthWest) - (lumaNorthEast + lumaSouthEast)
    );

    float directionReduction = max(
        (lumaNorthWest + lumaNorthEast + lumaSouthWest + lumaSouthEast)
            * (0.25 * FXAA_REDUCE_MUL),
        FXAA_REDUCE_MIN
    );
    float inverseMinimumDirection = rcp(
        min(abs(edgeDirection.x), abs(edgeDirection.y)) + directionReduction
    );
    edgeDirection =
        clamp(edgeDirection * inverseMinimumDirection, -FXAA_SPAN_MAX, FXAA_SPAN_MAX)
        * pixelSize;

    float3 innerColor = 0.5 * (
        SampleInput(centerUv + edgeDirection * (-1.0 / 6.0)).rgb
        + SampleInput(centerUv + edgeDirection * (1.0 / 6.0)).rgb
    );
    float3 outerColor = 0.5 * innerColor + 0.25 * (
        SampleInput(centerUv + edgeDirection * -0.5).rgb
        + SampleInput(centerUv + edgeDirection * 0.5).rgb
    );

    float outerLuma = Luminance(outerColor);
    float3 filteredColor =
        outerLuma < lumaMinimum || outerLuma > lumaMaximum ? innerColor : outerColor;
    return float4(filteredColor, center.a);
}
