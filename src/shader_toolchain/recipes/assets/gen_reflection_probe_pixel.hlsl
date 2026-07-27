cbuffer CB_PARAMS : register(b0)
{
    struct
    {
        float fIndex;
        float fMipLevel;
        float2 padding;
    } cb_param : packoffset(c0);
}

#if defined(PS_OCTAHEDRAL)
SamplerState PointMirrorMirror : register(s2);
SamplerState LinearMirrorMirror : register(s11);
#if defined(PS_ARRAY)
Texture2DArray<float4> probeTexture : register(t0);
#else
Texture2D<float4> probeTexture : register(t0);
#endif
#else
SamplerState PointClampClamp : register(s1);
SamplerState LinearClampClamp : register(s6);
#if defined(PS_ARRAY)
TextureCubeArray<float4> probeTexture : register(t0);
#else
TextureCube<float4> probeTexture : register(t0);
#endif
#endif

static const float3 LUMINANCE_WEIGHTS = float3(0.299, 0.587, 0.114);

// sqrt((sampleIndex + 0.5) / 32), retained at the precision recovered from
// DXBC so the unrolled loop uses the shipped hemisphere elevations.
static const float HEMISPHERE_RADII[32] = {
    0.125, 0.216506347, 0.279508501, 0.330718905,
    0.375, 0.41457811, 0.450693905, 0.484122932,
    0.515388191, 0.54486239, 0.572821975, 0.59947896,
    0.625, 0.649519026, 0.673145592, 0.695970535,
    0.718070328, 0.73951, 0.76034534, 0.780624747,
    0.800390542, 0.819679797, 0.838525474, 0.85695684,
    0.875, 0.892678559, 0.910013735, 0.927024782,
    0.943729281, 0.960143209, 0.976281226, 0.992156744,
};

// cos/sin of successive golden-angle rotations. These are precomputed in the
// original program rather than evaluated with GPU trigonometry.
static const float2 GOLDEN_ANGLE_DIRECTIONS[32] = {
    float2(1, 0),
    float2(-0.737368822, 0.675490379),
    float2(0.0874255449, -0.996171057),
    float2(0.608439267, 0.79360044),
    float2(-0.984713554, -0.174181595),
    float2(0.843755186, -0.536728203),
    float2(-0.259603322, 0.965715349),
    float2(-0.460907787, -0.887448013),
    float2(0.939321518, 0.343037963),
    float2(-0.924345315, 0.381556928),
    float2(0.423845619, -0.90573442),
    float2(0.29928413, 0.954164028),
    float2(-0.865212202, -0.501405835),
    float2(0.976675391, -0.214721262),
    float2(-0.575128019, 0.818063438),
    float2(-0.128512248, -0.991707921),
    float2(0.764649928, 0.644445896),
    float2(-0.999145985, 0.041319102),
    float2(0.708828628, -0.705380738),
    float2(-0.0461904667, 0.99893266),
    float2(-0.640709758, -0.767783165),
    float2(0.991069496, 0.133346319),
    float2(-0.820858061, 0.571132302),
    float2(0.219480991, -0.975616753),
    float2(0.497184396, 0.867644906),
    float2(-0.952693939, -0.303931266),
    float2(0.907789588, -0.419425935),
    float2(-0.386057764, 0.922474623),
    float2(-0.338455528, -0.940982401),
    float2(0.885190964, 0.465227842),
    float2(-0.966969192, 0.254893243),
    float2(0.540835202, -0.841128588),
};

float3 DecodeDestinationDirection(float2 uv)
{
    float2 octahedral = uv * 2.0 - 1.0;
    float middle = 1.0 - abs(octahedral.x) - abs(octahedral.y);
    float fold = saturate(-middle);
    float2 adjustment = octahedral >= 0.0 ? -fold : fold;
    float3 direction = float3(octahedral.x + adjustment.x,
                              middle,
                              octahedral.y + adjustment.y);
    return direction * rsqrt(dot(direction, direction));
}

float2 EncodeOctahedralMirror(float3 direction)
{
    float inverseL1 = rcp(max(1.0e-4,
        abs(direction.x) + abs(direction.y) + abs(direction.z)));
    float2 projected = direction.xy * inverseL1;
    float2 folded = 1.0 - abs(projected.yx);
    folded = projected < 0.0 ? -folded : folded;
    projected = direction.z <= 0.0 ? folded : projected;

    // The source uses mirror addressing and stores its octahedron two tiles
    // away from the canonical range. Preserve that recovered edge convention.
    projected += float2(-2.0, 2.0);
    projected = max(abs(projected.x), abs(projected.y)) >= 1.0
        ? -projected : projected;
    return projected * 0.5 + 0.5;
}

float4 SampleProbePoint(float3 direction)
{
#if defined(PS_OCTAHEDRAL)
    float2 uv = EncodeOctahedralMirror(direction);
#if defined(PS_ARRAY)
    return probeTexture.SampleLevel(PointMirrorMirror,
                                    float3(uv, cb_param.fIndex), 0.0);
#else
    return probeTexture.SampleLevel(PointMirrorMirror, uv, 0.0);
#endif
#else
#if defined(PS_ARRAY)
    return probeTexture.SampleLevel(PointClampClamp,
                                    float4(direction, cb_param.fIndex), 0.0);
#else
    return probeTexture.SampleLevel(PointClampClamp, direction, 0.0);
#endif
#endif
}

float4 SampleProbeLinear(float3 direction)
{
#if defined(PS_OCTAHEDRAL)
    float2 uv = EncodeOctahedralMirror(direction);
#if defined(PS_ARRAY)
    return probeTexture.SampleLevel(LinearMirrorMirror,
                                    float3(uv, cb_param.fIndex), 0.0);
#else
    return probeTexture.SampleLevel(LinearMirrorMirror, uv, 0.0);
#endif
#else
#if defined(PS_ARRAY)
    return probeTexture.SampleLevel(LinearClampClamp,
                                    float4(direction, cb_param.fIndex), 0.0);
#else
    return probeTexture.SampleLevel(LinearClampClamp, direction, 0.0);
#endif
#endif
}

void BuildHemisphereBasis(float3 normal, out float3 tangent, out float3 bitangent)
{
    float signY = normal.y >= 0.0 ? 1.0 : -1.0;
    float inverseDenominator = -rcp(normal.y + signY);
    tangent = float3(
        1.0 + signY * normal.x * normal.x * inverseDenominator,
        -signY * normal.x,
        signY * normal.x * normal.z * inverseDenominator
    );
    bitangent = float3(
        normal.x * normal.z * inverseDenominator,
        -normal.z,
        signY + normal.z * normal.z * inverseDenominator
    );
}

float SampleWeight(float4 sampleValue, float accumulatedAlpha)
{
    float luminance = dot(sampleValue.rgb, LUMINANCE_WEIGHTS);
    float luminanceCubed = luminance * luminance * luminance;
    float alphaFade = saturate(accumulatedAlpha * (1.0 / 128.0));
    alphaFade = 1.0 - alphaFade * alphaFade;
    return 1.0 + alphaFade * (1.0 + 25.0 * luminanceCubed);
}

float4 mainPS(float4 position : SV_Position0, float2 uv : UNSCALED_UV0)
    : SV_Target0
{
    float3 normal = DecodeDestinationDirection(uv);
    float roughness = saturate(0.25 * cb_param.fMipLevel);
    if (roughness == 0.0)
        return SampleProbePoint(normal);

    float3 tangent;
    float3 bitangent;
    BuildHemisphereBasis(normal, tangent, bitangent);

    float roughnessCosine = cos(
        roughness * roughness * 0.36815539 + 0.0245436933
    );
    float cosineRange = 1.0 - roughnessCosine;
    float totalWeight = 0.0;
    float accumulatedAlpha = 0.0;
    float3 accumulatedColor = 0.0;

    [unroll]
    for (uint sampleIndex = 0; sampleIndex < 32; ++sampleIndex)
    {
        float sampleCosine =
            cosineRange * HEMISPHERE_RADII[sampleIndex] + roughnessCosine;
        float sampleSine = sqrt(1.0 - sampleCosine * sampleCosine);
        float2 azimuth = GOLDEN_ANGLE_DIRECTIONS[sampleIndex] * sampleSine;
        float3 sampleDirection = normal * sampleCosine;
        sampleDirection = tangent * azimuth.x + sampleDirection;
        sampleDirection = bitangent * azimuth.y + sampleDirection;
        sampleDirection *= rsqrt(dot(sampleDirection, sampleDirection));

        float4 sampleValue = SampleProbeLinear(sampleDirection);
        float weight = SampleWeight(sampleValue, accumulatedAlpha);
        float encodedAlpha = sampleValue.a * sampleValue.a;
        encodedAlpha = encodedAlpha * 127.5 + 0.5;
        totalWeight = weight + totalWeight;
        accumulatedAlpha = encodedAlpha * weight + accumulatedAlpha;
        accumulatedColor = sampleValue.rgb * weight + accumulatedColor;
    }

    float normalization = max(0.001, totalWeight);
    float4 result;
    result.rgb = accumulatedColor / normalization;
    result.a = sqrt((accumulatedAlpha / normalization - 0.5) / 127.5);
    return result;
}
