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
$project = Join-Path $repository "native\gpu_diff\gpu_diff.vcxproj"
& $msbuild $project /p:Configuration=Release /p:Platform=x64 /m /v:minimal
if ($LASTEXITCODE -ne 0) {
    throw "GPU differential harness build failed"
}
