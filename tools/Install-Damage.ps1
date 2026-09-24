[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$Destination = (Join-Path $env:USERPROFILE 'Saved Games\DCS\Mods\aircraft\KC-390'),
    [string]$DcsRoot = 'D:\Program Files\DCS World',
    [string]$RestoreBackup
)

$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$destinationRoot = [IO.Path]::GetFullPath($Destination).TrimEnd('\', '/')
$files = @(
    'Entry\KC-390.lua', 'Shapes\KC-390.edm', 'Shapes\KC-390_lod01.edm',
    'Shapes\KC-390_lod02.edm', 'Shapes\KC-390_lod03.edm', 'Shapes\KC-390_collision.edm',
    'Shapes\KC-390_NoseCone.edm', 'Shapes\KC-390_WingLeft.edm',
    'Shapes\KC-390_WingRight.edm', 'Shapes\KC-390_CargoDoor.edm',
    'ARGUMENTOS_KC-390.txt', 'README.md'
)
if ($destinationRoot -eq $root.TrimEnd('\', '/')) { throw 'The installed mod must be separate from the source project.' }
if (-not (Test-Path -LiteralPath (Join-Path $destinationRoot 'Entry\KC-390_SFM.lua'))) {
    throw 'Destination must be an existing KC-390 installation.'
}
$active = @(Get-Process | Where-Object { $_.ProcessName -in @('DCS', 'DCS_updater', 'ModelViewer2') })
if ($active.Count -and -not $WhatIfPreference) {
    throw 'Close DCS, its updater and ModelViewer2 before installing or restoring models. No files changed.'
}

function Get-HashOrNull([string]$Path) {
    if (Test-Path -LiteralPath $Path -PathType Leaf) { return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash }
    return $null
}

if ($RestoreBackup) {
    $backup = [IO.Path]::GetFullPath($RestoreBackup)
    $manifestPath = Join-Path $backup 'deployment.json'
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.Schema -ne 1 -or $manifest.Destination -ne $destinationRoot) { throw 'Backup does not belong to this installation.' }
    foreach ($record in $manifest.Files) {
        if ($files -notcontains $record.File) { throw 'Unexpected path in backup manifest.' }
        $current = Get-HashOrNull (Join-Path $destinationRoot $record.File)
        if ($current -ne $record.InstalledHash -and $current -ne $record.OriginalHash) {
            throw ('Refusing to overwrite a later modification: ' + $record.File)
        }
        if ($record.OriginalHash -and (Get-HashOrNull (Join-Path $backup ('original\' + $record.File))) -ne $record.OriginalHash) {
            throw ('Backup hash mismatch: ' + $record.File)
        }
    }
    if (-not $PSCmdlet.ShouldProcess($destinationRoot, 'Restore verified KC-390 damage backup')) { return }
    foreach ($record in $manifest.Files) {
        $target = Join-Path $destinationRoot $record.File
        if ($record.OriginalHash) {
            Copy-Item -LiteralPath (Join-Path $backup ('original\' + $record.File)) -Destination $target
        } elseif (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target
        }
        if ((Get-HashOrNull $target) -ne $record.OriginalHash) { throw ('Restore verification failed: ' + $record.File) }
    }
    $manifest.State = 'Restored'
    $manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    Write-Output ('PASS: restored and verified ' + $manifest.Files.Count + ' files; backup retained at ' + $backup)
    return
}

& (Join-Path $DcsRoot 'bin\luae.exe') (Join-Path $PSScriptRoot 'check_ai.lua') $root
if ($LASTEXITCODE -ne 0) { throw 'Source damage validation failed.' }
$records = @(foreach ($relative in $files) {
    $source = Join-Path $root $relative
    $originalHash = Get-HashOrNull (Join-Path $destinationRoot $relative)
    $installedHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
    if ($originalHash -ne $installedHash) {
        [pscustomobject]@{ File = $relative; OriginalHash = $originalHash; InstalledHash = $installedHash }
    }
})
if (-not $records.Count) { Write-Output 'PASS: installation already matches the source damage package.'; return }
if (-not $PSCmdlet.ShouldProcess($destinationRoot, ('Back up and install {0} KC-390 files' -f $records.Count))) { return }
$backup = Join-Path $env:LOCALAPPDATA ('KC390-Damage\Backups\Install-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
[IO.Directory]::CreateDirectory($backup) | Out-Null
$manifestPath = Join-Path $backup 'deployment.json'
$manifest = [pscustomobject]@{ Schema = 1; State = 'BackedUp'; Destination = $destinationRoot; Files = $records }
foreach ($record in $records) {
    if ($record.OriginalHash) {
        $copy = Join-Path $backup ('original\' + $record.File)
        [IO.Directory]::CreateDirectory((Split-Path -Parent $copy)) | Out-Null
        Copy-Item -LiteralPath (Join-Path $destinationRoot $record.File) -Destination $copy
        if ((Get-HashOrNull $copy) -ne $record.OriginalHash) { throw ('Backup verification failed: ' + $record.File) }
    }
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
try {
    foreach ($record in $records) {
        $source = Join-Path $root $record.File
        $target = Join-Path $destinationRoot $record.File
        if ((Get-HashOrNull $source) -ne $record.InstalledHash -or (Get-HashOrNull $target) -ne $record.OriginalHash) {
            throw ('Concurrent modification detected: ' + $record.File)
        }
        [IO.Directory]::CreateDirectory((Split-Path -Parent $target)) | Out-Null
        Copy-Item -LiteralPath $source -Destination $target
        if ((Get-HashOrNull $target) -ne $record.InstalledHash) { throw ('Installation verification failed: ' + $record.File) }
    }
    $manifest.State = 'Installed'
} catch {
    $manifest.State = 'Incomplete'
    throw
} finally {
    $manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    Write-Output ('Backup and restore manifest: ' + $backup)
}
Write-Output ('PASS: installed and verified ' + $records.Count + ' files. Textures, SFM and normal DCS options were not changed.')