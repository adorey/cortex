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
#                           latest/download/ASSET and download/VERSION/ASSET, over https;
#                           http only to this machine (127.0.0.1, localhost), for tests
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

    # The file a path leads to, through every link and junction on the way - a directory of PATH
    # may be one, and the file itself too.
    function Resolve-Final([string] $Path) {
        $full = [IO.Path]::GetFullPath($Path)
        for ($round = 0; $round -lt 40; $round++) {
            $root = [IO.Path]::GetPathRoot($full)
            $parts = @($full.Substring($root.Length).Split(@('\', '/'), [StringSplitOptions]::RemoveEmptyEntries))
            $current = $root
            $moved = $false
            for ($i = 0; $i -lt $parts.Count; $i++) {
                $current = Join-Path $current $parts[$i]
                $item = Get-Item -LiteralPath $current -Force -ErrorAction SilentlyContinue
                if ($item -and $item.LinkType -and $item.Target) {
                    $to = @($item.Target)[0]
                    if (-not [IO.Path]::IsPathRooted($to)) { $to = Join-Path (Split-Path -Parent $current) $to }
                    $rest = if ($i -lt $parts.Count - 1) { $parts[($i + 1)..($parts.Count - 1)] -join '\' } else { "" }
                    $full = [IO.Path]::GetFullPath($(if ($rest) { Join-Path $to $rest } else { $to }))
                    $moved = $true
                    break
                }
            }
            if (-not $moved) { return $full }
        }
        return $full
    }

    # The releases' URL: https, or plain http to this machine for a test - its host exactly, a port
    # of digits at most. No user part: http://127.0.0.1:1@example.com names example.com.
    function Test-ReleasesUrl([string] $Url) {
        if ($Url -match '[@\s]') { return $false }
        return ($Url -match '^https://.') -or ($Url -match '^http://(127\.0\.0\.1|localhost|\[::1\])(:[0-9]+)?(/|$)')
    }

    # Invoke-WebRequest follows a redirect to any scheme: each hop is asked for, and checked, here -
    # https only.
    function Save-Url([string] $Url, [string] $OutFile) {
        for ($hop = 0; $hop -le 10; $hop++) {
            $request = [Net.HttpWebRequest]::Create($Url)
            $request.AllowAutoRedirect = $false
            $request.UserAgent = "cortex-install"
            try {
                $response = $request.GetResponse()
            } catch [Net.WebException] {
                if (-not $_.Exception.Response) { throw }
                $response = $_.Exception.Response
            }
            try {
                $code = [int] $response.StatusCode
                if ($code -ge 300 -and $code -lt 400) {
                    $location = $response.Headers["Location"]
                    if (-not $location) { throw "a redirect without a location" }
                    $next = (New-Object System.Uri ([Uri] $Url), $location).AbsoluteUri
                    if ($next -notmatch '^https://') { throw "$Url redirects to $next, which is not https" }
                    $Url = $next
                    continue
                }
                if ($code -ne 200) { throw "HTTP $code" }
                $in = $response.GetResponseStream()
                $out = [IO.File]::Create($OutFile)
                try { $in.CopyTo($out) } finally { $out.Dispose(); $in.Dispose() }
                return
            } finally {
                $response.Close()
            }
        }
        throw "more than 10 redirects"
    }

    # The cortex found first on PATH, unless it is the one in $BinDir, through a link or not.
    function Get-OtherCortex([string] $BinDir) {
        $found = Get-Command cortex -CommandType Application, ExternalScript -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found -and (Resolve-Final $found.Source) -ne (Resolve-Final (Join-Path $BinDir "cortex.exe"))) {
            return $found.Source
        }
    }

    $ErrorActionPreference = "Stop"
    $ProgressPreference = "SilentlyContinue"     # Windows PowerShell's progress bar slows a download tenfold

    if ($Version -and $Version -cnotmatch '^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?\z') {
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
    # SHA256SUMS comes from where the archive does: it proves the download whole, not its origin.
    # That origin is https - or this machine, for a test - never a plain http elsewhere.
    if (-not (Test-ReleasesUrl $releases)) {
        throw "install.ps1: CORTEX_RELEASES_URL must be https:// - http:// only to 127.0.0.1, localhost or [::1] (got $releases)"
    }
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
                Save-Url $download[0] $download[1]
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
        # .NET itself, not Get-FileHash or Expand-Archive: those come from script modules, which
        # Windows PowerShell started from PowerShell 7 looks for in the wrong place (PSModulePath).
        $stream = [IO.File]::OpenRead($zip)
        try {
            $digest = [Security.Cryptography.SHA256]::Create().ComputeHash($stream)
        } finally {
            $stream.Dispose()
        }
        $actual = -join ($digest | ForEach-Object { $_.ToString("x2") })
        if ($actual -cne $expected) {
            throw "install.ps1: checksum mismatch for $asset - expected $expected, got $actual. Nothing was installed."
        }

        $unpacked = Join-Path $work "unpacked"
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [IO.Compression.ZipFile]::ExtractToDirectory($zip, $unpacked)
        $exe = Join-Path $unpacked "cortex.exe"
        if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
            throw "install.ps1: $asset holds no cortex.exe - nothing was installed"
        }
        # Run once before it is installed: a binary Windows will not start - blocked, quarantined,
        # no program at all - or that starts and fails - a DLL missing, its files not unpacked - is
        # neither installed nor put on PATH.
        $output = @()
        $previous = $ErrorActionPreference
        try {
            # A native command's stderr is an error record: under "Stop", its first line would throw.
            $ErrorActionPreference = "Continue"
            $output = @(& $exe --version 2>&1 | ForEach-Object { "$_" })
            $code = $LASTEXITCODE
        } catch {
            throw "install.ps1: cortex.exe does not run here - check that your antivirus let it through: $($_.Exception.Message). Nothing was installed."
        } finally {
            $ErrorActionPreference = $previous
        }
        if ($code -ne 0) {
            throw "install.ps1: cortex.exe does not run here - it exited with code $code$(if ($output) { ': ' + ($output -join ' ') }). Check that your antivirus let it through. Nothing was installed."
        }
        $installed = @($output | Where-Object { $_ })[0]

        # --- The command's name --------------------------------------------
        New-Item -ItemType Directory -Force -Path $binDir | Out-Null
        $binDir = (Resolve-Path -LiteralPath $binDir).ProviderPath.TrimEnd("\")
        if (-not $Name) {
            # Installed before, it keeps its name: running the script again is the upgrade.
            if (Test-Path -LiteralPath (Join-Path $binDir "cortex.exe")) {
                $Name = "cortex"
            } elseif (Test-Path -LiteralPath (Join-Path $binDir "cortex-ai.exe")) {
                $Name = "cortex-ai"
            } elseif (Get-OtherCortex $binDir) {
                Write-Host "Another cortex command comes first on PATH: $(Get-OtherCortex $binDir)"
                Write-Host "Installing as cortex-ai instead - run the script with -Name cortex to install as cortex anyway."
                $Name = "cortex-ai"
            } else {
                $Name = "cortex"
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

    if ($installed) {
        Write-Host "Installed $installed as $target"
    } else {
        Write-Host "Installed $target"
    }
    if ($Name -ceq "cortex" -and (Get-OtherCortex $binDir)) {
        Write-Host "note: another cortex command comes first on PATH, $(Get-OtherCortex $binDir): typing cortex runs it, not this one."
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
