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
    hdr,
    rect,
};

struct ConstantBinding {
    uint32_t slot;
    ConstantProfile profile;
};

enum class TextureKind {
    two_d,
    three_d,
    two_d_array,
    cube,
};

struct TextureBinding {
    uint32_t slot;
    TextureKind kind;
    uint32_t mip_levels;
};

struct Options {
    std::filesystem::path vertex;
    std::filesystem::path baseline;
    std::filesystem::path candidate;
    std::filesystem::path failure_dir;
    uint32_t width = 64;
    uint32_t height = 64;
    uint32_t cases = 256;
    uint64_t seed = 0x534D465841413031ull;
    double absolute_tolerance = 0.0;
    double relative_tolerance = 0.0;
    std::vector<TextureBinding> textures = {{0, TextureKind::two_d, 1}};
    std::vector<std::pair<uint32_t, bool>> samplers = {{6, false}};
    std::vector<ConstantBinding> constant_buffers = {
        {5, ConstantProfile::projection}};
    bool depth_output = false;
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
    if (profile == "hdr") return ConstantProfile::hdr;
    if (profile == "rect") return ConstantProfile::rect;
    throw std::runtime_error(
        "constant profile must be projection, random, hdr, or rect");
}

const char* constant_profile_name(ConstantProfile profile) {
    switch (profile) {
    case ConstantProfile::projection: return "projection";
    case ConstantProfile::random: return "random";
    case ConstantProfile::hdr: return "hdr";
    case ConstantProfile::rect: return "rect";
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
    if (kind == TextureKind::two_d_array || kind == TextureKind::three_d) return 4;
    return 1;
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
        } else if (name == "--failure-dir") {
            options.failure_dir = std::filesystem::u8path(value());
        } else if (name == "--width") {
            options.width = static_cast<uint32_t>(parse_u64(value()));
        } else if (name == "--height") {
            options.height = static_cast<uint32_t>(parse_u64(value()));
        } else if (name == "--cases") {
            options.cases = static_cast<uint32_t>(parse_u64(value()));
        } else if (name == "--seed") {
            options.seed = parse_u64(value());
        } else if (name == "--absolute-tolerance") {
            options.absolute_tolerance = parse_double(value());
        } else if (name == "--relative-tolerance") {
            options.relative_tolerance = parse_double(value());
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
                        : static_cast<uint32_t>(parse_u64(binding.substr(second + 1))),
                });
            }
        } else if (name == "--sampler-slot") {
            options.samplers.front().first =
                static_cast<uint32_t>(parse_u64(value()));
        } else if (name == "--samplers") {
            options.samplers.clear();
            std::stringstream samplers(value());
            std::string sampler;
            while (std::getline(samplers, sampler, ',')) {
                const size_t separator = sampler.find(':');
                if (separator == std::string::npos) {
                    throw std::runtime_error(
                        "samplers must use slot:point or slot:linear");
                }
                const uint32_t slot = static_cast<uint32_t>(
                    parse_u64(sampler.substr(0, separator)));
                const std::string filter = sampler.substr(separator + 1);
                if (filter != "point" && filter != "linear") {
                    throw std::runtime_error(
                        "sampler filter must be point or linear");
                }
                options.samplers.emplace_back(slot, filter == "point");
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
                options.samplers.front().second = true;
            } else if (filter != "linear") {
                throw std::runtime_error("filter must be point or linear");
            } else {
                options.samplers.front().second = false;
            }
        } else if (name == "--output") {
            const std::string output = value();
            if (output == "depth") {
                options.depth_output = true;
            } else if (output != "color") {
                throw std::runtime_error("output must be color or depth");
            }
        } else if (name == "--warp") {
            options.warp = true;
        } else {
            throw std::runtime_error("unknown argument: " + name);
        }
    }
    if (options.vertex.empty() || options.baseline.empty() || options.candidate.empty()) {
        throw std::runtime_error("--vertex, --baseline, and --candidate are required");
    }
    if (options.width == 0 || options.height == 0 || options.cases == 0) {
        throw std::runtime_error("width, height, and cases must be positive");
    }
    if (options.width > 4096 || options.height > 4096) {
        throw std::runtime_error("texture dimensions must not exceed 4096");
    }
    if (options.textures.empty()) {
        throw std::runtime_error("at least one texture slot is required");
    }
    if (std::any_of(
            options.textures.begin(), options.textures.end(),
            [](const TextureBinding& texture) {
                return texture.mip_levels == 0 || texture.mip_levels > 13;
            })) {
        throw std::runtime_error("texture mip count must be between 1 and 13");
    }
    if (std::any_of(
            options.textures.begin(),
            options.textures.end(),
            [](const TextureBinding& texture) {
                return texture.slot >= D3D11_COMMONSHADER_INPUT_RESOURCE_SLOT_COUNT;
            })
        || std::any_of(
            options.samplers.begin(),
            options.samplers.end(),
            [](const auto& sampler) {
                return sampler.first >= D3D11_COMMONSHADER_SAMPLER_SLOT_COUNT;
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
        const TextureKind kind = options_.textures.at(index).kind;
        const uint32_t mip_levels = options_.textures.at(index).mip_levels;
        const UINT row_pitch = options_.width * 4 * sizeof(float);
        const UINT slice_pitch = row_pitch * options_.height;
        if (kind == TextureKind::three_d) {
            context_->UpdateSubresource(
                inputs_.at(index).Get(), 0, nullptr, values.data(),
                row_pitch, slice_pitch);
        } else {
            const uint32_t slices = texture_slices(kind);
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

    std::array<float, 62 * 4> constant_values(
        ConstantProfile profile, uint32_t case_index) const {
        std::array<float, 62 * 4> constants{};
        if (profile == ConstantProfile::rect) {
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

    std::vector<float> render(ID3D11PixelShader* shader) {
        constexpr float clear[4] = {0.0f, 0.0f, 0.0f, 0.0f};
        if (options_.depth_output) {
            context_->ClearDepthStencilView(
                depth_view_.Get(), D3D11_CLEAR_DEPTH, 0.0f, 0);
        } else {
            context_->ClearRenderTargetView(render_target_view_.Get(), clear);
        }
        context_->PSSetShader(shader, nullptr, 0);
        context_->Draw(3, 0);
        context_->CopyResource(
            staging_.Get(),
            options_.depth_output
                ? static_cast<ID3D11Resource*>(depth_target_.Get())
                : static_cast<ID3D11Resource*>(render_target_.Get()));

        D3D11_MAPPED_SUBRESOURCE mapped{};
        check(context_->Map(staging_.Get(), 0, D3D11_MAP_READ, 0, &mapped), "Map output");
        const size_t components = options_.depth_output ? 1 : 4;
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
        context_->Unmap(staging_.Get(), 0);
        return output;
    }

    ID3D11PixelShader* baseline_shader() const { return baseline_shader_.Get(); }
    ID3D11PixelShader* candidate_shader() const { return candidate_shader_.Get(); }

private:
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
            description.Depth = texture_slices(kind);
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
        description.ArraySize = texture_slices(kind);
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

    void create_pipeline() {
        const auto vertex = read_binary(options_.vertex);
        const auto baseline = read_binary(options_.baseline);
        const auto candidate = read_binary(options_.candidate);
        check(
            device_->CreateVertexShader(vertex.data(), vertex.size(), nullptr, &vertex_shader_),
            "CreateVertexShader");
        check(
            device_->CreatePixelShader(
                baseline.data(), baseline.size(), nullptr, &baseline_shader_),
            "CreatePixelShader baseline");
        check(
            device_->CreatePixelShader(
                candidate.data(), candidate.size(), nullptr, &candidate_shader_),
            "CreatePixelShader candidate");

        for (const TextureBinding& binding : options_.textures) {
            inputs_.push_back(create_input_texture(binding));
            ComPtr<ID3D11ShaderResourceView> view;
            check(
                device_->CreateShaderResourceView(
                    inputs_.back().Get(), nullptr, &view),
                "CreateShaderResourceView");
            input_views_.push_back(std::move(view));
        }
        if (options_.depth_output) {
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
            render_target_ = create_texture(
                D3D11_USAGE_DEFAULT, D3D11_BIND_RENDER_TARGET, 0);
            staging_ = create_texture(
                D3D11_USAGE_STAGING, 0, D3D11_CPU_ACCESS_READ);
        }
        if (!options_.depth_output) {
            check(
                device_->CreateRenderTargetView(
                    render_target_.Get(), nullptr, &render_target_view_),
                "CreateRenderTargetView");
        }

        D3D11_BUFFER_DESC buffer_description{};
        buffer_description.ByteWidth = 62 * 16;
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

        for (const auto& [slot, point] : options_.samplers) {
            static_cast<void>(slot);
            D3D11_SAMPLER_DESC sampler_description{};
            sampler_description.Filter = point
                ? D3D11_FILTER_MIN_MAG_MIP_POINT
                : D3D11_FILTER_MIN_MAG_MIP_LINEAR;
            sampler_description.AddressU = D3D11_TEXTURE_ADDRESS_CLAMP;
            sampler_description.AddressV = D3D11_TEXTURE_ADDRESS_CLAMP;
            sampler_description.AddressW = D3D11_TEXTURE_ADDRESS_CLAMP;
            sampler_description.MaxLOD = D3D11_FLOAT32_MAX;
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
        ID3D11RenderTargetView* target = render_target_view_.Get();
        context_->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
        context_->VSSetShader(vertex_shader_.Get(), nullptr, 0);
        for (size_t index = 0; index < options_.constant_buffers.size(); ++index) {
            ID3D11Buffer* constant_buffer = constant_buffers_[index].Get();
            context_->VSSetConstantBuffers(
                options_.constant_buffers[index].slot, 1, &constant_buffer);
            context_->PSSetConstantBuffers(
                options_.constant_buffers[index].slot, 1, &constant_buffer);
        }
        for (size_t index = 0; index < options_.textures.size(); ++index) {
            ID3D11ShaderResourceView* input_view = input_views_[index].Get();
            context_->PSSetShaderResources(
                options_.textures[index].slot, 1, &input_view);
        }
        for (size_t index = 0; index < options_.samplers.size(); ++index) {
            ID3D11SamplerState* sampler = samplers_[index].Get();
            context_->PSSetSamplers(
                options_.samplers[index].first, 1, &sampler);
        }
        context_->RSSetState(rasterizer_state_.Get());
        context_->RSSetViewports(1, &viewport);
        if (options_.depth_output) {
            context_->OMSetDepthStencilState(depth_state_.Get(), 0);
            context_->OMSetRenderTargets(0, nullptr, depth_view_.Get());
        } else {
            context_->OMSetRenderTargets(1, &target, nullptr);
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
    std::vector<ComPtr<ID3D11Resource>> inputs_;
    ComPtr<ID3D11Texture2D> render_target_;
    ComPtr<ID3D11Texture2D> depth_target_;
    ComPtr<ID3D11Texture2D> staging_;
    std::vector<ComPtr<ID3D11ShaderResourceView>> input_views_;
    ComPtr<ID3D11RenderTargetView> render_target_view_;
    ComPtr<ID3D11DepthStencilView> depth_view_;
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
            && absolute <= absolute_tolerance + relative_tolerance * scale;
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
    std::filesystem::copy_file(
        options.vertex,
        options.failure_dir / "vertex.dxbc",
        std::filesystem::copy_options::overwrite_existing);
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
                * texture_slices(options.textures[index].kind));
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
                const std::string resource_pattern = fill_case(
                    inputs[resource],
                    index + static_cast<uint32_t>(resource * 3),
                    options.width,
                    options.height
                        * texture_slices(options.textures[resource].kind),
                    random);
                if (resource == 0) {
                    pattern = resource_pattern;
                }
                runner.update_input(resource, inputs[resource]);
            }
            runner.update_constants(index);
            const auto baseline = runner.render(runner.baseline_shader());
            const auto candidate = runner.render(runner.candidate_shader());
            const Comparison comparison = compare_outputs(
                baseline,
                candidate,
                options.absolute_tolerance,
                options.relative_tolerance,
                options.depth_output ? 1 : 4);
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
                  << "  \"seed\": " << options.seed << ",\n"
                  << "  \"requested_cases\": " << options.cases << ",\n"
                  << "  \"tested_cases\": " << tested_cases << ",\n"
                  << "  \"width\": " << options.width << ",\n"
                  << "  \"height\": " << options.height << ",\n"
                  << "  \"absolute_tolerance\": " << options.absolute_tolerance << ",\n"
                  << "  \"relative_tolerance\": " << options.relative_tolerance << ",\n"
                  << "  \"texture_slots\": [";
        for (size_t index = 0; index < options.textures.size(); ++index) {
            if (index != 0) {
                std::cout << ", ";
            }
            std::cout << options.textures[index].slot;
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
            std::cout << "{\"slot\": " << options.samplers[index].first
                      << ", \"filter\": \""
                      << (options.samplers[index].second ? "point" : "linear")
                      << "\"}";
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
