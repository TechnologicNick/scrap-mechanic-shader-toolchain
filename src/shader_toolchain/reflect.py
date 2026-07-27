"""Normalized runtime ABI reflection for Shader Model 5 DXBC."""

from __future__ import annotations

import ctypes
import sys
from typing import Any


HRESULT = ctypes.c_long
UINT = ctypes.c_uint


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]


IID_ID3D11_SHADER_REFLECTION = GUID(
    0x8D536CA1,
    0x0CCA,
    0x4956,
    (ctypes.c_ubyte * 8)(0xA8, 0x37, 0x78, 0x69, 0x63, 0x75, 0x55, 0x84),
)


class SignatureParameterDesc(ctypes.Structure):
    _fields_ = [
        ("SemanticName", ctypes.c_char_p),
        ("SemanticIndex", UINT),
        ("Register", UINT),
        ("SystemValueType", ctypes.c_int),
        ("ComponentType", ctypes.c_int),
        ("Mask", ctypes.c_ubyte),
        ("ReadWriteMask", ctypes.c_ubyte),
        ("Stream", UINT),
        ("MinPrecision", ctypes.c_int),
    ]


class ShaderBufferDesc(ctypes.Structure):
    _fields_ = [
        ("Name", ctypes.c_char_p),
        ("Type", ctypes.c_int),
        ("Variables", UINT),
        ("Size", UINT),
        ("Flags", UINT),
    ]


class ShaderVariableDesc(ctypes.Structure):
    _fields_ = [
        ("Name", ctypes.c_char_p),
        ("StartOffset", UINT),
        ("Size", UINT),
        ("Flags", UINT),
        ("DefaultValue", ctypes.c_void_p),
        ("StartTexture", UINT),
        ("TextureSize", UINT),
        ("StartSampler", UINT),
        ("SamplerSize", UINT),
    ]


class ShaderTypeDesc(ctypes.Structure):
    _fields_ = [
        ("Class", ctypes.c_int),
        ("Type", ctypes.c_int),
        ("Rows", UINT),
        ("Columns", UINT),
        ("Elements", UINT),
        ("Members", UINT),
        ("Offset", UINT),
        ("Name", ctypes.c_char_p),
    ]


class ShaderInputBindDesc(ctypes.Structure):
    _fields_ = [
        ("Name", ctypes.c_char_p),
        ("Type", ctypes.c_int),
        ("BindPoint", UINT),
        ("BindCount", UINT),
        ("Flags", UINT),
        ("ReturnType", ctypes.c_int),
        ("Dimension", ctypes.c_int),
        ("NumSamples", UINT),
    ]


class ShaderDesc(ctypes.Structure):
    _fields_ = [
        ("Version", UINT),
        ("Creator", ctypes.c_char_p),
        ("Flags", UINT),
        ("ConstantBuffers", UINT),
        ("BoundResources", UINT),
        ("InputParameters", UINT),
        ("OutputParameters", UINT),
        ("InstructionCount", UINT),
        ("TempRegisterCount", UINT),
        ("TempArrayCount", UINT),
        ("DefCount", UINT),
        ("DclCount", UINT),
        ("TextureNormalInstructions", UINT),
        ("TextureLoadInstructions", UINT),
        ("TextureCompInstructions", UINT),
        ("TextureBiasInstructions", UINT),
        ("TextureGradientInstructions", UINT),
        ("FloatInstructionCount", UINT),
        ("IntInstructionCount", UINT),
        ("UintInstructionCount", UINT),
        ("StaticFlowControlCount", UINT),
        ("DynamicFlowControlCount", UINT),
        ("MacroInstructionCount", UINT),
        ("ArrayInstructionCount", UINT),
        ("CutInstructionCount", UINT),
        ("EmitInstructionCount", UINT),
        ("GSOutputTopology", ctypes.c_int),
        ("GSMaxOutputVertexCount", UINT),
        ("InputPrimitive", ctypes.c_int),
        ("PatchConstantParameters", UINT),
        ("GSInstanceCount", UINT),
        ("ControlPoints", UINT),
        ("HSOutputPrimitive", ctypes.c_int),
        ("HSPartitioning", ctypes.c_int),
        ("TessellatorDomain", ctypes.c_int),
        ("BarrierInstructions", UINT),
        ("InterlockedInstructions", UINT),
        ("TextureStoreInstructions", UINT),
    ]


def _method(pointer: int, index: int, restype: Any, *argtypes: Any) -> Any:
    vtable = ctypes.cast(
        pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
    ).contents
    return ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(vtable[index])


def _text(value: bytes | None) -> str:
    return value.decode("utf-8", errors="replace") if value else ""


class ShaderReflector:
    def __init__(self) -> None:
        if sys.platform != "win32":
            raise RuntimeError("DXBC reflection requires Windows and d3dcompiler_47.dll")
        self.dll = ctypes.WinDLL("d3dcompiler_47.dll")
        self.reflect = self.dll.D3DReflect
        self.reflect.argtypes = [
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.POINTER(GUID),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        self.reflect.restype = HRESULT

    def _type(self, pointer: int) -> dict[str, Any]:
        desc = ShaderTypeDesc()
        result = _method(pointer, 0, HRESULT, ctypes.POINTER(ShaderTypeDesc))(
            pointer, ctypes.byref(desc)
        )
        if result < 0:
            raise RuntimeError(f"shader type reflection failed: 0x{result & 0xffffffff:08x}")
        members = []
        get_member = _method(pointer, 1, ctypes.c_void_p, UINT)
        for index in range(desc.Members):
            member = get_member(pointer, index)
            members.append(self._type(member))
        return {
            "class": desc.Class,
            "type": desc.Type,
            "rows": desc.Rows,
            "columns": desc.Columns,
            "elements": desc.Elements,
            "offset": desc.Offset,
            "members": members,
        }

    def _constant_buffer(self, pointer: int, bindings: dict[str, int]) -> dict[str, Any]:
        desc = ShaderBufferDesc()
        result = _method(pointer, 0, HRESULT, ctypes.POINTER(ShaderBufferDesc))(
            pointer, ctypes.byref(desc)
        )
        if result < 0:
            raise RuntimeError(f"constant-buffer reflection failed: 0x{result & 0xffffffff:08x}")
        get_variable = _method(pointer, 1, ctypes.c_void_p, UINT)
        variables = []
        for index in range(desc.Variables):
            variable = get_variable(pointer, index)
            variable_desc = ShaderVariableDesc()
            result = _method(
                variable, 0, HRESULT, ctypes.POINTER(ShaderVariableDesc)
            )(variable, ctypes.byref(variable_desc))
            if result < 0:
                raise RuntimeError(f"shader-variable reflection failed: 0x{result & 0xffffffff:08x}")
            variable_type = _method(variable, 1, ctypes.c_void_p)(variable)
            variables.append(
                {
                    "offset": variable_desc.StartOffset,
                    "size": variable_desc.Size,
                    "type": self._type(variable_type),
                }
            )
        variables.sort(key=lambda item: (item["offset"], item["size"]))
        return {
            "bind_point": bindings.get(_text(desc.Name), -1),
            "type": desc.Type,
            "size": desc.Size,
            "variables": variables,
        }

    def abi(self, bytecode: bytes) -> dict[str, Any]:
        source = ctypes.create_string_buffer(bytecode)
        reflection = ctypes.c_void_p()
        result = self.reflect(
            source,
            len(bytecode),
            ctypes.byref(IID_ID3D11_SHADER_REFLECTION),
            ctypes.byref(reflection),
        )
        if result < 0:
            raise RuntimeError(f"D3DReflect failed: 0x{result & 0xffffffff:08x}")
        try:
            desc = ShaderDesc()
            result = _method(
                reflection.value, 3, HRESULT, ctypes.POINTER(ShaderDesc)
            )(reflection.value, ctypes.byref(desc))
            if result < 0:
                raise RuntimeError(f"shader reflection failed: 0x{result & 0xffffffff:08x}")

            resources = []
            constant_buffer_bindings: dict[str, int] = {}
            get_resource = _method(
                reflection.value, 6, HRESULT, UINT, ctypes.POINTER(ShaderInputBindDesc)
            )
            for index in range(desc.BoundResources):
                resource = ShaderInputBindDesc()
                result = get_resource(reflection.value, index, ctypes.byref(resource))
                if result < 0:
                    raise RuntimeError(f"resource reflection failed: 0x{result & 0xffffffff:08x}")
                if resource.Type in (0, 1):
                    constant_buffer_bindings[_text(resource.Name)] = resource.BindPoint
                resources.append(
                    {
                        "type": resource.Type,
                        "bind_point": resource.BindPoint,
                        "bind_count": resource.BindCount,
                        "flags": resource.Flags,
                        "return_type": resource.ReturnType,
                        "dimension": resource.Dimension,
                        "samples": resource.NumSamples,
                    }
                )
            resources.sort(key=lambda item: (item["type"], item["bind_point"]))

            def signatures(method_index: int, count: int) -> list[dict[str, Any]]:
                get_parameter = _method(
                    reflection.value,
                    method_index,
                    HRESULT,
                    UINT,
                    ctypes.POINTER(SignatureParameterDesc),
                )
                output = []
                for index in range(count):
                    parameter = SignatureParameterDesc()
                    result = get_parameter(
                        reflection.value, index, ctypes.byref(parameter)
                    )
                    if result < 0:
                        raise RuntimeError(f"signature reflection failed: 0x{result & 0xffffffff:08x}")
                    output.append(
                        {
                            "semantic": _text(parameter.SemanticName).upper(),
                            "index": parameter.SemanticIndex,
                            "system_value": parameter.SystemValueType,
                            "component_type": parameter.ComponentType,
                            "mask": parameter.Mask,
                            "read_write_mask": parameter.ReadWriteMask,
                            "stream": parameter.Stream,
                            "min_precision": parameter.MinPrecision,
                        }
                    )
                output.sort(key=lambda item: (item["semantic"], item["index"], item["stream"]))
                return output

            get_buffer = _method(reflection.value, 4, ctypes.c_void_p, UINT)
            buffers = [
                self._constant_buffer(
                    get_buffer(reflection.value, index), constant_buffer_bindings
                )
                for index in range(desc.ConstantBuffers)
            ]
            buffers.sort(key=lambda item: (item["type"], item["bind_point"]))

            x, y, z = UINT(), UINT(), UINT()
            _method(
                reflection.value,
                20,
                UINT,
                ctypes.POINTER(UINT),
                ctypes.POINTER(UINT),
                ctypes.POINTER(UINT),
            )(reflection.value, ctypes.byref(x), ctypes.byref(y), ctypes.byref(z))
            return {
                "version": desc.Version,
                "inputs": signatures(7, desc.InputParameters),
                "outputs": signatures(8, desc.OutputParameters),
                "resources": resources,
                "constant_buffers": buffers,
                "thread_group": [x.value, y.value, z.value],
            }
        finally:
            _method(reflection.value, 2, ctypes.c_ulong)(reflection.value)


def abi_differences(baseline: dict[str, Any], candidate: dict[str, Any]) -> list[str]:
    differences = []
    for field in (
        "version",
        "inputs",
        "outputs",
        "resources",
        "constant_buffers",
        "thread_group",
    ):
        if baseline[field] != candidate[field]:
            differences.append(field)
    return differences
