[CmdletBinding()]
param(
    [string]$DcsRoot = 'D:\Program Files\DCS World',
    [string]$NormalProfile = (Join-Path $env:USERPROFILE 'Saved Games\DCS'),
    [ValidateSet('Damage', 'Takeoff', 'Fans')][string]$Scenario = 'Damage',
    [switch]$AllowParallelDcs,
    [switch]$Render,
    [ValidateRange(120, 600)][int]$TimeoutSeconds = 360
)

$ErrorActionPreference = 'Stop'
$useRendering = $Render -or $Scenario -eq 'Fans'
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$lua = Join-Path $DcsRoot 'bin\luae.exe'
& $lua (Join-Path $PSScriptRoot 'check_ai.lua') $root
if ($LASTEXITCODE -ne 0) { throw 'Local AI configuration validation failed.' }
$existing = @(Get-Process | Where-Object { $_.ProcessName -in @('DCS', 'DCS_updater') })
if ($existing.Count -and -not $AllowParallelDcs) { throw 'DCS is already running. Close it first or explicitly use -AllowParallelDcs for an independent test.' }
$identifier = 'KC390-AI-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 6)
$work = Join-Path ([System.IO.Path]::GetTempPath()) $identifier
$profileName = 'DCS.' + $identifier
$testProfile = Join-Path (Split-Path -Parent $NormalProfile) $profileName
$modLink = Join-Path $testProfile 'Mods\aircraft\KC-390'
$normalConfig = Join-Path $NormalProfile 'Config'
$optionsPath = Join-Path $normalConfig 'options.lua'
$optionsHash = (Get-FileHash -LiteralPath $optionsPath -Algorithm SHA256).Hash
$tracked = @('Entry\KC-390.lua', 'Entry\KC-390_SFM.lua', 'Shapes\KC-390.lods', 'Shapes\KC-390.edm', 'Shapes\KC-390_lod01.edm', 'Shapes\KC-390_lod02.edm', 'Shapes\KC-390_lod03.edm', 'Shapes\KC-390_collision.edm')
$missionName = if ($Scenario -in @('Takeoff', 'Fans')) { 'KC-390 Takeoff Test.miz' } else { 'KC-390 AI Test.miz' }
$tracked += @('tools\check_ai.lua', 'tools\prepare_ai_test.lua', 'tools\validate_ai.ps1', ('Missions\QuickStart\' + $missionName))
$sourceHashes = @{}
foreach ($relative in $tracked) { $sourceHashes[$relative] = (Get-FileHash -LiteralPath (Join-Path $root $relative) -Algorithm SHA256).Hash }
$process = $null
$createdProfile = $false
$timedOut = $false
if ((Test-Path -LiteralPath $testProfile) -or (Test-Path -LiteralPath $work)) { throw 'Refusing to reuse an existing test directory.' }
[System.IO.Directory]::CreateDirectory($work) | Out-Null
Copy-Item -LiteralPath $optionsPath -Destination (Join-Path $work 'options.before.lua')
try {
    [System.IO.Directory]::CreateDirectory((Join-Path $testProfile 'Config')) | Out-Null
    $createdProfile = $true
    foreach ($directory in @('Scripts\Hooks', 'Mods\aircraft', 'Tracks')) { [System.IO.Directory]::CreateDirectory((Join-Path $testProfile $directory)) | Out-Null }
    foreach ($authFile in @('authdata.bin', 'network.vault')) {
        Copy-Item -LiteralPath (Join-Path $normalConfig $authFile) -Destination (Join-Path $testProfile ('Config\' + $authFile))
    }
    New-Item -ItemType Junction -Path $modLink -Target $root | Out-Null
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory((Join-Path $root ('Missions\QuickStart\' + $missionName)), (Join-Path $work 'staged'))
    $renderMode = if ($useRendering) { 'Render' } else { 'Headless' }
    & $lua (Join-Path $PSScriptRoot 'prepare_ai_test.lua') $work $testProfile $Scenario $renderMode
    if ($LASTEXITCODE -ne 0) { throw 'Mission generation failed.' }
    $testMission = Join-Path $work 'AI-validation.miz'
    [System.IO.Compression.ZipFile]::CreateFromDirectory((Join-Path $work 'staged'), $testMission)
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = Join-Path $DcsRoot 'bin\DCS.exe'
    $startInfo.WorkingDirectory = $DcsRoot
    $startInfo.UseShellExecute = $false
    $renderArgument = if ($useRendering) { '' } else { ' --norender' }
    $startInfo.Arguments = '-w ' + $profileName + $renderArgument + ' --force_disable_VR --mission "' + $testMission + '"'
    $process = [System.Diagnostics.Process]::Start($startInfo)
    Write-Output ('Isolated DCS PID={0}; mode={1}; existing sessions untouched={2}' -f $process.Id, $renderMode, ($existing.Id -join ','))
    $timedOut = -not $process.WaitForExit($TimeoutSeconds * 1000)
    if ($timedOut) { $process.Kill(); $process.WaitForExit() }
    Write-Output ('DCS exit={0}; timeout={1}' -f $process.ExitCode, $timedOut)
} finally {
    if ($process) {
        if (-not $process.HasExited) { $process.Kill(); $process.WaitForExit() }
        $process.Dispose()
    }
    $logPath = Join-Path $testProfile 'Logs\dcs.log'
    if (Test-Path -LiteralPath $logPath) { Copy-Item -LiteralPath $logPath -Destination (Join-Path $work 'dcs.log') }
    $screenshots = Join-Path $testProfile 'ScreenShots'
    if (Test-Path -LiteralPath $screenshots) { Copy-Item -LiteralPath $screenshots -Destination (Join-Path $work 'ScreenShots') -Recurse }
    if ($createdProfile) {
        if (Test-Path -LiteralPath $modLink) { [System.IO.Directory]::Delete($modLink) }
        if (Test-Path -LiteralPath $testProfile) { Remove-Item -LiteralPath $testProfile -Recurse -Force }
    }
    $optionsUnchanged = (Get-FileHash -LiteralPath $optionsPath -Algorithm SHA256).Hash -eq $optionsHash
    $sourceUnchanged = $true
    foreach ($relative in $tracked) {
        if ((Get-FileHash -LiteralPath (Join-Path $root $relative) -Algorithm SHA256).Hash -ne $sourceHashes[$relative]) { $sourceUnchanged = $false }
    }
    $profileRemoved = -not (Test-Path -LiteralPath $testProfile)
    $preservation = @{ NormalOptionsUnchanged = $optionsUnchanged; SourceUnchanged = $sourceUnchanged; TemporaryProfileAndAuthRemoved = $profileRemoved }
    @{ Preservation = $preservation; SourceHashes = $sourceHashes; Profile = $testProfile; TimedOut = $timedOut } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $work 'manifest.json') -Encoding UTF8
    $preservation | ConvertTo-Json
    Write-Output ('Evidence: {0}' -f $work)
    if (-not ($optionsUnchanged -and $sourceUnchanged -and $profileRemoved)) { throw 'Preservation check failed. Inspect the evidence; no unrelated files were restored.' }
}
$resultLog = Join-Path $work 'dcs.log'
if (-not (Test-Path -LiteralPath $resultLog)) { throw 'No DCS log: the native test did not run.' }
$markers = @(Select-String -LiteralPath $resultLog -Pattern 'KC390_AI_' | ForEach-Object { $_.Line })
$markers | Write-Output
if ($timedOut -or -not ($markers -match 'KC390_AI_RESULT PASS$') -or ($markers -match 'KC390_AI_RESULT (ERROR|FAIL)')) { throw 'Native AI validation did not pass. See the saved log.' }