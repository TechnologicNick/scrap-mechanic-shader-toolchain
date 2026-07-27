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

RWTexture2D<float2> initialSpectrum : register(u0);

uint PermuteRandom(uint state)
{
    uint shift = (state >> 28) + 4;
    uint word = ((state >> shift) ^ state) * 0x108ef2d9u;
    return (word >> 22) ^ word;
}

uint NextRandom(uint state)
{
    state = state * 0x2c9277b5u + 0xac564b05u;
    return PermuteRandom(state);
}

uint PixelSeed(uint2 pixel)
{
    uint seed = pixel.x * 1973u + 3242u;
    seed = pixel.y * 9277u + seed;
    seed = seed + 0x0000684bu;
    return (pixel.y ^ pixel.x) * 4801u + seed;
}

[numthreads(32, 32, 1)]
void mainCS(uint3 dispatchThreadId : SV_DispatchThreadID)
{
    uint2 pixel = dispatchThreadId.xy;
    float windLength = water.windSpeed * water.windSpeed / water.gravity;
    float windLengthSquared = windLength * windLength;

    float2 waveVector = (float2(pixel) - 128.0) * water.tauDivPatchSize;
    float waveNumberSquared = dot(waveVector, waveVector);
    float spectrum = exp2(
        1.44269502 * (-1.0 / (windLengthSquared * waveNumberSquared))
    );
    spectrum = water.waveAmplitude * spectrum;
    spectrum = spectrum / (waveNumberSquared * waveNumberSquared);

    float reciprocalWaveNumber = rsqrt(waveNumberSquared);
    float waveNumber = sqrt(waveNumberSquared);
    float2 waveDirection = reciprocalWaveNumber * waveVector;
    float directionalAlignment = dot(waveDirection, water.windDirection);
    directionalAlignment = directionalAlignment * directionalAlignment;
    spectrum = spectrum * directionalAlignment;
    spectrum = waveNumber >= 9.99999997e-7 ? spectrum : 0.0;
    spectrum = 0.5 * spectrum;

    uint firstRandom = NextRandom(PixelSeed(pixel));
    uint secondRandom = NextRandom(firstRandom);
    float uniformRadius = max(
        1.1920929e-7, float(firstRandom) * 2.32830644e-10
    );
    float gaussianRadius = sqrt(-1.38629436 * log2(uniformRadius));
    float angle = float(secondRandom) * 1.46291812e-9;
    float sine;
    float cosine;
    sincos(angle, sine, cosine);

    float amplitude = sqrt(spectrum);
    initialSpectrum[pixel] = float2(cosine, sine)
        * gaussianRadius * amplitude;
}
