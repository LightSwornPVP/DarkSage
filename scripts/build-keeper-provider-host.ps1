param(
    [Parameter(Mandatory = $true)]
    [string]$PythonPath,
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory
)

$ErrorActionPreference = "Stop"
$Repository = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = (Resolve-Path -LiteralPath $PythonPath).Path
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

& $Python -c "from importlib.metadata import version; assert version('Nuitka') == '4.1.3'"
if ($LASTEXITCODE -ne 0) { throw "Nuitka 4.1.3 is required" }

$TempRoot = Join-Path ([IO.Path]::GetTempPath()) ("keeper-provider-host-build-" + [Guid]::NewGuid().ToString("N"))
$SourceStage = Join-Path $TempRoot "source"
$BuildRoot = Join-Path $TempRoot "build"
New-Item -ItemType Directory -Path $SourceStage -Force | Out-Null
New-Item -ItemType Directory -Path $BuildRoot -Force | Out-Null
try {
    Copy-Item -LiteralPath (Join-Path $Repository "keeper") -Destination $SourceStage -Recurse
    Copy-Item -LiteralPath (Join-Path $Repository "keeper_provider_host.py") -Destination $SourceStage
    Get-ChildItem -LiteralPath $SourceStage -Recurse -Directory -Filter "__pycache__" |
        Sort-Object { $_.FullName.Length } -Descending |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }

    $PreviousPath = $env:Path
    $PreviousNuitkaCache = $env:NUITKA_CACHE_DIR
    try {
        $env:Path = (Split-Path -Parent $Python) + ";" + $env:Path
        $env:NUITKA_CACHE_DIR = Join-Path $TempRoot "nuitka-cache"
        Push-Location $SourceStage
        try {
            & $Python -m nuitka `
                --standalone `
                --assume-yes-for-downloads `
                --output-dir=$BuildRoot `
                --output-filename=KeeperProviderHost.exe `
                --nofollow-import-to=PySide6 `
                --nofollow-import-to=tkinter `
                keeper_provider_host.py
            if ($LASTEXITCODE -ne 0) { throw "Provider Host build failed" }
        }
        finally { Pop-Location }
    }
    finally {
        $env:Path = $PreviousPath
        $env:NUITKA_CACHE_DIR = $PreviousNuitkaCache
    }

    $Distribution = Get-ChildItem -LiteralPath $BuildRoot -Recurse -Directory -Filter "*.dist" |
        Select-Object -First 1
    if (-not $Distribution) { throw "Provider Host build did not produce a standalone distribution" }
    $BuiltExecutable = Join-Path $Distribution.FullName "KeeperProviderHost.exe"
    if (-not (Test-Path -LiteralPath $BuiltExecutable -PathType Leaf)) {
        throw "Provider Host build did not produce the dedicated executable"
    }
    $PackageRoot = Join-Path $OutputDirectory "KeeperProviderHost.dist"
    if (Test-Path -LiteralPath $PackageRoot) {
        $Resolved = (Resolve-Path -LiteralPath $PackageRoot).Path
        $Prefix = $OutputDirectory.TrimEnd("\") + "\"
        if (-not $Resolved.StartsWith($Prefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "refusing to replace Provider Host output outside the requested directory"
        }
        Remove-Item -LiteralPath $Resolved -Recurse -Force
    }
    Copy-Item -LiteralPath $Distribution.FullName -Destination $PackageRoot -Recurse
    $Forbidden = Get-ChildItem -LiteralPath $PackageRoot -Recurse -Force | Where-Object {
        $_.FullName -match '(?i)\.ai-workflow(\|$)|pilot-invocations|__pycache__' -or
        $_.Extension -in '.pyc', '.pyo' -or
        $_.Name -match '^(keeper\.db|.*\.key|.*\.pem|.*\.pfx)$'
    }
    if ($Forbidden) { throw "Provider Host package contains protected or secret material" }
    $Executable = Join-Path $PackageRoot "KeeperProviderHost.exe"
    $Version = (& $Python -c "from keeper.authority_service.core import SERVICE_VERSION; print(SERVICE_VERSION)").Trim()
    if ($LASTEXITCODE -ne 0 -or -not $Version) { throw "Provider Host version is unavailable" }
    $PackagePrefix = $PackageRoot.TrimEnd("\") + "\"
    $Files = @(Get-ChildItem -LiteralPath $PackageRoot -Recurse -File | ForEach-Object {
        if (-not $_.FullName.StartsWith($PackagePrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Provider Host package file escaped the output root"
        }
        $Relative = $_.FullName.Substring($PackagePrefix.Length).Replace("\", "/")
        [ordered]@{
            path = $Relative
            size = $_.Length
            sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    } | Sort-Object { $_.path })
    $ManifestPath = Join-Path $PackageRoot "keeper-provider-host-package-manifest.json"
    $ManifestJson = [ordered]@{
        schema_version = 1
        product = "KeeperProviderHost"
        version = $Version
        files = $Files
    } | ConvertTo-Json -Depth 6
    [IO.File]::WriteAllText(
        $ManifestPath,
        $ManifestJson + [Environment]::NewLine,
        (New-Object Text.UTF8Encoding($false))
    )
    Write-Output ([ordered]@{
        package_root = $PackageRoot
        package_manifest = $ManifestPath
        package_sha256 = (Get-FileHash -LiteralPath $ManifestPath -Algorithm SHA256).Hash
        executable = $Executable
        executable_sha256 = (Get-FileHash -LiteralPath $Executable -Algorithm SHA256).Hash
        file_count = @(Get-ChildItem -LiteralPath $PackageRoot -Recurse -File).Count
    } | ConvertTo-Json -Depth 4)
}
finally {
    if (Test-Path -LiteralPath $TempRoot) {
        $ResolvedTemp = (Resolve-Path -LiteralPath $TempRoot).Path
        $TempPrefix = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
        if (-not $ResolvedTemp.StartsWith($TempPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "refusing to remove Provider Host build state outside the temporary directory"
        }
        Remove-Item -LiteralPath $ResolvedTemp -Recurse -Force
    }
}
