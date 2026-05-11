param(
    [string]$Version = $env:INSTALL_VERSION,
    [string]$InstallDir = $env:INSTALL_DIR,
    [string]$ReleaseApiUrl = $env:INSTALL_RELEASE_API_URL,
    [string]$ReleaseDownloadBase = $env:INSTALL_RELEASE_DOWNLOAD_BASE
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$RepoOwner = "LichKing-2234"
$RepoName = "atlassian-cli"

if (-not $InstallDir) {
    $InstallDir = Join-Path $HOME ".local\bin"
}
if (-not $ReleaseApiUrl) {
    $ReleaseApiUrl = "https://api.github.com/repos/$RepoOwner/$RepoName/releases/latest"
}
if (-not $ReleaseDownloadBase) {
    $ReleaseDownloadBase = "https://github.com/$RepoOwner/$RepoName/releases/download"
}
$InstallRequestTimeoutSec = if ($env:INSTALL_CURL_MAX_TIME) {
    [int]$env:INSTALL_CURL_MAX_TIME
} elseif ($env:INSTALL_CURL_CONNECT_TIMEOUT) {
    [int]$env:INSTALL_CURL_CONNECT_TIMEOUT
} else {
    120
}

function Fail([string]$Message) {
    throw "error: $Message"
}

function Normalize-Tag([string]$Tag) {
    if ($Tag.StartsWith("v")) {
        return $Tag
    }
    return "v$Tag"
}

function Release-Version([string]$Tag) {
    if ($Tag.StartsWith("v")) {
        return $Tag.Substring(1)
    }
    return $Tag
}

function Assert-WindowsAmd64 {
    if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
        Fail "install.ps1 only supports Windows amd64"
    }

    $ProcessorArch = $env:PROCESSOR_ARCHITEW6432
    if (-not $ProcessorArch) {
        $ProcessorArch = $env:PROCESSOR_ARCHITECTURE
    }
    if ($ProcessorArch -notin @("AMD64", "x86_64")) {
        Fail "unsupported architecture: $ProcessorArch"
    }
}

function Resolve-ReleaseTag {
    if ($Version) {
        return Normalize-Tag $Version
    }

    $Headers = @{ "User-Agent" = "$RepoName-installer" }
    $Metadata = Invoke-RestMethod -Uri $ReleaseApiUrl -Headers $Headers -TimeoutSec $InstallRequestTimeoutSec
    if (-not $Metadata.tag_name) {
        Fail "failed to parse tag_name from release metadata"
    }
    return Normalize-Tag ([string]$Metadata.tag_name)
}

function Download-File([string]$Url, [string]$Destination) {
    Write-Host "Downloading $Url"
    Invoke-WebRequest -Uri $Url -OutFile $Destination -TimeoutSec $InstallRequestTimeoutSec
}

function Checksum-ForArchive([string]$ArchiveName, [string]$ChecksumsPath) {
    foreach ($Line in Get-Content -LiteralPath $ChecksumsPath) {
        $Parts = $Line.Trim() -split "\s+", 2
        if ($Parts.Count -eq 2 -and $Parts[1] -eq $ArchiveName) {
            return $Parts[0].ToLowerInvariant()
        }
    }
    Fail "missing checksum entry for $ArchiveName"
}

function Assert-ZipLayout([string]$ArchivePath) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $Zip = [System.IO.Compression.ZipFile]::OpenRead($ArchivePath)
    try {
        $HasBinary = $false
        foreach ($Entry in $Zip.Entries) {
            $Name = $Entry.FullName
            if ($Name -eq "atlassian/atlassian.exe") {
                $HasBinary = $true
            }
            if ($Name -ne "atlassian" -and -not $Name.StartsWith("atlassian/")) {
                Fail "zip archive must contain a top-level atlassian bundle"
            }
            if ($Name.StartsWith("/") -or $Name.Contains("\") -or $Name -match "^[A-Za-z]:") {
                Fail "zip archive contains an unsafe path"
            }
            if (($Name -split "/") -contains "..") {
                Fail "zip archive contains an unsafe path"
            }
        }
        if (-not $HasBinary) {
            Fail "zip archive must contain atlassian/atlassian.exe"
        }
    }
    finally {
        $Zip.Dispose()
    }
}

function Assert-NoReparsePoints([string]$Path) {
    $ReparsePoint = Get-ChildItem -LiteralPath $Path -Force -Recurse |
        Where-Object { ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) }
    if ($ReparsePoint) {
        Fail "archive extracted a symbolic link or reparse point"
    }
}

function Install-WindowsBundle([string]$BundleSource, [string]$DestinationDir) {
    $Executable = Join-Path $BundleSource "atlassian.exe"
    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
        Fail "archive did not extract an atlassian.exe executable"
    }
    Assert-NoReparsePoints $BundleSource

    $RuntimeDir = Join-Path $DestinationDir ".atlassian-cli"
    $BundleDir = Join-Path $RuntimeDir "atlassian"
    $TempBundle = Join-Path $RuntimeDir ".atlassian.tmp.$PID"
    $TempShim = Join-Path $DestinationDir ".atlassian.tmp.$PID"
    $TempCmd = Join-Path $DestinationDir ".atlassian.tmp.$PID.cmd"

    New-Item -ItemType Directory -Force -Path $RuntimeDir, $DestinationDir | Out-Null
    Remove-Item -LiteralPath $TempBundle, $TempShim, $TempCmd -Recurse -Force -ErrorAction SilentlyContinue

    Copy-Item -LiteralPath $BundleSource -Destination $TempBundle -Recurse
    $ShellShim = @'
#!/bin/sh
SELF_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd) || exit 1
exec "${SELF_DIR}/.atlassian-cli/atlassian/atlassian.exe" "$@"
'@
    Set-Content -LiteralPath $TempShim -Value $ShellShim -NoNewline -Encoding ASCII

    $CmdLauncher = "@echo off`r`nset ""SELF_DIR=%~dp0""`r`n""%SELF_DIR%.atlassian-cli\atlassian\atlassian.exe"" %*`r`n"
    [System.IO.File]::WriteAllText($TempCmd, $CmdLauncher, [System.Text.Encoding]::ASCII)

    Remove-Item -LiteralPath $BundleDir -Recurse -Force -ErrorAction SilentlyContinue
    Move-Item -LiteralPath $TempBundle -Destination $BundleDir
    Move-Item -LiteralPath $TempShim -Destination (Join-Path $DestinationDir "atlassian") -Force
    Move-Item -LiteralPath $TempCmd -Destination (Join-Path $DestinationDir "atlassian.cmd") -Force
}

function Main {
    Assert-WindowsAmd64

    $ReleaseTag = Resolve-ReleaseTag
    $ReleaseVersion = Release-Version $ReleaseTag
    $ArchiveName = "atlassian-cli_${ReleaseVersion}_windows_amd64.zip"

    $TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) "atlassian-cli-install-$PID"
    Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null

    try {
        $ArchivePath = Join-Path $TempRoot $ArchiveName
        $ChecksumsPath = Join-Path $TempRoot "checksums.txt"
        $ExtractDir = Join-Path $TempRoot "extract"

        Download-File "$ReleaseDownloadBase/$ReleaseTag/$ArchiveName" $ArchivePath
        Download-File "$ReleaseDownloadBase/$ReleaseTag/checksums.txt" $ChecksumsPath

        $ExpectedChecksum = Checksum-ForArchive $ArchiveName $ChecksumsPath
        $ActualChecksum = (Get-FileHash -Algorithm SHA256 -LiteralPath $ArchivePath).Hash.ToLowerInvariant()
        if ($ActualChecksum -ne $ExpectedChecksum) {
            Fail "checksum mismatch for $ArchiveName"
        }

        Assert-ZipLayout $ArchivePath
        Expand-Archive -LiteralPath $ArchivePath -DestinationPath $ExtractDir -Force
        $BundleSource = Join-Path $ExtractDir "atlassian"
        if (-not (Test-Path -LiteralPath $BundleSource -PathType Container)) {
            Fail "archive did not extract an atlassian payload"
        }
        Install-WindowsBundle $BundleSource $InstallDir
    }
    finally {
        Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }

    Write-Output "installed $ReleaseTag to $(Join-Path $InstallDir 'atlassian.cmd')"
    $ResolvedInstallDir = [System.IO.Path]::GetFullPath($InstallDir).TrimEnd("\")
    $PathEntries = $env:Path -split [System.IO.Path]::PathSeparator |
        ForEach-Object { if ($_) { [System.IO.Path]::GetFullPath($_).TrimEnd("\") } }
    if ($PathEntries -notcontains $ResolvedInstallDir) {
        Write-Warning "add $InstallDir to PATH to run atlassian directly"
    }
}

Main
