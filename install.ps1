# ============================================================================
# Cortex - install.ps1: the one-line install on Windows (ADR-008, section 3.2)
# ============================================================================
#
#   irm https://raw.githubusercontent.com/adorey/cortex/main/install.ps1 | iex
#
# With options - a version, or the command's name - run it as a script block:
#
#   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/adorey/cortex/main/install.ps1))) -Version 1.0.0
#   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/adorey/cortex/main/install.ps1))) -Name cortex
#
# Downloads the release asset for Windows - the latest release, or the version given - checks
# it against the release's SHA256SUMS and stops on a mismatch, then installs `cortex.exe` into
# %USERPROFILE%\.cortex\bin and adds that directory to the user's PATH. It needs no
# administrator right. Run it again to upgrade.
#
# When another `cortex` command comes first on PATH, the binary is installed as `cortex-ai`
# instead; `-Name cortex` installs it as `cortex` anyway.
#
# Environment:
#   CORTEX_HOME             where Cortex lives on this machine (default: %USERPROFILE%\.cortex)
#   CORTEX_RELEASES_URL     where the releases are downloaded from (default: the GitHub
#                           releases of adorey/cortex) - a mirror serving the same layout,
#                           latest/download/ASSET and download/VERSION/ASSET
#   CORTEX_NO_MODIFY_PATH   set to 1 to leave the user's PATH as it is (-NoModifyPath)
#
# Windows PowerShell 5.1 and PowerShell 7 alike. ASCII only: Windows PowerShell reads a script
# without a byte order mark in the system's code page.
# ============================================================================

param(
    [string] $Version = "",
    [string] $Name = "",
    [switch] $NoModifyPath
)

# Everything runs inside a function: piped into iex, the script runs in the caller's session,
# which must not inherit its variables or its preferences.
function Install-Cortex {
    param([string] $Version, [string] $Name, [bool] $NoModifyPath)

    $ErrorActionPreference = "Stop"
    $ProgressPreference = "SilentlyContinue"     # Windows PowerShell's progress bar slows a download tenfold

    if ($Version -and $Version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$') {
        throw "install.ps1: not a version: $Version (expected X.Y.Z)"
    }
    if ($Name -and $Name -cnotin @("cortex", "cortex-ai")) {
        throw "install.ps1: -Name is cortex or cortex-ai (got $Name)"
    }

    # --- This machine ------------------------------------------------------
    # Windows on ARM runs the x86_64 build under emulation: there is no build of its own.
    $arch = $env:PROCESSOR_ARCHITEW6432
    if (-not $arch) { $arch = $env:PROCESSOR_ARCHITECTURE }
    switch ($arch) {
        "AMD64" { }
        "ARM64" { Write-Host "No build for Windows on ARM: installing the x86_64 one, which Windows runs under emulation." }
        default { throw "install.ps1: no build for Windows on $arch - the Windows target is x86_64" }
    }
    $asset = "cortex-windows-x86_64.zip"

    # Windows PowerShell 5.1 may not offer TLS 1.2 by default; GitHub requires it.
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

    $releases = if ($env:CORTEX_RELEASES_URL) { $env:CORTEX_RELEASES_URL } else { "https://github.com/adorey/cortex/releases" }
    $base = if ($Version) { "$releases/download/$Version" } else { "$releases/latest/download" }
    $cortexHome = if ($env:CORTEX_HOME) { $env:CORTEX_HOME } else { Join-Path $HOME ".cortex" }
    $binDir = Join-Path $cortexHome "bin"

    # --- Download and check ------------------------------------------------
    # Next to the binary's final place, so that the last step is a move on one volume.
    New-Item -ItemType Directory -Force -Path $cortexHome | Out-Null
    $work = Join-Path $cortexHome (".install." + [IO.Path]::GetRandomFileName())
    New-Item -ItemType Directory -Path $work | Out-Null
    try {
        Write-Host "Downloading $asset from $base"
        $sums = Join-Path $work "SHA256SUMS"
        $zip = Join-Path $work $asset
        foreach ($download in @(@("$base/SHA256SUMS", $sums), @("$base/$asset", $zip))) {
            try {
                Invoke-WebRequest -Uri $download[0] -OutFile $download[1] -UseBasicParsing
            } catch {
                throw "install.ps1: could not download $($download[0]): $($_.Exception.Message)"
            }
        }

        $expected = $null
        foreach ($line in Get-Content -LiteralPath $sums) {
            $fields = $line -split '\s+', 2
            if ($fields.Count -eq 2 -and ($fields[1] -ceq $asset -or $fields[1] -ceq "*$asset")) {
                $expected = $fields[0].ToLowerInvariant()
                break
            }
        }
        if (-not $expected) { throw "install.ps1: SHA256SUMS lists no $asset - nothing was installed" }
        # Get-FileHash answers in upper case, sha256sum in lower case.
        $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash.ToLowerInvariant()
        if ($actual -cne $expected) {
            throw "install.ps1: checksum mismatch for $asset - expected $expected, got $actual. Nothing was installed."
        }

        $unpacked = Join-Path $work "unpacked"
        Expand-Archive -LiteralPath $zip -DestinationPath $unpacked
        $exe = Join-Path $unpacked "cortex.exe"
        if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
            throw "install.ps1: $asset holds no cortex.exe - nothing was installed"
        }

        # --- The command's name --------------------------------------------
        New-Item -ItemType Directory -Force -Path $binDir | Out-Null
        $binDir = (Resolve-Path -LiteralPath $binDir).ProviderPath.TrimEnd("\")
        if (-not $Name) {
            $Name = "cortex"
            $existing = Get-Command cortex -CommandType Application, ExternalScript -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($existing) {
                $existingDir = (Split-Path -Parent $existing.Source).TrimEnd("\")
                if ($existingDir -ne $binDir) {
                    Write-Host "Another cortex command comes first on PATH: $($existing.Source)"
                    Write-Host "Installing as cortex-ai instead - run the script with -Name cortex to install as cortex anyway."
                    $Name = "cortex-ai"
                }
            }
        }

        # --- Install -------------------------------------------------------
        $target = Join-Path $binDir "$Name.exe"
        try {
            Move-Item -LiteralPath $exe -Destination $target -Force
        } catch {
            throw "install.ps1: could not replace $target - is a cortex command still running? $($_.Exception.Message)"
        }
    } finally {
        Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
    }

    $installed = $null
    try { $installed = (& $target --version) 2>$null } catch { }
    if ($installed) {
        Write-Host "Installed $installed as $target"
    } else {
        Write-Host "Installed $target - but it did not run here: check that your antivirus let it through."
    }

    # --- PATH ----------------------------------------------------------------
    # Read and written in the registry as it is stored: [Environment]::SetEnvironmentVariable would
    # write back every %VARIABLE% of the user's PATH expanded, and as a plain string.
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey("Environment", $true)
    try {
        $userPath = [string] $key.GetValue("Path", "", [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
        $entries = @($userPath -split ";" | Where-Object { $_ } | ForEach-Object { [Environment]::ExpandEnvironmentVariables($_).TrimEnd("\") })
        if ($entries -contains $binDir) {
            return
        }
        if ($NoModifyPath -or $env:CORTEX_NO_MODIFY_PATH -eq "1") {
            Write-Host ""
            Write-Host "$binDir is not on your PATH. Add it to your user PATH to run $Name from any terminal."
            return
        }
        $newPath = if ($userPath) { "$($userPath.TrimEnd(';'));$binDir" } else { $binDir }
        $key.SetValue("Path", $newPath, [Microsoft.Win32.RegistryValueKind]::ExpandString)
    } finally {
        $key.Close()
    }
    # Tell the programs that are running - Explorer, which starts the next terminal - that the
    # environment changed: setting a variable through .NET broadcasts it.
    [Environment]::SetEnvironmentVariable("CORTEX_INSTALL", "1", "User")
    [Environment]::SetEnvironmentVariable("CORTEX_INSTALL", $null, "User")
    # This session too - piped into iex, the script runs in it. Terminals already open keep their PATH.
    $env:Path = "$($env:Path.TrimEnd(';'));$binDir"
    Write-Host ""
    Write-Host "Added $binDir to your user PATH. Terminals opened before this one need to be reopened to see it."
}

Install-Cortex -Version $Version -Name $Name -NoModifyPath $NoModifyPath.IsPresent
