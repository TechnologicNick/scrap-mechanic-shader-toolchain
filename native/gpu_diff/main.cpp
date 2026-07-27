#include <d3d11.h>
#include <dxgi.h>
#include <wrl/client.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using Microsoft::WRL::ComPtr;

namespace {

enum class ConstantProfile {
    projection,
    random,
    composition,
    composition_fog,
    hdr,
    rect,
    cluster,
    reflection,
    bloom,
    ao,
    fsr_easu,
    fsr_rcas,
    index,
    auto_hdr,
    cloud,
    cluster_culling,
    hzb,
};

struct ConstantBinding {
    uint32_t slot;
    ConstantProfile profile;
};

struct SamplerBinding {
    uint32_t slot;
    bool point;
    bool comparison = false;
};

enum class TextureKind {
    two_d,
    three_d,
    two_d_array,
    cube,
};

enum class ShaderStage {
    pixel,
    compute,
};

struct TextureBinding {
    uint32_t slot;
    TextureKind kind;
    uint32_t mip_levels;
    uint32_t slices = 0;
};

enum class StructuredInputProfile {
    random,
    zero,
};

struct StructuredInputBinding {
    uint32_t slot;
    uint32_t elements;
    uint32_t stride = sizeof(uint32_t);
    StructuredInputProfile profile = StructuredInputProfile::random;
};

enum class StructuredOutputProfile {
    zero,
    hdr_feedback,
    hdr_setting,
};

struct StructuredOutputBinding {
    uint32_t slot;
    uint32_t elements;
    uint32_t stride = sizeof(uint32_t);
    StructuredOutputProfile profile = StructuredOutputProfile::zero;
};

struct Options {
    ShaderStage stage = ShaderStage::pixel;
    std::filesystem::path vertex;
    std::filesystem::path baseline;
    std::filesystem::path candidate;
    std::filesystem::path failure_dir;
    uint32_t width = 64;
    uint32_t height = 64;
    uint32_t dispatch_width = 0;
    uint32_t dispatch_height = 0;
    uint32_t cases = 256;
    uint64_t seed = 0x534D465841413031ull;
    double absolute_tolerance = 0.0;
    double relative_tolerance = 0.0;
    uint32_t ulp_tolerance = 0;
    std::vector<TextureBinding> textures = {{0, TextureKind::two_d, 1}};
    std::vector<uint32_t> smooth_texture_slots;
    std::vector<uint32_t> monochrome_texture_slots;
    std::vector<StructuredInputBinding> structured_inputs;
    uint32_t structured_output_elements = 0;
    uint32_t structured_output_stride = sizeof(uint32_t);
    std::vector<StructuredOutputBinding> structured_outputs;
    std::vector<SamplerBinding> samplers = {{6, false, false}};
    std::vector<ConstantBinding> constant_buffers = {
        {5, ConstantProfile::projection}};
    bool depth_output = false;
    bool texture_outputs = true;
    uint32_t output_components = 4;
    uint32_t output_targets = 1;
    std::vector<uint32_t> output_target_components;
    std::array<uint32_t, 3> thread_group = {1, 1, 1};
    bool warp = false;
};

struct SplitMix64 {
    uint64_t state;

    uint64_t next() {
        uint64_t value = (state += 0x9E3779B97F4A7C15ull);
        value = (value ^ (value >> 30)) * 0xBF58476D1CE4E5B9ull;
        value = (value ^ (value >> 27)) * 0x94D049BB133111EBull;
        return value ^ (value >> 31);
    }

    float unit() {
        return static_cast<float>(next() >> 40) * (1.0f / 16777216.0f);
    }
};

struct Comparison {
    bool passed = true;
    uint64_t compared_values = 0;
    uint64_t exact_values = 0;
    uint64_t differing_values = 0;
    uint64_t differing_pixels = 0;
    double max_absolute_error = 0.0;
    double max_relative_error = 0.0;
    uint32_t max_ulp_error = 0;
    size_t worst_index = 0;
    float worst_baseline = 0.0f;
    float worst_candidate = 0.0f;
};

void check(HRESULT result, const char* operation) {
    if (FAILED(result)) {
        std::ostringstream message;
        message << operation << " failed with HRESULT 0x" << std::hex
                << static_cast<uint32_t>(result);
        throw std::runtime_error(message.str());
    }
}

std::vector<uint8_t> read_binary(const std::filesystem::path& path) {
    std::ifstream stream(path, std::ios::binary | std::ios::ate);
    if (!stream) {
        throw std::runtime_error("cannot open shader bytecode: " + path.string());
    }
    const auto size = stream.tellg();
    if (size <= 0) {
        throw std::runtime_error("empty shader bytecode: " + path.string());
    }
    std::vector<uint8_t> bytes(static_cast<size_t>(size));
    stream.seekg(0);
    stream.read(reinterpret_cast<char*>(bytes.data()), size);
    if (!stream) {
        throw std::runtime_error("cannot read shader bytecode: " + path.string());
    }
    return bytes;
}

uint64_t parse_u64(const std::string& text) {
    size_t end = 0;
    const uint64_t value = std::stoull(text, &end, 0);
    if (end != text.size()) {
        throw std::runtime_error("invalid integer: " + text);
    }
    return value;
}

double parse_double(const std::string& text) {
    size_t end = 0;
    const double value = std::stod(text, &end);
    if (end != text.size() || !std::isfinite(value) || value < 0.0) {
        throw std::runtime_error("invalid non-negative number: " + text);
    }
    return value;
}

ConstantProfile parse_constant_profile(const std::string& profile) {
    if (profile == "projection") return ConstantProfile::projection;
    if (profile == "random") return ConstantProfile::random;
    if (profile == "composition") return ConstantProfile::composition;
    if (profile == "composition-fog") return ConstantProfile::composition_fog;
    if (profile == "hdr") return ConstantProfile::hdr;
    if (profile == "rect") return ConstantProfile::rect;
    if (profile == "cluster") return ConstantProfile::cluster;
    if (profile == "reflection") return ConstantProfile::reflection;
    if (profile == "bloom") return ConstantProfile::bloom;
    if (profile == "ao") return ConstantProfile::ao;
    if (profile == "fsr-easu") return ConstantProfile::fsr_easu;
    if (profile == "fsr-rcas") return ConstantProfile::fsr_rcas;
    if (profile == "index") return ConstantProfile::index;
    if (profile == "auto-hdr") return ConstantProfile::auto_hdr;
    if (profile == "cloud") return ConstantProfile::cloud;
    if (profile == "cluster-culling") return ConstantProfile::cluster_culling;
    if (profile == "hzb") return ConstantProfile::hzb;
    throw std::runtime_error(
        "unsupported constant-buffer profile");
}

StructuredOutputProfile parse_structured_output_profile(
    const std::string& profile) {
    if (profile == "zero") return StructuredOutputProfile::zero;
    if (profile == "hdr-feedback") return StructuredOutputProfile::hdr_feedback;
    if (profile == "hdr-setting") return StructuredOutputProfile::hdr_setting;
    throw std::runtime_error("unknown structured output profile: " + profile);
}

const char* constant_profile_name(ConstantProfile profile) {
    switch (profile) {
    case ConstantProfile::projection: return "projection";
    case ConstantProfile::random: return "random";
    case ConstantProfile::composition: return "composition";
    case ConstantProfile::composition_fog: return "composition-fog";
    case ConstantProfile::hdr: return "hdr";
    case ConstantProfile::rect: return "rect";
    case ConstantProfile::cluster: return "cluster";
    case ConstantProfile::reflection: return "reflection";
    case ConstantProfile::bloom: return "bloom";
    case ConstantProfile::ao: return "ao";
    case ConstantProfile::fsr_easu: return "fsr-easu";
    case ConstantProfile::fsr_rcas: return "fsr-rcas";
    case ConstantProfile::index: return "index";
    case ConstantProfile::auto_hdr: return "auto-hdr";
    case ConstantProfile::cloud: return "cloud";
    case ConstantProfile::cluster_culling: return "cluster-culling";
    case ConstantProfile::hzb: return "hzb";
    }
    return "unknown";
}

TextureKind parse_texture_kind(const std::string& kind) {
    if (kind == "2d") return TextureKind::two_d;
    if (kind == "3d") return TextureKind::three_d;
    if (kind == "2darray") return TextureKind::two_d_array;
    if (kind == "cube") return TextureKind::cube;
    throw std::runtime_error("texture kind must be 2d, 3d, 2darray, or cube");
}

const char* texture_kind_name(TextureKind kind) {
    switch (kind) {
    case TextureKind::two_d: return "2d";
    case TextureKind::three_d: return "3d";
    case TextureKind::two_d_array: return "2darray";
    case TextureKind::cube: return "cube";
    }
    return "unknown";
}

uint32_t texture_slices(TextureKind kind) {
    if (kind == TextureKind::cube) return 6;
    if (kind == TextureKind::two_d_array) return 6;
    if (kind == TextureKind::three_d) return 4;
    return 1;
}

uint32_t texture_slices(const TextureBinding& binding) {
    return binding.slices == 0 ? texture_slices(binding.kind) : binding.slices;
}

Options parse_options(int argc, char** argv) {
    Options options;
    for (int index = 1; index < argc; ++index) {
        const std::string name = argv[index];
        auto value = [&]() -> std::string {
            if (++index >= argc) {
                throw std::runtime_error("missing value after " + name);
            }
            return argv[index];
        };
        if (name == "--vertex") {
            options.vertex = std::filesystem::u8path(value());
        } else if (name == "--baseline") {
            options.baseline = std::filesystem::u8path(value());
        } else if (name == "--candidate") {
            options.candidate = std::filesystem::u8path(value());
        } else if (name == "--stage") {
            const std::string stage = value();
            if (stage == "compute") {
                options.stage = ShaderStage::compute;
            } else if (stage != "pixel") {
                throw std::runtime_error("stage must be pixel or compute");
            }
        } else if (name == "--failure-dir") {
            options.failure_dir = std::filesystem::u8path(value());
        } else if (name == "--width") {
            options.width = static_cast<uint32_t>(parse_u64(value()));
        } else if (name == "--height") {
            options.height = static_cast<uint32_t>(parse_u64(value()));
        } else if (name == "--dispatch-width") {
            options.dispatch_width = static_cast<uint32_t>(parse_u64(value()));
        } else if (name == "--dispatch-height") {
            options.dispatch_height = static_cast<uint32_t>(parse_u64(value()));
        } else if (name == "--cases") {
            options.cases = static_cast<uint32_t>(parse_u64(value()));
        } else if (name == "--seed") {
            options.seed = parse_u64(value());
        } else if (name == "--absolute-tolerance") {
            options.absolute_tolerance = parse_double(value());
        } else if (name == "--relative-tolerance") {
            options.relative_tolerance = parse_double(value());
        } else if (name == "--ulp-tolerance") {
            options.ulp_tolerance = static_cast<uint32_t>(parse_u64(value()));
        } else if (name == "--texture-slot") {
            options.textures = {{
                static_cast<uint32_t>(parse_u64(value())), TextureKind::two_d, 1}};
        } else if (name == "--texture-slots") {
            options.textures.clear();
            std::stringstream slots(value());
            std::string slot;
            while (std::getline(slots, slot, ',')) {
                options.textures.push_back({
                    static_cast<uint32_t>(parse_u64(slot)), TextureKind::two_d, 1});
            }
        } else if (name == "--textures") {
            options.textures.clear();
            std::stringstream bindings(value());
            std::string binding;
            while (std::getline(bindings, binding, ',')) {
                const size_t first = binding.find(':');
                if (first == std::string::npos) {
                    throw std::runtime_error("textures must use slot:kind");
                }
                const size_t second = binding.find(':', first + 1);
                const size_t third = second == std::string::npos
                    ? std::string::npos
                    : binding.find(':', second + 1);
                const std::string kind = binding.substr(
                    first + 1,
                    second == std::string::npos
                        ? std::string::npos
                        : second - first - 1);
                options.textures.push_back({
                    static_cast<uint32_t>(parse_u64(binding.substr(0, first))),
                    parse_texture_kind(kind),
                    second == std::string::npos
                        ? 1u
                        : static_cast<uint32_t>(parse_u64(binding.substr(
                            second + 1,
                            third == std::string::npos
                                ? std::string::npos
                                : third - second - 1))),
                    third == std::string::npos
                        ? 0u
                        : static_cast<uint32_t>(parse_u64(binding.substr(third + 1))),
                });
            }
        } else if (name == "--structured-inputs") {
            options.structured_inputs.clear();
            std::stringstream bindings(value());
            std::string binding;
            while (std::getline(bindings, binding, ',')) {
                const size_t first = binding.find(':');
                const size_t second = binding.find(':', first + 1);
                const size_t third = second == std::string::npos
                    ? std::string::npos
                    : binding.find(':', second + 1);
                if (first == std::string::npos) {
                    throw std::runtime_error(
                        "structured inputs must use slot:elements[:stride]");
                }
                options.structured_inputs.push_back({
                    static_cast<uint32_t>(parse_u64(binding.substr(0, first))),
                    static_cast<uint32_t>(parse_u64(binding.substr(
                        first + 1, second == std::string::npos
                            ? std::string::npos : second - first - 1))),
                    second == std::string::npos ? 4u : static_cast<uint32_t>(
                        parse_u64(binding.substr(
                            second + 1, third == std::string::npos
                                ? std::string::npos : third - second - 1))),
                    third != std::string::npos && binding.substr(third + 1) == "zero"
                        ? StructuredInputProfile::zero
                        : StructuredInputProfile::random,
                });
            }
        } else if (name == "--smooth-texture-slots") {
            options.smooth_texture_slots.clear();
            std::stringstream slots(value());
            std::string slot;
            while (std::getline(slots, slot, ',')) {
                if (!slot.empty()) {
                    options.smooth_texture_slots.push_back(
                        static_cast<uint32_t>(parse_u64(slot)));
                }
            }
        } else if (name == "--monochrome-texture-slots") {
            options.monochrome_texture_slots.clear();
            std::stringstream slots(value());
            std::string slot;
            while (std::getline(slots, slot, ',')) {
                if (!slot.empty()) {
                    options.monochrome_texture_slots.push_back(
                        static_cast<uint32_t>(parse_u64(slot)));
                }
            }
        } else if (name == "--structured-output-elements") {
            options.structured_output_elements =
                static_cast<uint32_t>(parse_u64(value()));
        } else if (name == "--structured-output-stride") {
            options.structured_output_stride =
                static_cast<uint32_t>(parse_u64(value()));
        } else if (name == "--structured-outputs") {
            options.structured_outputs.clear();
            std::stringstream bindings(value());
            std::string binding;
            while (std::getline(bindings, binding, ',')) {
                const size_t first = binding.find(':');
                const size_t second = binding.find(':', first + 1);
                const size_t third = binding.find(':', second + 1);
                if (first == std::string::npos || second == std::string::npos) {
                    throw std::runtime_error(
                        "structured outputs must use slot:elements:stride[:profile]");
                }
                options.structured_outputs.push_back({
                    static_cast<uint32_t>(parse_u64(binding.substr(0, first))),
                    static_cast<uint32_t>(parse_u64(binding.substr(
                        first + 1, second - first - 1))),
                    static_cast<uint32_t>(parse_u64(binding.substr(
                        second + 1, third == std::string::npos
                            ? std::string::npos : third - second - 1))),
                    third == std::string::npos
                        ? StructuredOutputProfile::zero
                        : parse_structured_output_profile(binding.substr(third + 1)),
                });
            }
        } else if (name == "--sampler-slot") {
            options.samplers.front().slot =
                static_cast<uint32_t>(parse_u64(value()));
        } else if (name == "--samplers") {
            options.samplers.clear();
            std::stringstream samplers(value());
            std::string sampler;
            while (std::getline(samplers, sampler, ',')) {
                const size_t separator = sampler.find(':');
                if (separator == std::string::npos) {
                    throw std::runtime_error(
                        "samplers must use slot:point[:comparison] or slot:linear[:comparison]");
                }
                const uint32_t slot = static_cast<uint32_t>(
                    parse_u64(sampler.substr(0, separator)));
                const size_t second = sampler.find(':', separator + 1);
                const std::string filter = sampler.substr(
                    separator + 1, second == std::string::npos
                        ? std::string::npos : second - separator - 1);
                if (filter != "point" && filter != "linear") {
                    throw std::runtime_error(
                        "sampler filter must be point or linear");
                }
                const bool comparison = second != std::string::npos
                    && sampler.substr(second + 1) == "comparison";
                if (second != std::string::npos && !comparison) {
                    throw std::runtime_error(
                        "sampler mode must be comparison");
                }
                options.samplers.push_back({slot, filter == "point", comparison});
            }
        } else if (name == "--constant-buffer-slot") {
            options.constant_buffers.front().slot =
                static_cast<uint32_t>(parse_u64(value()));
        } else if (name == "--constant-profile") {
            options.constant_buffers.front().profile =
                parse_constant_profile(value());
        } else if (name == "--constant-buffers") {
            options.constant_buffers.clear();
            std::stringstream bindings(value());
            std::string binding;
            while (std::getline(bindings, binding, ',')) {
                const size_t separator = binding.find(':');
                if (separator == std::string::npos) {
                    throw std::runtime_error(
                        "constant buffers must use slot:profile");
                }
                options.constant_buffers.push_back(
                    {
                        static_cast<uint32_t>(parse_u64(
                            binding.substr(0, separator))),
                        parse_constant_profile(binding.substr(separator + 1)),
                    });
            }
        } else if (name == "--filter") {
            const std::string filter = value();
            if (filter == "point") {
                options.samplers.front().point = true;
            } else if (filter != "linear") {
                throw std::runtime_error("filter must be point or linear");
            } else {
                options.samplers.front().point = false;
            }
        } else if (name == "--output") {
            const std::string output = value();
            if (output == "depth") {
                options.depth_output = true;
                options.output_components = 1;
            } else if (output != "color") {
                throw std::runtime_error("output must be color or depth");
            }
        } else if (name == "--output-components") {
            options.output_components = static_cast<uint32_t>(parse_u64(value()));
        } else if (name == "--output-targets") {
            options.output_targets = static_cast<uint32_t>(parse_u64(value()));
        } else if (name == "--texture-outputs") {
            options.texture_outputs = parse_u64(value()) != 0;
        } else if (name == "--output-target-components") {
            options.output_target_components.clear();
            std::stringstream components(value());
            std::string component;
            while (std::getline(components, component, ',')) {
                options.output_target_components.push_back(
                    static_cast<uint32_t>(parse_u64(component)));
            }
        } else if (name == "--thread-group") {
            std::stringstream values(value());
            std::string component;
            for (size_t component_index = 0; component_index < 3; ++component_index) {
                if (!std::getline(values, component, ',')) {
                    throw std::runtime_error("thread group must use x,y,z");
                }
                options.thread_group[component_index] =
                    static_cast<uint32_t>(parse_u64(component));
            }
            if (std::getline(values, component, ',')) {
                throw std::runtime_error("thread group must use x,y,z");
            }
        } else if (name == "--warp") {
            options.warp = true;
        } else {
            throw std::runtime_error("unknown argument: " + name);
        }
    }
    if ((options.stage == ShaderStage::pixel && options.vertex.empty())
        || options.baseline.empty() || options.candidate.empty()) {
        throw std::runtime_error(
            "--baseline and --candidate are required; pixel stage also needs --vertex");
    }
    if (options.width == 0 || options.height == 0 || options.cases == 0) {
        throw std::runtime_error("width, height, and cases must be positive");
    }
    if (options.dispatch_width == 0) options.dispatch_width = options.width;
    if (options.dispatch_height == 0) options.dispatch_height = options.height;
    if (options.output_components == 0 || options.output_components > 4
        || options.output_targets == 0 || options.output_targets > 8
        || std::any_of(
            options.thread_group.begin(), options.thread_group.end(),
            [](uint32_t value) { return value == 0; })) {
        throw std::runtime_error("output components and thread-group sizes must be positive");
    }
    if (options.output_target_components.empty()) {
        options.output_target_components.assign(
            options.output_targets, options.output_components);
    }
    if (options.output_target_components.size() != options.output_targets
        || std::any_of(
            options.output_target_components.begin(),
            options.output_target_components.end(),
            [](uint32_t value) { return value == 0 || value > 4; })) {
        throw std::runtime_error(
            "output target components must provide one 1..4 value per target");
    }
    if (options.stage == ShaderStage::compute && options.depth_output) {
        throw std::runtime_error("compute stage does not support depth output");
    }
    if (options.depth_output && options.output_targets != 1) {
        throw std::runtime_error("depth output requires one output target");
    }
    if (options.structured_output_elements > 0 && options.structured_outputs.empty()) {
        options.structured_outputs.push_back({
            0, options.structured_output_elements, options.structured_output_stride,
            StructuredOutputProfile::zero});
    }
    if (!options.structured_outputs.empty()
        && (options.stage != ShaderStage::compute || options.output_components != 1)) {
        throw std::runtime_error(
            "structured output requires compute stage and one output component");
    }
    if (options.width > 4096 || options.height > 4096) {
        throw std::runtime_error("texture dimensions must not exceed 4096");
    }
    if (std::any_of(
            options.textures.begin(), options.textures.end(),
            [](const TextureBinding& texture) {
                const uint32_t slices = texture_slices(texture);
                return texture.mip_levels == 0 || texture.mip_levels > 13
                    || slices == 0 || slices > 2048
                    || (texture.kind == TextureKind::two_d && slices != 1)
                    || (texture.kind == TextureKind::cube && slices != 6);
            })) {
        throw std::runtime_error("invalid texture mip count or slice count");
    }
    if (std::any_of(
            options.textures.begin(),
            options.textures.end(),
            [](const TextureBinding& texture) {
                return texture.slot >= D3D11_COMMONSHADER_INPUT_RESOURCE_SLOT_COUNT;
            })
        || std::any_of(
            options.structured_inputs.begin(),
            options.structured_inputs.end(),
            [](const StructuredInputBinding& input) {
                return input.slot >= D3D11_COMMONSHADER_INPUT_RESOURCE_SLOT_COUNT
                    || input.elements == 0 || input.stride == 0
                    || (input.stride & 3) != 0;
            })
        || std::any_of(
            options.structured_outputs.begin(),
            options.structured_outputs.end(),
            [](const StructuredOutputBinding& output) {
                return output.slot >= D3D11_PS_CS_UAV_REGISTER_COUNT
                    || output.elements == 0 || output.stride == 0
                    || (output.stride & 3) != 0;
            })
        || std::any_of(
            options.samplers.begin(),
            options.samplers.end(),
            [](const auto& sampler) {
                return sampler.slot >= D3D11_COMMONSHADER_SAMPLER_SLOT_COUNT;
            })
        || std::any_of(
            options.constant_buffers.begin(),
            options.constant_buffers.end(),
            [](const ConstantBinding& binding) {
                return binding.slot
                    >= D3D11_COMMONSHADER_CONSTANT_BUFFER_API_SLOT_COUNT;
            })) {
        throw std::runtime_error("resource binding slot is out of range");
    }
    if (options.structured_output_stride == 0
        || (options.structured_output_stride & 3) != 0) {
        throw std::runtime_error("structured output stride must be a positive multiple of four");
    }
    if (options.texture_outputs && std::any_of(
            options.structured_outputs.begin(), options.structured_outputs.end(),
            [&options](const StructuredOutputBinding& output) {
                return output.slot < options.output_targets;
            })) {
        throw std::runtime_error(
            "structured output slots must not overlap texture output slots");
    }
    return options;
}

std::string json_escape(const std::string& text) {
    std::ostringstream output;
    for (const unsigned char value : text) {
        switch (value) {
        case '\\': output << "\\\\"; break;
        case '"': output << "\\\""; break;
        case '\n': output << "\\n"; break;
        case '\r': output << "\\r"; break;
        case '\t': output << "\\t"; break;
        default:
            if (value < 0x20) {
                output << "\\u" << std::hex << std::setw(4) << std::setfill('0')
                       << static_cast<unsigned>(value) << std::dec;
            } else {
                output << static_cast<char>(value);
            }
        }
    }
    return output.str();
}

std::string feature_level_name(D3D_FEATURE_LEVEL level) {
    switch (level) {
    case D3D_FEATURE_LEVEL_11_1: return "11_1";
    case D3D_FEATURE_LEVEL_11_0: return "11_0";
    case D3D_FEATURE_LEVEL_10_1: return "10_1";
    case D3D_FEATURE_LEVEL_10_0: return "10_0";
    default: return "unknown";
    }
}

class Runner {
public:
    explicit Runner(const Options& options) : options_(options) {
        const std::array<D3D_FEATURE_LEVEL, 4> levels = {
            D3D_FEATURE_LEVEL_11_1,
            D3D_FEATURE_LEVEL_11_0,
            D3D_FEATURE_LEVEL_10_1,
            D3D_FEATURE_LEVEL_10_0,
        };
        check(
            D3D11CreateDevice(
                nullptr,
                options.warp ? D3D_DRIVER_TYPE_WARP : D3D_DRIVER_TYPE_HARDWARE,
                nullptr,
                0,
                levels.data(),
                static_cast<UINT>(levels.size()),
                D3D11_SDK_VERSION,
                &device_,
                &feature_level_,
                &context_),
            "D3D11CreateDevice");
        discover_adapter();
        create_pipeline();
    }

    const std::string& adapter_name() const { return adapter_name_; }
    D3D_FEATURE_LEVEL feature_level() const { return feature_level_; }

    void update_input(size_t index, const std::vector<float>& values) {
        const TextureBinding& binding = options_.textures.at(index);
        const TextureKind kind = binding.kind;
        const uint32_t mip_levels = binding.mip_levels;
        const UINT row_pitch = options_.width * 4 * sizeof(float);
        const UINT slice_pitch = row_pitch * options_.height;
        if (kind == TextureKind::three_d) {
            context_->UpdateSubresource(
                inputs_.at(index).Get(), 0, nullptr, values.data(),
                row_pitch, slice_pitch);
        } else {
            const uint32_t slices = texture_slices(binding);
            for (uint32_t slice = 0; slice < slices; ++slice) {
                context_->UpdateSubresource(
                    inputs_.at(index).Get(),
                    D3D11CalcSubresource(0, slice, mip_levels),
                    nullptr,
                    values.data()
                        + static_cast<size_t>(slice) * options_.width
                            * options_.height * 4,
                    row_pitch,
                    0);
            }
        }
        if (mip_levels > 1) {
            context_->GenerateMips(input_views_.at(index).Get());
        }
    }

    void update_structured_input(
        size_t index, const std::vector<uint32_t>& values) {
        context_->UpdateSubresource(
            structured_inputs_.at(index).Get(),
            0,
            nullptr,
            values.data(),
            0,
            0);
    }

    void update_constants(uint32_t case_index) {
        for (size_t index = 0; index < options_.constant_buffers.size(); ++index) {
            const auto constants = constant_values(
                options_.constant_buffers[index].profile, case_index);
            context_->UpdateSubresource(
                constant_buffers_[index].Get(),
                0,
                nullptr,
                constants.data(),
                0,
                0);
        }
    }

    void initialize_structured_outputs(uint32_t case_index) {
        for (size_t index = 0; index < options_.structured_outputs.size(); ++index) {
            const auto& binding = options_.structured_outputs[index];
            std::vector<uint32_t> values(
                static_cast<size_t>(binding.elements) * binding.stride / 4, 0);
            SplitMix64 random{
                options_.seed ^ (static_cast<uint64_t>(case_index) << 32)
                ^ (static_cast<uint64_t>(binding.slot) << 48)};
            if (binding.profile == StructuredOutputProfile::hdr_feedback) {
                for (size_t value = 0; value < std::min<size_t>(8, values.size()); ++value) {
                    values[value] = 1u + static_cast<uint32_t>(random.next() % 2048u);
                }
                if (values.size() >= 8) {
                    values[7] = 4u + static_cast<uint32_t>(random.next() % 252u);
                }
            } else if (binding.profile == StructuredOutputProfile::hdr_setting) {
                const auto set_float = [&](size_t value, float number) {
                    if (value < values.size()) {
                        std::memcpy(&values[value], &number, sizeof(number));
                    }
                };
                for (size_t value = 0; value < std::min<size_t>(20, values.size()); ++value) {
                    set_float(value, 0.05f + random.unit() * 0.9f);
                }
                set_float(13, 0.8f + random.unit() * 0.4f);
                set_float(18, 0.05f + random.unit() * 0.2f);
                set_float(19, 0.5f + random.unit() * 2.0f);
                for (size_t value = 20; value < std::min<size_t>(28, values.size()); ++value) {
                    set_float(value, 10.0f + random.unit() * 790.0f);
                }
            }
            context_->UpdateSubresource(
                structured_outputs_[index].Get(), 0, nullptr,
                values.data(), 0, 0);
        }
    }

    static constexpr size_t constant_register_count = 4096;

    std::array<float, constant_register_count * 4> constant_values(
        ConstantProfile profile, uint32_t case_index) const {
        std::array<float, constant_register_count * 4> constants{};
        if (profile == ConstantProfile::auto_hdr) {
            const uint32_t dispatch_count = 1u + case_index % 16u;
            std::memcpy(&constants[4], &dispatch_count, sizeof(dispatch_count));
        } else if (profile == ConstantProfile::index) {
            constants[0] = 0.0f;
        } else if (profile == ConstantProfile::fsr_easu) {
            const float width = static_cast<float>(options_.width);
            const float height = static_cast<float>(options_.height);
            constants[0] = 1.0f;
            constants[1] = 1.0f;
            constants[2] = 0.0f;
            constants[3] = 0.0f;
            constants[4] = 1.0f / width;
            constants[5] = 1.0f / height;
            constants[6] = 1.0f / width;
            constants[7] = -1.0f / height;
            constants[8] = -1.0f / width;
            constants[9] = 2.0f / height;
            constants[10] = 1.0f / width;
            constants[11] = 2.0f / height;
            constants[12] = 0.0f;
            constants[13] = 4.0f / height;
        } else if (profile == ConstantProfile::fsr_rcas) {
            constants[0] = std::exp2(-0.2f);
        } else if (profile == ConstantProfile::cluster) {
            const uint32_t slice_size = std::min(options_.width, 64u);
            const uint32_t depth_lights = 2;
            std::memcpy(&constants[1], &slice_size, sizeof(slice_size));
            std::memcpy(&constants[5], &depth_lights, sizeof(depth_lights));
        } else if (profile == ConstantProfile::ao) {
            constants[3 * 4 + 0] = 1.0f;
            constants[3 * 4 + 1] = 1.0f;
            constants[3 * 4 + 2] = 1.0f / static_cast<float>(options_.width);
            constants[3 * 4 + 3] = 1.0f / static_cast<float>(options_.height);
            std::memcpy(&constants[4 * 4 + 0], &options_.width, sizeof(options_.width));
            std::memcpy(&constants[4 * 4 + 1], &options_.height, sizeof(options_.height));
            constants[5 * 4 + 0] = 1.0f;
            constants[5 * 4 + 1] = 1.0f;
            constants[5 * 4 + 2] = 1.0f - 0.5f / static_cast<float>(options_.width);
            constants[5 * 4 + 3] = 1.0f - 0.5f / static_cast<float>(options_.height);
            constants[6 * 4 + 2] = 1.0f;
            constants[6 * 4 + 3] = 1.0f;
        } else if (profile == ConstantProfile::bloom) {
            SplitMix64 random{
                options_.seed ^ (static_cast<uint64_t>(case_index) << 32)};
            float* bloom = constants.data() + 570 * 4;
            bloom[0] = case_index == 0 ? 0.2f : random.unit() * 0.5f;
            bloom[1] = case_index == 0 ? 0.8f : bloom[0] + random.unit() * 1.5f;
            bloom[2] = case_index == 0 ? 0.1f : random.unit() * 0.5f;
            bloom[3] = case_index == 0 ? 0.8f : 0.05f + random.unit() * 2.0f;
            bloom[4] = case_index == 0 ? 1.0f : random.unit() * 4.0f;
            bloom[5] = case_index == 0 ? 2.0f : random.unit() * 6.0f;
            bloom[6] = case_index == 0 ? 0.01f : 0.0001f + random.unit() * 0.1f;
        } else if (profile == ConstantProfile::reflection) {
            SplitMix64 random{
                options_.seed ^ (static_cast<uint64_t>(case_index) << 32)};
            for (uint32_t probe = 0; probe < 128; ++probe) {
                float* record = constants.data() + probe * 40;
                for (uint32_t component = 0; component < 40; ++component) {
                    record[component] = random.unit() * 40.0f - 20.0f;
                }
                record[3] = case_index == 0 ? static_cast<float>(probe % 3)
                    : case_index == 1 ? static_cast<float>(3 + probe % 32)
                    : static_cast<float>((probe & 1) ? 3 + probe % 64 : probe % 3);
                record[4] = (probe % 5 == 0 ? 80.0f : 4.0f) + random.unit();
                record[5] = (probe % 7 == 0 ? 70.0f : 5.0f) + random.unit();
                record[6] = (probe % 11 == 0 ? 65.0f : 6.0f) + random.unit();
            }
        } else if (profile == ConstantProfile::rect) {
            SplitMix64 random{
                options_.seed ^ (static_cast<uint64_t>(case_index) << 32)};
            const float extent = static_cast<float>(
                std::max(1u, std::min(options_.width, options_.height) - 1));
            constants[0] = case_index == 0 ? 0.0f : random.unit() * 4.0f;
            constants[1] = constants[0];
            constants[2] = case_index == 1 ? 1.0f : extent - constants[0];
            constants[3] = constants[2];
        } else if (profile == ConstantProfile::hdr) {
            SplitMix64 random{
                options_.seed ^ (static_cast<uint64_t>(case_index) << 32)};
            constants[3 * 4 + 3] = case_index == 0
                ? 1.0f
                : 0.5f + random.unit() * 2.0f;
            constants[4 * 4 + 2] = case_index == 0
                ? 0.0f
                : random.unit() * 0.25f;
            constants[4 * 4 + 3] = case_index == 0
                ? 1.0f
                : 0.5f + random.unit() * 1.5f;
        } else if (profile == ConstantProfile::composition
                   || profile == ConstantProfile::composition_fog) {
            SplitMix64 random{
                options_.seed ^ (static_cast<uint64_t>(case_index) << 32)};
            if (case_index == 1) {
                constants.fill(1.0f);
            } else if (case_index > 1) {
                for (float& value : constants) value = random.unit();
            }
            for (uint32_t fog = 0; fog < 2; ++fog) {
                float* record = constants.data() + (64 + fog * 7) * 4;
                const bool colored = profile == ConstantProfile::composition_fog;
                for (uint32_t component = 0; component < 4; ++component) {
                    record[component] = colored ? random.unit() : 0.0f;
                    record[4 + component] = colored ? random.unit() : 0.0f;
                    record[12 + component] = colored ? random.unit() : 0.0f;
                    record[16 + component] = colored ? random.unit() : 0.0f;
                }
                record[8] = random.unit() * 20.0f;
                record[9] = 0.001f + random.unit() * 2.0f;
                record[10] = 0.05f + random.unit() * 4.0f;
                record[11] = 0.001f + random.unit() * 2.0f;
                record[20] = 0.001f + random.unit() * 2.0f;
                record[21] = 0.05f + random.unit() * 4.0f;
                record[22] = random.unit() * 20.0f;
                record[23] = 0.001f + random.unit() * 2.0f;
            }
        } else if (profile == ConstantProfile::cluster_culling) {
            const uint32_t first_light = 0;
            const uint32_t one_light = 1;
            std::memcpy(&constants[4], &first_light, sizeof(first_light));
            std::memcpy(&constants[5], &one_light, sizeof(one_light));
            constants[90 * 4 + 0] = 0.0f;
            constants[90 * 4 + 1] = 0.0f;
            constants[90 * 4 + 2] = 0.0f;
            constants[90 * 4 + 3] = 1.0e12f;
        } else if (profile == ConstantProfile::hzb) {
            const uint32_t max_pixel_x = options_.width - 1;
            const uint32_t max_pixel_y = options_.height - 1;
            const uint32_t dispatch_count = case_index + 1;
            std::memcpy(&constants[0], &max_pixel_x, sizeof(max_pixel_x));
            std::memcpy(&constants[1], &max_pixel_y, sizeof(max_pixel_y));
            std::memcpy(&constants[2], &max_pixel_x, sizeof(max_pixel_x));
            std::memcpy(&constants[3], &max_pixel_y, sizeof(max_pixel_y));
            std::memcpy(&constants[4], &dispatch_count, sizeof(dispatch_count));
        } else if (profile == ConstantProfile::cloud) {
            SplitMix64 random{
                options_.seed ^ (static_cast<uint64_t>(case_index) << 32)};
            for (float& value : constants) {
                value = 0.05f + random.unit() * 0.9f;
            }
            constants[1 * 4 + 0] = 0.0f;
            constants[1 * 4 + 1] = 0.0f;
            constants[1 * 4 + 2] = 1.0f;
            constants[3 * 4 + 0] = 1.0f;
            constants[3 * 4 + 1] = 0.95f;
            constants[3 * 4 + 2] = 0.9f;
            constants[3 * 4 + 3] = 1.0f;
            constants[7 * 4 + 0] = 0.016f;
            constants[7 * 4 + 1] = random.unit();
            constants[7 * 4 + 3] = 0.016f;
            constants[8 * 4 + 3] = random.unit();
            constants[11 * 4 + 3] = -10000.0f;

            float* cloud = constants.data() + 78 * 4;
            cloud[3] = 35000000.0f;
            cloud[7] = 0.25f + random.unit() * 0.45f;
            cloud[11] = 6000.0f;
            cloud[12] = 0.0f;
            cloud[13] = 0.0f;
            cloud[14] = 1.0f;
            cloud[15] = 100.0f + random.unit() * 300.0f;
            cloud[19] = 36000000.0f;
            cloud[23] = 5000.0f;
            cloud[24] = random.unit();
            const uint32_t max_depth_x = options_.width - 1;
            const uint32_t max_depth_y = options_.height - 1;
            std::memcpy(&cloud[28], &max_depth_x, sizeof(max_depth_x));
            std::memcpy(&cloud[29], &max_depth_y, sizeof(max_depth_y));
            cloud[30] = 0.5f;
            cloud[31] = 0.001f;
            for (uint32_t matrix = 0; matrix < 2; ++matrix) {
                float* rotation = cloud + 32 + matrix * 12;
                std::fill(rotation, rotation + 12, 0.0f);
                rotation[0] = 1.0f;
                rotation[5] = 1.0f;
                rotation[10] = 1.0f;
            }
        } else if (profile == ConstantProfile::random && case_index == 1) {
            constants.fill(1.0f);
        } else if (profile == ConstantProfile::random && case_index > 1) {
            SplitMix64 random{
                options_.seed ^ (static_cast<uint64_t>(case_index) << 32)};
            for (float& value : constants) {
                value = random.unit() * 4.0f - 2.0f;
            }
        } else if (profile == ConstantProfile::projection) {
            for (uint32_t matrix_register = 0; matrix_register <= 44;
                 matrix_register += 4) {
                constants[(matrix_register + 0) * 4 + 0] = 1.0f;
                constants[(matrix_register + 1) * 4 + 1] = 1.0f;
                constants[(matrix_register + 2) * 4 + 2] = 1.0f;
                constants[(matrix_register + 3) * 4 + 3] = 1.0f;
            }
            constants[2 * 4 + 2] = -2.0f;
            constants[3 * 4 + 2] = -1.0f;
            constants[49 * 4 + 2] = 1.0f;
            constants[49 * 4 + 3] = 1.0f;
            constants[49 * 4 + 1] = 500.0f;
            std::memcpy(
                &constants[51 * 4], &options_.width, sizeof(options_.width));
            std::memcpy(
                &constants[51 * 4 + 1],
                &options_.height,
                sizeof(options_.height));
            constants[51 * 4 + 2] = 1.0f / static_cast<float>(options_.width);
            constants[51 * 4 + 3] = 1.0f / static_cast<float>(options_.height);
            constants[52 * 4] = 1.0f / static_cast<float>(options_.width);
            constants[52 * 4 + 1] = 1.0f / static_cast<float>(options_.height);
            constants[52 * 4 + 2] = 1.0f / static_cast<float>(options_.width);
            constants[52 * 4 + 3] = 1.0f / static_cast<float>(options_.height);
            constants[53 * 4] = 1.0f;
            constants[53 * 4 + 1] = 1.0f;
            constants[54 * 4] =
                1.0f - 0.5f / static_cast<float>(options_.width);
            constants[54 * 4 + 1] =
                1.0f - 0.5f / static_cast<float>(options_.height);
            constants[54 * 4 + 2] = constants[54 * 4];
            constants[54 * 4 + 3] = constants[54 * 4 + 1];
            constants[55 * 4] = constants[54 * 4];
            constants[55 * 4 + 1] = constants[54 * 4 + 1];
            constants[56 * 4] = 1.0f;
            constants[56 * 4 + 1] = 1.0f;
            constants[60 * 4] = 1.0f;
            constants[60 * 4 + 1] = 1.0f;
        }
        return constants;
    }

    std::vector<float> render(bool candidate) {
        constexpr float clear[4] = {0.0f, 0.0f, 0.0f, 0.0f};
        if (options_.stage == ShaderStage::compute) {
            for (const auto& view : compute_views_) {
                context_->ClearUnorderedAccessViewFloat(view.Get(), clear);
            }
            std::vector<ID3D11UnorderedAccessView*> views;
            uint32_t count = static_cast<uint32_t>(compute_views_.size());
            if (!options_.structured_outputs.empty()) {
                count = std::max(count, 1 + std::max_element(
                    options_.structured_outputs.begin(),
                    options_.structured_outputs.end(),
                    [](const auto& left, const auto& right) {
                        return left.slot < right.slot;
                    })->slot);
            }
            views.resize(count, nullptr);
            for (size_t index = 0; index < compute_views_.size(); ++index) {
                views[index] = compute_views_[index].Get();
            }
            if (!options_.structured_outputs.empty()) {
                for (size_t index = 0; index < options_.structured_outputs.size(); ++index) {
                    views[options_.structured_outputs[index].slot] =
                        structured_output_views_[index].Get();
                }
            }
            context_->CSSetUnorderedAccessViews(
                0, static_cast<UINT>(views.size()), views.data(), nullptr);
            context_->CSSetShader(
                candidate ? candidate_compute_shader_.Get()
                          : baseline_compute_shader_.Get(),
                nullptr,
                0);
            context_->Dispatch(
                (options_.dispatch_width + options_.thread_group[0] - 1)
                    / options_.thread_group[0],
                (options_.dispatch_height + options_.thread_group[1] - 1)
                    / options_.thread_group[1],
                1);
            std::vector<ID3D11UnorderedAccessView*> no_views(views.size(), nullptr);
            context_->CSSetUnorderedAccessViews(
                0, static_cast<UINT>(no_views.size()), no_views.data(), nullptr);
        } else if (options_.depth_output) {
            context_->ClearDepthStencilView(
                depth_view_.Get(), D3D11_CLEAR_DEPTH, 0.0f, 0);
        } else {
            for (const auto& view : render_target_views_) {
                context_->ClearRenderTargetView(view.Get(), clear);
            }
        }
        if (options_.stage == ShaderStage::pixel) {
            context_->PSSetShader(
                candidate ? candidate_shader_.Get() : baseline_shader_.Get(),
                nullptr,
                0);
            context_->Draw(3, 0);
        }
        if (!options_.depth_output) {
            std::vector<float> output;
            const auto& targets = options_.stage == ShaderStage::compute
                ? compute_targets_ : render_targets_;
            for (size_t target = 0; target < targets.size(); ++target) {
                context_->CopyResource(staging_targets_[target].Get(), targets[target].Get());
                D3D11_MAPPED_SUBRESOURCE mapped{};
                check(context_->Map(
                    staging_targets_[target].Get(), 0, D3D11_MAP_READ, 0, &mapped),
                    "Map color output");
                const size_t components =
                    options_.output_target_components[target];
                const size_t old_size = output.size();
                output.resize(old_size + static_cast<size_t>(options_.width)
                    * options_.height * components);
                const size_t row_size = static_cast<size_t>(options_.width)
                    * components * sizeof(float);
                for (uint32_t y = 0; y < options_.height; ++y) {
                    if (components == 3) {
                        const float* source = reinterpret_cast<const float*>(
                            static_cast<const uint8_t*>(mapped.pData)
                                + y * mapped.RowPitch);
                        float* destination = output.data() + old_size
                            + static_cast<size_t>(y) * options_.width * 3;
                        for (uint32_t x = 0; x < options_.width; ++x) {
                            std::memcpy(destination + x * 3, source + x * 4,
                                3 * sizeof(float));
                        }
                    } else {
                        std::memcpy(
                            reinterpret_cast<uint8_t*>(output.data() + old_size)
                                + y * row_size,
                            static_cast<const uint8_t*>(mapped.pData)
                                + y * mapped.RowPitch,
                            row_size);
                    }
                }
                context_->Unmap(staging_targets_[target].Get(), 0);
            }
            for (size_t index = 0; index < options_.structured_outputs.size(); ++index) {
                context_->CopyResource(
                    structured_stagings_[index].Get(), structured_outputs_[index].Get());
                D3D11_MAPPED_SUBRESOURCE mapped{};
                check(context_->Map(
                    structured_stagings_[index].Get(), 0, D3D11_MAP_READ, 0, &mapped),
                    "Map structured output");
                const auto& binding = options_.structured_outputs[index];
                const size_t value_count = static_cast<size_t>(binding.elements)
                    * binding.stride / sizeof(float);
                const size_t old_size = output.size();
                output.resize(old_size + value_count);
                std::memcpy(
                    output.data() + old_size, mapped.pData,
                    value_count * sizeof(float));
                context_->Unmap(structured_stagings_[index].Get(), 0);
            }
            return output;
        }
        ID3D11Resource* staging_resource =
            static_cast<ID3D11Resource*>(staging_.Get());
        ID3D11Resource* output_resource =
            static_cast<ID3D11Resource*>(depth_target_.Get());
        context_->CopyResource(staging_resource, output_resource);

        D3D11_MAPPED_SUBRESOURCE mapped{};
        check(context_->Map(staging_resource, 0, D3D11_MAP_READ, 0, &mapped), "Map output");
        const size_t components = options_.output_components;
        std::vector<float> output(
            static_cast<size_t>(options_.width) * options_.height * components);
        const size_t row_size =
            static_cast<size_t>(options_.width) * components * sizeof(float);
        for (uint32_t y = 0; y < options_.height; ++y) {
            std::memcpy(
                reinterpret_cast<uint8_t*>(output.data()) + y * row_size,
                static_cast<const uint8_t*>(mapped.pData) + y * mapped.RowPitch,
                row_size);
        }
        context_->Unmap(staging_resource, 0);
        return output;
    }

private:
    static DXGI_FORMAT output_format(uint32_t components) {
        switch (components) {
        case 1: return DXGI_FORMAT_R32_FLOAT;
        case 2: return DXGI_FORMAT_R32G32_FLOAT;
        // D3D11 does not permit R32G32B32_FLOAT render targets/UAVs. Store an
        // unused alpha channel and compact it during readback.
        case 3: return DXGI_FORMAT_R32G32B32A32_FLOAT;
        case 4: return DXGI_FORMAT_R32G32B32A32_FLOAT;
        default: throw std::runtime_error("invalid output component count");
        }
    }
    void discover_adapter() {
        ComPtr<IDXGIDevice> dxgi_device;
        check(device_.As(&dxgi_device), "query IDXGIDevice");
        ComPtr<IDXGIAdapter> adapter;
        check(dxgi_device->GetAdapter(&adapter), "GetAdapter");
        DXGI_ADAPTER_DESC description{};
        check(adapter->GetDesc(&description), "GetDesc");
        const int required = WideCharToMultiByte(
            CP_UTF8, 0, description.Description, -1, nullptr, 0, nullptr, nullptr);
        if (required > 1) {
            std::string utf8(static_cast<size_t>(required), '\0');
            WideCharToMultiByte(
                CP_UTF8,
                0,
                description.Description,
                -1,
                utf8.data(),
                required,
                nullptr,
                nullptr);
            utf8.pop_back();
            adapter_name_ = utf8;
        }
    }

    ComPtr<ID3D11Texture2D> create_texture(
        D3D11_USAGE usage,
        UINT bind_flags,
        UINT cpu_flags,
        DXGI_FORMAT format = DXGI_FORMAT_R32G32B32A32_FLOAT) {
        D3D11_TEXTURE2D_DESC description{};
        description.Width = options_.width;
        description.Height = options_.height;
        description.MipLevels = 1;
        description.ArraySize = 1;
        description.Format = format;
        description.SampleDesc.Count = 1;
        description.Usage = usage;
        description.BindFlags = bind_flags;
        description.CPUAccessFlags = cpu_flags;
        ComPtr<ID3D11Texture2D> texture;
        check(device_->CreateTexture2D(&description, nullptr, &texture), "CreateTexture2D");
        return texture;
    }

    ComPtr<ID3D11Resource> create_input_texture(const TextureBinding& binding) {
        const TextureKind kind = binding.kind;
        const UINT bind_flags = D3D11_BIND_SHADER_RESOURCE
            | (binding.mip_levels > 1 ? D3D11_BIND_RENDER_TARGET : 0);
        const UINT generate_mips = binding.mip_levels > 1
            ? D3D11_RESOURCE_MISC_GENERATE_MIPS
            : 0;
        if (kind == TextureKind::three_d) {
            D3D11_TEXTURE3D_DESC description{};
            description.Width = options_.width;
            description.Height = options_.height;
            description.Depth = texture_slices(binding);
            description.MipLevels = binding.mip_levels;
            description.Format = DXGI_FORMAT_R32G32B32A32_FLOAT;
            description.Usage = D3D11_USAGE_DEFAULT;
            description.BindFlags = bind_flags;
            description.MiscFlags = generate_mips;
            ComPtr<ID3D11Texture3D> texture;
            check(device_->CreateTexture3D(&description, nullptr, &texture), "CreateTexture3D");
            ComPtr<ID3D11Resource> resource;
            check(texture.As(&resource), "query Texture3D resource");
            return resource;
        }

        D3D11_TEXTURE2D_DESC description{};
        description.Width = options_.width;
        description.Height = options_.height;
        description.MipLevels = binding.mip_levels;
        description.ArraySize = texture_slices(binding);
        description.Format = DXGI_FORMAT_R32G32B32A32_FLOAT;
        description.SampleDesc.Count = 1;
        description.Usage = D3D11_USAGE_DEFAULT;
        description.BindFlags = bind_flags;
        description.MiscFlags = generate_mips;
        if (kind == TextureKind::cube) {
            description.MiscFlags |= D3D11_RESOURCE_MISC_TEXTURECUBE;
        }
        ComPtr<ID3D11Texture2D> texture;
        check(device_->CreateTexture2D(&description, nullptr, &texture), "Create input Texture2D");
        ComPtr<ID3D11Resource> resource;
        check(texture.As(&resource), "query Texture2D resource");
        return resource;
    }

    ComPtr<ID3D11Buffer> create_structured_buffer(
        uint32_t elements, uint32_t stride, D3D11_USAGE usage,
        UINT bind_flags, UINT cpu_flags) {
        D3D11_BUFFER_DESC description{};
        description.ByteWidth = elements * stride;
        description.Usage = usage;
        description.BindFlags = bind_flags;
        description.CPUAccessFlags = cpu_flags;
        description.MiscFlags = D3D11_RESOURCE_MISC_BUFFER_STRUCTURED;
        description.StructureByteStride = stride;
        ComPtr<ID3D11Buffer> buffer;
        check(device_->CreateBuffer(&description, nullptr, &buffer), "Create structured buffer");
        return buffer;
    }

    void create_pipeline() {
        const auto baseline = read_binary(options_.baseline);
        const auto candidate = read_binary(options_.candidate);
        if (options_.stage == ShaderStage::compute) {
            check(
                device_->CreateComputeShader(
                    baseline.data(), baseline.size(), nullptr,
                    &baseline_compute_shader_),
                "CreateComputeShader baseline");
            check(
                device_->CreateComputeShader(
                    candidate.data(), candidate.size(), nullptr,
                    &candidate_compute_shader_),
                "CreateComputeShader candidate");
        } else {
            const auto vertex = read_binary(options_.vertex);
            check(
                device_->CreateVertexShader(
                    vertex.data(), vertex.size(), nullptr, &vertex_shader_),
                "CreateVertexShader");
            check(
                device_->CreatePixelShader(
                    baseline.data(), baseline.size(), nullptr, &baseline_shader_),
                "CreatePixelShader baseline");
            check(
                device_->CreatePixelShader(
                    candidate.data(), candidate.size(), nullptr, &candidate_shader_),
                "CreatePixelShader candidate");
        }

        for (const TextureBinding& binding : options_.textures) {
            inputs_.push_back(create_input_texture(binding));
            ComPtr<ID3D11ShaderResourceView> view;
            check(
                device_->CreateShaderResourceView(
                    inputs_.back().Get(), nullptr, &view),
                "CreateShaderResourceView");
            input_views_.push_back(std::move(view));
        }
        for (const StructuredInputBinding& binding : options_.structured_inputs) {
            structured_inputs_.push_back(create_structured_buffer(
                binding.elements,
                binding.stride,
                D3D11_USAGE_DEFAULT,
                D3D11_BIND_SHADER_RESOURCE,
                0));
            ComPtr<ID3D11ShaderResourceView> view;
            check(
                device_->CreateShaderResourceView(
                    structured_inputs_.back().Get(), nullptr, &view),
                "Create structured ShaderResourceView");
            structured_input_views_.push_back(std::move(view));
        }
        if (options_.stage == ShaderStage::compute) {
            for (const auto& binding : options_.structured_outputs) {
                structured_outputs_.push_back(create_structured_buffer(
                    binding.elements, binding.stride, D3D11_USAGE_DEFAULT,
                    D3D11_BIND_UNORDERED_ACCESS, 0));
                structured_stagings_.push_back(create_structured_buffer(
                    binding.elements, binding.stride, D3D11_USAGE_STAGING,
                    0, D3D11_CPU_ACCESS_READ));
                ComPtr<ID3D11UnorderedAccessView> view;
                check(device_->CreateUnorderedAccessView(
                    structured_outputs_.back().Get(), nullptr, &view),
                    "Create structured UnorderedAccessView");
                structured_output_views_.push_back(std::move(view));
            }
            if (options_.texture_outputs) {
                for (uint32_t index = 0; index < options_.output_targets; ++index) {
                    compute_targets_.push_back(create_texture(
                        D3D11_USAGE_DEFAULT, D3D11_BIND_UNORDERED_ACCESS, 0,
                        output_format(options_.output_target_components[index])));
                    staging_targets_.push_back(create_texture(
                        D3D11_USAGE_STAGING, 0, D3D11_CPU_ACCESS_READ,
                        output_format(options_.output_target_components[index])));
                    ComPtr<ID3D11UnorderedAccessView> view;
                    check(device_->CreateUnorderedAccessView(
                        compute_targets_.back().Get(), nullptr, &view),
                        "CreateUnorderedAccessView");
                    compute_views_.push_back(std::move(view));
                }
            }
        } else if (options_.depth_output) {
            depth_target_ = create_texture(
                D3D11_USAGE_DEFAULT,
                D3D11_BIND_DEPTH_STENCIL,
                0,
                DXGI_FORMAT_D32_FLOAT);
            staging_ = create_texture(
                D3D11_USAGE_STAGING,
                0,
                D3D11_CPU_ACCESS_READ,
                DXGI_FORMAT_D32_FLOAT);
            check(
                device_->CreateDepthStencilView(
                    depth_target_.Get(), nullptr, &depth_view_),
                "CreateDepthStencilView");
        } else {
            for (uint32_t index = 0; index < options_.output_targets; ++index) {
                render_targets_.push_back(create_texture(
                    D3D11_USAGE_DEFAULT, D3D11_BIND_RENDER_TARGET, 0,
                    output_format(options_.output_target_components[index])));
                staging_targets_.push_back(create_texture(
                    D3D11_USAGE_STAGING, 0, D3D11_CPU_ACCESS_READ,
                    output_format(options_.output_target_components[index])));
                ComPtr<ID3D11RenderTargetView> view;
                check(device_->CreateRenderTargetView(
                    render_targets_.back().Get(), nullptr, &view),
                    "CreateRenderTargetView");
                render_target_views_.push_back(std::move(view));
            }
        }

        D3D11_BUFFER_DESC buffer_description{};
        buffer_description.ByteWidth = constant_register_count * 16;
        buffer_description.Usage = D3D11_USAGE_DEFAULT;
        buffer_description.BindFlags = D3D11_BIND_CONSTANT_BUFFER;
        for (const ConstantBinding& binding : options_.constant_buffers) {
            const auto constants = constant_values(binding.profile, 0);
            D3D11_SUBRESOURCE_DATA buffer_data{};
            buffer_data.pSysMem = constants.data();
            ComPtr<ID3D11Buffer> buffer;
            check(
                device_->CreateBuffer(
                    &buffer_description, &buffer_data, &buffer),
                "CreateBuffer");
            constant_buffers_.push_back(std::move(buffer));
        }

        for (const SamplerBinding& binding : options_.samplers) {
            D3D11_SAMPLER_DESC sampler_description{};
            sampler_description.Filter = binding.comparison
                ? (binding.point
                    ? D3D11_FILTER_COMPARISON_MIN_MAG_MIP_POINT
                    : D3D11_FILTER_COMPARISON_MIN_MAG_MIP_LINEAR)
                : (binding.point
                    ? D3D11_FILTER_MIN_MAG_MIP_POINT
                    : D3D11_FILTER_MIN_MAG_MIP_LINEAR);
            sampler_description.AddressU = D3D11_TEXTURE_ADDRESS_CLAMP;
            sampler_description.AddressV = D3D11_TEXTURE_ADDRESS_CLAMP;
            sampler_description.AddressW = D3D11_TEXTURE_ADDRESS_CLAMP;
            sampler_description.MaxLOD = D3D11_FLOAT32_MAX;
            sampler_description.ComparisonFunc = D3D11_COMPARISON_LESS_EQUAL;
            ComPtr<ID3D11SamplerState> sampler;
            check(
                device_->CreateSamplerState(&sampler_description, &sampler),
                "CreateSamplerState");
            samplers_.push_back(std::move(sampler));
        }

        D3D11_RASTERIZER_DESC rasterizer_description{};
        rasterizer_description.FillMode = D3D11_FILL_SOLID;
        rasterizer_description.CullMode = D3D11_CULL_NONE;
        rasterizer_description.DepthClipEnable = TRUE;
        check(
            device_->CreateRasterizerState(
                &rasterizer_description, &rasterizer_state_),
            "CreateRasterizerState");

        if (options_.depth_output) {
            D3D11_DEPTH_STENCIL_DESC depth_description{};
            depth_description.DepthEnable = TRUE;
            depth_description.DepthWriteMask = D3D11_DEPTH_WRITE_MASK_ALL;
            depth_description.DepthFunc = D3D11_COMPARISON_ALWAYS;
            check(
                device_->CreateDepthStencilState(
                    &depth_description, &depth_state_),
                "CreateDepthStencilState");
        }

        D3D11_VIEWPORT viewport{};
        viewport.Width = static_cast<float>(options_.width);
        viewport.Height = static_cast<float>(options_.height);
        viewport.MaxDepth = 1.0f;
        if (options_.stage == ShaderStage::pixel) {
            context_->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
            context_->VSSetShader(vertex_shader_.Get(), nullptr, 0);
        }
        for (size_t index = 0; index < options_.constant_buffers.size(); ++index) {
            ID3D11Buffer* constant_buffer = constant_buffers_[index].Get();
            context_->VSSetConstantBuffers(
                options_.constant_buffers[index].slot, 1, &constant_buffer);
            context_->PSSetConstantBuffers(
                options_.constant_buffers[index].slot, 1, &constant_buffer);
            context_->CSSetConstantBuffers(
                options_.constant_buffers[index].slot, 1, &constant_buffer);
        }
        for (size_t index = 0; index < options_.textures.size(); ++index) {
            ID3D11ShaderResourceView* input_view = input_views_[index].Get();
            context_->PSSetShaderResources(
                options_.textures[index].slot, 1, &input_view);
            context_->CSSetShaderResources(
                options_.textures[index].slot, 1, &input_view);
        }
        for (size_t index = 0; index < options_.structured_inputs.size(); ++index) {
            ID3D11ShaderResourceView* input_view =
                structured_input_views_[index].Get();
            context_->CSSetShaderResources(
                options_.structured_inputs[index].slot, 1, &input_view);
        }
        for (size_t index = 0; index < options_.samplers.size(); ++index) {
            ID3D11SamplerState* sampler = samplers_[index].Get();
            context_->PSSetSamplers(
                options_.samplers[index].slot, 1, &sampler);
            context_->CSSetSamplers(
                options_.samplers[index].slot, 1, &sampler);
        }
        if (options_.stage == ShaderStage::compute) {
            return;
        }
        context_->RSSetState(rasterizer_state_.Get());
        context_->RSSetViewports(1, &viewport);
        if (options_.depth_output) {
            context_->OMSetDepthStencilState(depth_state_.Get(), 0);
            context_->OMSetRenderTargets(0, nullptr, depth_view_.Get());
        } else {
            std::vector<ID3D11RenderTargetView*> targets;
            for (const auto& target : render_target_views_) targets.push_back(target.Get());
            context_->OMSetRenderTargets(
                static_cast<UINT>(targets.size()), targets.data(), nullptr);
        }
    }

    const Options& options_;
    ComPtr<ID3D11Device> device_;
    ComPtr<ID3D11DeviceContext> context_;
    D3D_FEATURE_LEVEL feature_level_{};
    std::string adapter_name_;
    ComPtr<ID3D11VertexShader> vertex_shader_;
    ComPtr<ID3D11PixelShader> baseline_shader_;
    ComPtr<ID3D11PixelShader> candidate_shader_;
    ComPtr<ID3D11ComputeShader> baseline_compute_shader_;
    ComPtr<ID3D11ComputeShader> candidate_compute_shader_;
    std::vector<ComPtr<ID3D11Resource>> inputs_;
    std::vector<ComPtr<ID3D11Buffer>> structured_inputs_;
    std::vector<ComPtr<ID3D11Texture2D>> render_targets_;
    ComPtr<ID3D11Texture2D> depth_target_;
    std::vector<ComPtr<ID3D11Texture2D>> compute_targets_;
    std::vector<ComPtr<ID3D11Buffer>> structured_outputs_;
    std::vector<ComPtr<ID3D11Buffer>> structured_stagings_;
    ComPtr<ID3D11Texture2D> staging_;
    std::vector<ComPtr<ID3D11Texture2D>> staging_targets_;
    std::vector<ComPtr<ID3D11ShaderResourceView>> input_views_;
    std::vector<ComPtr<ID3D11ShaderResourceView>> structured_input_views_;
    std::vector<ComPtr<ID3D11RenderTargetView>> render_target_views_;
    ComPtr<ID3D11DepthStencilView> depth_view_;
    std::vector<ComPtr<ID3D11UnorderedAccessView>> structured_output_views_;
    std::vector<ComPtr<ID3D11UnorderedAccessView>> compute_views_;
    std::vector<ComPtr<ID3D11Buffer>> constant_buffers_;
    std::vector<ComPtr<ID3D11SamplerState>> samplers_;
    ComPtr<ID3D11RasterizerState> rasterizer_state_;
    ComPtr<ID3D11DepthStencilState> depth_state_;
};

std::string fill_case(
    std::vector<float>& pixels,
    uint32_t case_index,
    uint32_t width,
    uint32_t height,
    SplitMix64& random) {
    const auto write = [&](uint32_t x, uint32_t y, float r, float g, float b, float a) {
        const size_t offset = (static_cast<size_t>(y) * width + x) * 4;
        pixels[offset] = r;
        pixels[offset + 1] = g;
        pixels[offset + 2] = b;
        pixels[offset + 3] = a;
    };
    const uint32_t pattern = case_index < 8 ? case_index : 8 + (case_index % 3);
    for (uint32_t y = 0; y < height; ++y) {
        for (uint32_t x = 0; x < width; ++x) {
            float r = 0.0f;
            float g = 0.0f;
            float b = 0.0f;
            float a = 1.0f;
            switch (pattern) {
            case 0:
                r = g = b = 0.0f;
                break;
            case 1:
                r = g = b = 1.0f;
                a = 0.25f;
                break;
            case 2:
                r = g = b = x < width / 2 ? 0.0f : 1.0f;
                break;
            case 3:
                r = g = b = y < height / 2 ? 0.0f : 1.0f;
                break;
            case 4:
                r = g = b = x > y ? 1.0f : 0.0f;
                break;
            case 5:
                r = g = b = ((x ^ y) & 1u) ? 1.0f : 0.0f;
                break;
            case 6:
                r = g = b = (x == width / 2 && y == height / 2) ? 1.0f : 0.0f;
                break;
            case 7:
                r = static_cast<float>(x) / static_cast<float>(std::max(1u, width - 1));
                g = static_cast<float>(y) / static_cast<float>(std::max(1u, height - 1));
                b = 1.0f - r;
                a = g;
                break;
            case 8:
                r = random.unit();
                g = random.unit();
                b = random.unit();
                a = random.unit();
                break;
            case 9:
                r = random.unit() * 20.0f - 4.0f;
                g = random.unit() * 20.0f - 4.0f;
                b = random.unit() * 20.0f - 4.0f;
                a = random.unit() * 4.0f;
                break;
            default:
                r = static_cast<float>(x) / static_cast<float>(std::max(1u, width - 1));
                g = static_cast<float>(y) / static_cast<float>(std::max(1u, height - 1));
                b = 0.5f * (r + g);
                r += (random.unit() - 0.5f) * 0.02f;
                g += (random.unit() - 0.5f) * 0.02f;
                b += (random.unit() - 0.5f) * 0.02f;
                a = random.unit();
                break;
            }
            write(x, y, r, g, b, a);
        }
    }
    static const std::array<const char*, 11> names = {
        "black",
        "white",
        "vertical_edge",
        "horizontal_edge",
        "diagonal_edge",
        "checkerboard",
        "single_pixel",
        "gradient",
        "random_unit",
        "random_hdr",
        "noisy_gradient",
    };
    return names[pattern];
}

std::string fill_smooth_case(
    std::vector<float>& pixels,
    uint32_t case_index,
    uint32_t width,
    uint32_t height,
    uint32_t slices) {
    const float phase = static_cast<float>(case_index % 17u) / 16.0f;
    for (uint32_t slice = 0; slice < slices; ++slice) {
        const float z = static_cast<float>(slice)
            / static_cast<float>(std::max(1u, slices - 1));
        for (uint32_t y = 0; y < height; ++y) {
            const float v = static_cast<float>(y)
                / static_cast<float>(std::max(1u, height - 1));
            for (uint32_t x = 0; x < width; ++x) {
                const float u = static_cast<float>(x)
                    / static_cast<float>(std::max(1u, width - 1));
                const size_t offset = (
                    (static_cast<size_t>(slice) * height + y) * width + x) * 4;
                pixels[offset] = 0.75f * u + 0.25f * phase;
                pixels[offset + 1] = 0.75f * v + 0.25f * (1.0f - phase);
                pixels[offset + 2] = 0.5f * (u + v) + 0.25f * z;
                pixels[offset + 3] = 0.5f + 0.25f * phase;
            }
        }
    }
    return "smooth_gradient";
}

uint32_t ordered_float(float value) {
    uint32_t bits = 0;
    std::memcpy(&bits, &value, sizeof(bits));
    if ((bits & 0x80000000u) != 0) {
        return 0x80000000u - (bits & 0x7fffffffu);
    }
    return 0x80000000u + bits;
}

Comparison compare_outputs(
    const std::vector<float>& baseline,
    const std::vector<float>& candidate,
    double absolute_tolerance,
    double relative_tolerance,
    uint32_t ulp_tolerance,
    size_t components_per_pixel) {
    Comparison result;
    result.compared_values = baseline.size();
    std::vector<bool> differing_pixels(
        baseline.size() / components_per_pixel, false);
    for (size_t index = 0; index < baseline.size(); ++index) {
        const float first = baseline[index];
        const float second = candidate[index];
        uint32_t first_bits = 0;
        uint32_t second_bits = 0;
        std::memcpy(&first_bits, &first, sizeof(first_bits));
        std::memcpy(&second_bits, &second, sizeof(second_bits));
        if (first_bits == second_bits) {
            ++result.exact_values;
            continue;
        }
        if (std::isnan(first) && std::isnan(second)) {
            ++result.exact_values;
            continue;
        }
        const double absolute = std::abs(static_cast<double>(first) - second);
        const double scale = std::max(std::abs(static_cast<double>(first)),
                                      std::abs(static_cast<double>(second)));
        const double relative = scale > 0.0 ? absolute / scale : absolute;
        uint32_t ulp = std::numeric_limits<uint32_t>::max();
        if (std::isfinite(first) && std::isfinite(second)) {
            const uint32_t a = ordered_float(first);
            const uint32_t b = ordered_float(second);
            ulp = a > b ? a - b : b - a;
        }
        if (absolute > result.max_absolute_error) {
            result.max_absolute_error = absolute;
            result.worst_index = index;
            result.worst_baseline = first;
            result.worst_candidate = second;
        }
        result.max_relative_error = std::max(result.max_relative_error, relative);
        result.max_ulp_error = std::max(result.max_ulp_error, ulp);
        const bool finite_match = std::isfinite(first) && std::isfinite(second)
            && (ulp <= ulp_tolerance
                || absolute <= absolute_tolerance + relative_tolerance * scale);
        if (!finite_match) {
            result.passed = false;
            ++result.differing_values;
            differing_pixels[index / components_per_pixel] = true;
        }
    }
    result.differing_pixels = static_cast<uint64_t>(std::count(
        differing_pixels.begin(), differing_pixels.end(), true));
    return result;
}

template <typename T>
void write_raw(const std::filesystem::path& path, const std::vector<T>& values) {
    std::ofstream stream(path, std::ios::binary);
    if (!stream) {
        throw std::runtime_error("cannot create failure artifact: " + path.string());
    }
    stream.write(
        reinterpret_cast<const char*>(values.data()),
        static_cast<std::streamsize>(values.size() * sizeof(T)));
}

void preserve_failure(
    const Options& options,
    uint32_t case_index,
    const std::string& pattern,
    const std::vector<std::vector<float>>& inputs,
    const std::vector<float>& baseline,
    const std::vector<float>& candidate,
    const Comparison& comparison) {
    if (options.failure_dir.empty()) {
        return;
    }
    std::filesystem::create_directories(options.failure_dir);
    for (size_t index = 0; index < inputs.size(); ++index) {
        write_raw(
            options.failure_dir
                / ("input" + std::to_string(index) + ".rgba32f"),
            inputs[index]);
    }
    const char* output_name = options.depth_output ? "depth.r32f" : "color.rgba32f";
    write_raw(options.failure_dir / ("baseline." + std::string(output_name)), baseline);
    write_raw(options.failure_dir / ("candidate." + std::string(output_name)), candidate);
    if (options.stage == ShaderStage::pixel) {
        std::filesystem::copy_file(
            options.vertex,
            options.failure_dir / "vertex.dxbc",
            std::filesystem::copy_options::overwrite_existing);
    }
    std::filesystem::copy_file(
        options.baseline,
        options.failure_dir / "baseline.dxbc",
        std::filesystem::copy_options::overwrite_existing);
    std::filesystem::copy_file(
        options.candidate,
        options.failure_dir / "candidate.dxbc",
        std::filesystem::copy_options::overwrite_existing);
    std::ofstream report(options.failure_dir / "failure.json");
    report << std::setprecision(17)
           << "{\n"
           << "  \"case_index\": " << case_index << ",\n"
           << "  \"pattern\": \"" << json_escape(pattern) << "\",\n"
           << "  \"seed\": " << options.seed << ",\n"
           << "  \"width\": " << options.width << ",\n"
           << "  \"height\": " << options.height << ",\n"
           << "  \"absolute_tolerance\": " << options.absolute_tolerance << ",\n"
           << "  \"relative_tolerance\": " << options.relative_tolerance << ",\n"
           << "  \"ulp_tolerance\": " << options.ulp_tolerance << ",\n"
           << "  \"output\": \""
           << (options.depth_output ? "depth" : "color") << "\",\n"
           << "  \"max_absolute_error\": " << comparison.max_absolute_error << ",\n"
           << "  \"max_relative_error\": " << comparison.max_relative_error << ",\n"
           << "  \"max_ulp_error\": " << comparison.max_ulp_error << ",\n"
           << "  \"worst_value_index\": " << comparison.worst_index << "\n"
           << "}\n";
}

} // namespace

int main(int argc, char** argv) {
    try {
        const Options options = parse_options(argc, argv);
        Runner runner(options);
        SplitMix64 random{options.seed};
        std::vector<std::vector<float>> inputs(
            options.textures.size());
        for (size_t index = 0; index < inputs.size(); ++index) {
            inputs[index].resize(
                static_cast<size_t>(options.width) * options.height * 4
                * texture_slices(options.textures[index]));
        }
        std::vector<std::vector<uint32_t>> structured_inputs;
        for (const StructuredInputBinding& binding : options.structured_inputs) {
            structured_inputs.emplace_back(
                static_cast<size_t>(binding.elements) * binding.stride / 4);
        }
        uint64_t exact_values = 0;
        uint64_t compared_values = 0;
        double max_absolute_error = 0.0;
        double max_relative_error = 0.0;
        uint32_t max_ulp_error = 0;
        uint32_t tested_cases = 0;
        bool passed = true;
        std::string failed_pattern;
        uint32_t failed_case = 0;
        Comparison failure;

        for (uint32_t index = 0; index < options.cases; ++index) {
            std::string pattern;
            for (size_t resource = 0; resource < inputs.size(); ++resource) {
                const bool smooth = std::find(
                    options.smooth_texture_slots.begin(),
                    options.smooth_texture_slots.end(),
                    options.textures[resource].slot)
                    != options.smooth_texture_slots.end();
                const std::string resource_pattern = smooth
                    ? fill_smooth_case(
                        inputs[resource], index, options.width, options.height,
                        texture_slices(options.textures[resource]))
                    : fill_case(
                        inputs[resource],
                        index + static_cast<uint32_t>(resource * 3),
                        options.width,
                        options.height * texture_slices(options.textures[resource]),
                        random);
                if (resource == 0) {
                    pattern = resource_pattern;
                }
                const bool monochrome = std::find(
                    options.monochrome_texture_slots.begin(),
                    options.monochrome_texture_slots.end(),
                    options.textures[resource].slot)
                    != options.monochrome_texture_slots.end();
                if (monochrome) {
                    for (size_t component = 0; component < inputs[resource].size();
                         component += 4) {
                        inputs[resource][component + 1] = inputs[resource][component];
                        inputs[resource][component + 2] = inputs[resource][component];
                        inputs[resource][component + 3] = inputs[resource][component];
                    }
                }
                runner.update_input(resource, inputs[resource]);
            }
            for (size_t resource = 0; resource < structured_inputs.size(); ++resource) {
                auto& values = structured_inputs[resource];
                if (options.structured_inputs[resource].profile
                    == StructuredInputProfile::zero) {
                    std::fill(values.begin(), values.end(), 0u);
                } else if (index == 0) {
                    std::fill(values.begin(), values.end(), 0u);
                } else if (index == 1) {
                    if (options.structured_inputs[resource].stride == 32) {
                        std::fill(values.begin(), values.end(), 0u);
                        for (size_t element = 0;
                             element < options.structured_inputs[resource].elements;
                             ++element) {
                            float* bounds = reinterpret_cast<float*>(
                                values.data() + element * 8);
                            bounds[0] = bounds[1] = bounds[2] = -1.0f;
                            bounds[4] = bounds[5] = bounds[6] = 1.0f;
                        }
                    } else {
                        std::fill(values.begin(), values.end(), 1u);
                    }
                } else {
                    if (options.structured_inputs[resource].stride == 32) {
                        for (size_t element = 0;
                             element < options.structured_inputs[resource].elements;
                             ++element) {
                            float* bounds = reinterpret_cast<float*>(
                                values.data() + element * 8);
                            for (uint32_t axis = 0; axis < 3; ++axis) {
                                const float center = random.unit() * 40.0f - 20.0f;
                                const float extent = 0.1f + random.unit() * 80.0f;
                                bounds[axis] = center - extent;
                                bounds[4 + axis] = center + extent;
                            }
                            bounds[3] = bounds[7] = 0.0f;
                        }
                    } else {
                        for (uint32_t& value : values) {
                            value = static_cast<uint32_t>(random.next());
                        }
                    }
                }
                runner.update_structured_input(resource, values);
            }
            runner.update_constants(index);
            runner.initialize_structured_outputs(index);
            const auto baseline = runner.render(false);
            runner.initialize_structured_outputs(index);
            const auto candidate = runner.render(true);
            const Comparison comparison = compare_outputs(
                baseline,
                candidate,
                options.absolute_tolerance,
                options.relative_tolerance,
                options.ulp_tolerance,
                options.output_components);
            ++tested_cases;
            exact_values += comparison.exact_values;
            compared_values += comparison.compared_values;
            max_absolute_error = std::max(
                max_absolute_error, comparison.max_absolute_error);
            max_relative_error = std::max(
                max_relative_error, comparison.max_relative_error);
            max_ulp_error = std::max(max_ulp_error, comparison.max_ulp_error);
            if (!comparison.passed) {
                passed = false;
                failed_pattern = pattern;
                failed_case = index;
                failure = comparison;
                preserve_failure(
                    options,
                    index,
                    pattern,
                    inputs,
                    baseline,
                    candidate,
                    comparison);
                break;
            }
        }

        std::cout << std::setprecision(17)
                  << "{\n"
                  << "  \"passed\": " << (passed ? "true" : "false") << ",\n"
                  << "  \"adapter\": \"" << json_escape(runner.adapter_name()) << "\",\n"
                  << "  \"driver\": \"" << (options.warp ? "warp" : "hardware") << "\",\n"
                  << "  \"feature_level\": \""
                  << feature_level_name(runner.feature_level()) << "\",\n"
                  << "  \"stage\": \""
                  << (options.stage == ShaderStage::compute ? "compute" : "pixel")
                  << "\",\n"
                  << "  \"seed\": " << options.seed << ",\n"
                  << "  \"requested_cases\": " << options.cases << ",\n"
                  << "  \"tested_cases\": " << tested_cases << ",\n"
                  << "  \"width\": " << options.width << ",\n"
                  << "  \"height\": " << options.height << ",\n"
                  << "  \"dispatch_width\": " << options.dispatch_width << ",\n"
                  << "  \"dispatch_height\": " << options.dispatch_height << ",\n"
                  << "  \"absolute_tolerance\": " << options.absolute_tolerance << ",\n"
                  << "  \"relative_tolerance\": " << options.relative_tolerance << ",\n"
                  << "  \"ulp_tolerance\": " << options.ulp_tolerance << ",\n"
                  << "  \"texture_slots\": [";
        for (size_t index = 0; index < options.textures.size(); ++index) {
            if (index != 0) {
                std::cout << ", ";
            }
            std::cout << options.textures[index].slot;
        }
        std::cout << "],\n"
                  << "  \"smooth_texture_slots\": [";
        for (size_t index = 0; index < options.smooth_texture_slots.size(); ++index) {
            if (index != 0) std::cout << ", ";
            std::cout << options.smooth_texture_slots[index];
        }
        std::cout << "],\n"
                  << "  \"texture_kinds\": [";
        for (size_t index = 0; index < options.textures.size(); ++index) {
            if (index != 0) {
                std::cout << ", ";
            }
            std::cout << "\"" << texture_kind_name(options.textures[index].kind)
                      << "\"";
        }
        std::cout << "],\n"
                  << "  \"texture_mips\": [";
        for (size_t index = 0; index < options.textures.size(); ++index) {
            if (index != 0) {
                std::cout << ", ";
            }
            std::cout << options.textures[index].mip_levels;
        }
        std::cout << "],\n"
                  << "  \"samplers\": [";
        for (size_t index = 0; index < options.samplers.size(); ++index) {
            if (index != 0) {
                std::cout << ", ";
            }
            std::cout << "{\"slot\": " << options.samplers[index].slot
                      << ", \"filter\": \""
                      << (options.samplers[index].point ? "point" : "linear")
                      << "\", \"comparison\": "
                      << (options.samplers[index].comparison ? "true" : "false")
                      << "}";
        }
        std::cout << "],\n"
                  << "  \"constant_buffers\": [";
        for (size_t index = 0; index < options.constant_buffers.size(); ++index) {
            if (index != 0) {
                std::cout << ", ";
            }
            std::cout << "{\"slot\": " << options.constant_buffers[index].slot
                      << ", \"profile\": \""
                      << constant_profile_name(
                            options.constant_buffers[index].profile)
                      << "\"}";
        }
        std::cout << "],\n"
                  << "  \"output\": \""
                  << (options.depth_output ? "depth" : "color") << "\",\n"
                  << "  \"output_components\": " << options.output_components << ",\n"
                  << "  \"output_targets\": " << options.output_targets << ",\n"
                  << "  \"structured_output_elements\": "
                  << options.structured_output_elements << ",\n"
                  << "  \"structured_output_stride\": "
                  << options.structured_output_stride << ",\n"
                  << "  \"compared_values\": " << compared_values << ",\n"
                  << "  \"exact_values\": " << exact_values << ",\n"
                  << "  \"max_absolute_error\": " << max_absolute_error << ",\n"
                  << "  \"max_relative_error\": " << max_relative_error << ",\n"
                  << "  \"max_ulp_error\": " << max_ulp_error;
        if (!passed) {
            std::cout << ",\n"
                      << "  \"failed_case\": " << failed_case << ",\n"
                      << "  \"failed_pattern\": \""
                      << json_escape(failed_pattern) << "\",\n"
                      << "  \"differing_values\": " << failure.differing_values << ",\n"
                      << "  \"differing_pixels\": " << failure.differing_pixels << ",\n"
                      << "  \"worst_value_index\": " << failure.worst_index << ",\n"
                      << "  \"worst_baseline\": " << failure.worst_baseline << ",\n"
                      << "  \"worst_candidate\": " << failure.worst_candidate;
        }
        std::cout << "\n}\n";
        return passed ? 0 : 2;
    } catch (const std::exception& error) {
        std::cerr << "error: " << error.what() << '\n';
        return 1;
    }
}
