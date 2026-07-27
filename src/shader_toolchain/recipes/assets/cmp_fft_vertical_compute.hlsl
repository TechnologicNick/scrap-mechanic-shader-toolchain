Texture2D<float2> inputSpectrum : register(t0);
RWTexture2D<float> heightField : register(u0);
groupshared float2 fftValues[512];

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
    fftValues[lane] = inputSpectrum.Load(
        uint3(dispatchThreadId.y, lane, 0)
    );
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
        float sine;
        float cosine;
        sincos(angle, sine, cosine);
        float2 result = lowerHalf
            ? current + RotateSwappedComplex(other, sine, cosine)
            : other - RotateSwappedComplex(current, sine, cosine);
        uint destinationBank = sourceBank ^ 256;
        fftValues[destinationBank + lane] = result.yx;
        GroupMemoryBarrierWithGroupSync();
        sourceBank = destinationBank;
    }

    float checkerboard = ((dispatchThreadId.x ^ dispatchThreadId.y) & 1)
        ? -1.0 : 1.0;
    heightField[dispatchThreadId.yx] = checkerboard
        * fftValues[sourceBank + lane].x * 0.00390625;
}
