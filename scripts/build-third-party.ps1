$ErrorActionPreference = "Stop"

$repository = Split-Path -Parent $PSScriptRoot
$vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path -LiteralPath $vswhere)) {
    throw "Visual Studio Installer's vswhere.exe was not found"
}

$visualStudio = & $vswhere -latest -products * `
    -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 `
    -property installationPath
if (-not $visualStudio) {
    throw "Visual Studio with the C++ build tools was not found"
}

$msbuild = Join-Path $visualStudio "MSBuild\Current\Bin\MSBuild.exe"
$migotoRoot = Join-Path $repository "third_party\3Dmigoto"
$migotoProject = Join-Path $migotoRoot "HLSLDecompiler\cmd_Decompiler\cmd_Decompiler.vcxproj"
& $msbuild $migotoProject /p:Configuration=Release /p:Platform=x64 `
    "/p:SolutionDir=$migotoRoot\" /m /v:minimal
if ($LASTEXITCODE -ne 0) {
    throw "3DMigoto cmd_Decompiler build failed"
}

$dxDecompilerProject = Join-Path $repository `
    "third_party\DXDecompiler\src\DXDecompilerCmd\DXDecompilerCmd.csproj"
dotnet build $dxDecompilerProject -c Release -v:minimal
if ($LASTEXITCODE -ne 0) {
    throw "DXDecompiler build failed"
}

