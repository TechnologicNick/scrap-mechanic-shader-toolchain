#include "include/post_fxaa_abi.hlsl"
#include "include/perframe_abi.hlsl"

SamplerState LinearClampClamp_s : register(s6);
Texture2D<float3> tColor : register(t0);
#if defined(PS_LUT_A)
Texture3D<float3> tLutA : register(t1);
#endif
#if defined(PS_LUT_B)
Texture3D<float3> tLutB : register(t2);
#endif

float2 DistortUv(float2 uv)
{
    float2 center = cb_vRenderScale * 0.5;
    float2 centered = uv - center;
    float radialScale = mad(
        cb_fBarrelDistortionIntensity, dot(centered, centered), 1.0);
    float zoom = max(0.0000999999975, 1.0 + cb_fZoom);
    // Keep the reciprocal scalar materialized: the original rounds it before
    // the component-wise multiply, which differs from a vector divide.
    precise float inverseZoom = rcp(zoom);
    return mad(centered * radialScale, inverseZoom, center);
}

float3 SampleSceneColor(float2 uv)
{
#if defined(PS_BARREL_DISTORTION) && defined(PS_CHROMATIC)
    float2 center = cb_vRenderScale * 0.5;
    float2 centered = uv - center;
    float radialScale = mad(
        cb_fBarrelDistortionIntensity, dot(centered, centered), 1.0);
    float2 distorted = centered * radialScale;
    float zoom = max(0.0000999999975, 1.0 + cb_fZoom);
    float inverseZoom = rcp(zoom);
    float2 baseUv = distorted * inverseZoom + center;

    float2 redCentered = centered
        + cb_vContainerPixelSize * cb_fChromaticAberrationIntensity;
    float redScale = mad(cb_fBarrelDistortionIntensity,
                         dot(redCentered, redCentered), 1.0);
    float2 redUv = redCentered * redScale * inverseZoom - distorted * inverseZoom;
    redUv += baseUv;

    float2 blueCentered = centered
        - cb_vContainerPixelSize * cb_fChromaticAberrationIntensity;
    float blueScale = mad(cb_fBarrelDistortionIntensity,
                          dot(blueCentered, blueCentered), 1.0);
    float2 blueUv = blueCentered * blueScale * inverseZoom - distorted * inverseZoom;
    blueUv += baseUv;
    return float3(
        tColor.SampleLevel(LinearClampClamp_s, redUv, 0.0).r,
        tColor.SampleLevel(LinearClampClamp_s, baseUv, 0.0).g,
        tColor.SampleLevel(LinearClampClamp_s, blueUv, 0.0).b);
#elif defined(PS_BARREL_DISTORTION)
    return tColor.SampleLevel(LinearClampClamp_s, DistortUv(uv), 0.0);
#elif defined(PS_CHROMATIC)
    float2 offset = cb_vContainerPixelSize * cb_fChromaticAberrationIntensity;
    return float3(
        tColor.SampleLevel(LinearClampClamp_s, uv + offset, 0.0).r,
        tColor.SampleLevel(LinearClampClamp_s, uv, 0.0).g,
        tColor.SampleLevel(LinearClampClamp_s, uv - offset, 0.0).b);
#else
    return tColor.SampleLevel(LinearClampClamp_s, uv, 0.0);
#endif
}

float FilmGrain(float2 unscaledUv)
{
    float animation = mad(cb_fRandom, 127.099998, 23.4500008 * cb_fTime);
    float3 seed = float3(unscaledUv.x, unscaledUv.y, unscaledUv.x)
        * (float3)cb_vuViewportSize.xyx + animation;
    seed = frac(seed * float3(0.103100002, 0.103, 0.0973000005));
    seed += dot(seed, seed.yzx + 33.3300018);
    float noise = frac((seed.x + seed.y) * seed.z) - 0.5;
    // The shipped shader deliberately expresses this as a two-lane dot.  It
    // therefore contributes twice the scalar intensity, rather than once.
    return dot(noise.xx, cb_fFilmGrainIntensity.xx);
}

float Vignette(float2 unscaledUv)
{
    float radius = length(unscaledUv - 0.5);
    float innerRadius = 1.0 - cb_fVignetteRadius;
    float normalized = max(0.0, (radius * 2.0 - innerRadius) / innerRadius);
    return cb_fVignetteIntensity
        * exp2((1.0 + cb_fVignetteSmoothness) * log2(normalized));
}

float3 mainPS(
    float4 position : SV_Position0,
    float2 uv : UV0,
    float2 unscaledUv : UNSCALED_UV0) : SV_Target0
{
#if defined(PS_BLACK_BARS)
    if (unscaledUv.y < cb_fBlackBar || (1.0 - cb_fBlackBar) < unscaledUv.y)
        return 0.0;
#endif

    float3 color = SampleSceneColor(uv);
#if defined(PS_LUT_A)
    float3 graded = tLutA.SampleLevel(LinearClampClamp_s, color, 0.0);
    #if defined(PS_LUT_B)
        float3 secondGrade = tLutB.SampleLevel(LinearClampClamp_s, color, 0.0);
        graded = mad(cb_fLutBlend, secondGrade - graded, graded);
    #endif
    color = graded;
#endif

    color = saturate((color - cb_fBrightnessBase) * cb_fBrightnessRangeRcp);
    color = exp2(log2(color) * cb_fBrightness);

#if defined(PS_FILM_GRAIN)
    color += FilmGrain(unscaledUv);
#endif
#if defined(PS_SCREEN_COLOR)
    color = mad(cb_fScreenColorIntensity,
                cb_vScreenColor * color - color, color);
    color = mad(cb_fScreenColorIntensity,
                cb_vScreenColor - color, color);
#endif
#if defined(PS_VIGNETTE)
    color = mad(Vignette(unscaledUv), -color, color);
#endif
    return color;
}
