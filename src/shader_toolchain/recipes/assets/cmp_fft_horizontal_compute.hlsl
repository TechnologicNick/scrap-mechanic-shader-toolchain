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

Texture2D<float2> inputSpectrum : register(t0);
RWTexture2D<float2> transformedSpectrum : register(u0);
groupshared float2 fftValues[512];

float2 RotateComplex(float2 value, float sine, float cosine)
{
    return float2(
        value.x * cosine - value.y * sine,
        value.y * cosine + value.x * sine
    );
}

float2 RotateSwappedComplex(float2 value, float sine, float cosine)
{
    return float2(
        value.x * cosine + value.y * sine,
        value.y * cosine - value.x * sine
    );
}

[numthreads(256, 1, 1)]
void mainCS(uint3 dispatchThreadId : SV_DispatchThreadID)
{
    uint lane = dispatchThreadId.x;
    uint2 reversed = reversebits(dispatchThreadId.xy) >> 24;
    uint2 negative = (256 - reversed) & 255;
    float2 positiveSpectrum = inputSpectrum.Load(
        uint3(reversed, 0)
    );
    float2 negativeSpectrum = inputSpectrum.Load(
        uint3(negative, 0)
    );

    float2 waveVector = (float2(dispatchThreadId.xy) - 128.0)
        * water.tauDivPatchSize;
    float phase = water.time * sqrt(water.gravity * length(waveVector));
    float sine;
    float cosine;
    sincos(phase, sine, cosine);
    float2 evolved = RotateComplex(positiveSpectrum, sine, cosine)
        + RotateComplex(negativeSpectrum, -sine, cosine);
    fftValues[lane] = evolved;
    GroupMemoryBarrierWithGroupSync();

    uint sourceBank = 0;
    [unroll]
    for (uint span = 2; span <= 256; span <<= 1)
    {
        uint halfSpan = span >> 1;
        uint position = lane & (span - 1);
        bool lowerHalf = position < halfSpan;
        uint partner = lowerHalf ? lane + halfSpan : lane - halfSpan;
        float2 current = fftValues[sourceBank + lane].yx;
        float2 other = fftValues[sourceBank + partner].yx;
        uint twiddleIndex = position & (halfSpan - 1);
        float angle = 6.28318548 * float(twiddleIndex) / float(span);
        sincos(angle, sine, cosine);
        float2 rotatedOther = RotateSwappedComplex(other, sine, cosine);
        float2 result = lowerHalf
            ? current + rotatedOther
            : other - RotateSwappedComplex(current, sine, cosine);
        uint destinationBank = sourceBank ^ 256;
        fftValues[destinationBank + lane] = result.yx;
        GroupMemoryBarrierWithGroupSync();
        sourceBank = destinationBank;
    }
    transformedSpectrum[dispatchThreadId.xy] = fftValues[sourceBank + lane];
}
