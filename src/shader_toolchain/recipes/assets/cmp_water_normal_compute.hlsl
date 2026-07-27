cbuffer CB_WATER_PARAMS : register(b1)
{
    struct
    {
        float gravity;
        float2 windDirection;
        float windSpeed;
        float waveAmplitude;
        float patchSize;
        float time;
        float damping;
        float tauDivPatchSize;
        float texelSize;
        float _padding;
    } water : packoffset(c0);
}

Texture2D<float> heightField : register(t0);
RWTexture2D<float2> encodedNormals : register(u0);

float Height(uint2 coordinate)
{
    return heightField.Load(uint3(coordinate, 0));
}

[numthreads(32, 32, 1)]
void mainCS(uint3 dispatchThreadId : SV_DispatchThreadID)
{
    uint2 center = dispatchThreadId.xy;
    uint xMinus = (center.x + 255) & 255;
    uint xPlus = (center.x + 1) & 255;
    uint yMinus = (center.y + 255) & 255;
    uint yPlus = (center.y + 1) & 255;

    float northWest = Height(uint2(xMinus, yMinus));
    float north = Height(uint2(center.x, yMinus));
    float northEast = Height(uint2(xPlus, yMinus));
    float west = Height(uint2(xMinus, center.y));
    float east = Height(uint2(xPlus, center.y));
    float southWest = Height(uint2(xMinus, yPlus));
    float south = Height(uint2(center.x, yPlus));
    float southEast = Height(uint2(xPlus, yPlus));

    float verticalDerivative = (south - north) * 2.0
        + (southWest - northWest);
    verticalDerivative = verticalDerivative + (southEast - northEast);
    float horizontalDerivative = (east - west) * 2.0
        + (northEast - northWest);
    horizontalDerivative = horizontalDerivative + (southEast - southWest);

    float derivativeScale = water.texelSize * water.waveAmplitude;
    float2 scaledDerivative = float2(
        horizontalDerivative, verticalDerivative
    ) * derivativeScale;
    float3 normal = float3(0.0, 0.0, 4.0)
        - float3(scaledDerivative + scaledDerivative, 0.0);
    normal *= rsqrt(dot(normal, normal));
    precise float planarMagnitude = abs(normal.x) + abs(normal.y);
    precise float encodingDenominator = normal.z + planarMagnitude;
    float2 encoded = normal.xy / encodingDenominator;
    encodedNormals[center] = encoded * 0.5 + 0.5;
}
