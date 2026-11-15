#Requires -RunAsAdministrator
param(
    [string]$AccountName = 'desktopbot',
    [string]$DestinationDirectory = 'C:\ProgramData\DiscordBot'
)
$ErrorActionPreference = 'Stop'
$account = Get-LocalUser -Name $AccountName
$accountIdentity = "$env:COMPUTERNAME\$AccountName"
if (-not (Test-Path -LiteralPath $DestinationDirectory -PathType Container)) {
    throw 'Prepare the administrator-owned dispatcher directory first'
}
$source = Join-Path $PSScriptRoot 'DesktopShutdown.cs'
$compiler = Join-Path ([Runtime.InteropServices.RuntimeEnvironment]::GetRuntimeDirectory()) 'csc.exe'
$temporaryDirectory = Join-Path $DestinationDirectory ('native-build-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temporaryDirectory | Out-Null
$temporaryAssembly = Join-Path $temporaryDirectory 'DesktopShutdown.dll'
$destination = Join-Path $DestinationDirectory 'DesktopShutdown.dll'
try {
    & $compiler /nologo /target:library ("/out:$temporaryAssembly") $source
    if ($LASTEXITCODE -ne 0) { throw 'Native shutdown bridge compilation failed' }
    if ([Reflection.AssemblyName]::GetAssemblyName($temporaryAssembly).Name -cne 'DesktopShutdown') {
        throw 'Native assembly identity does not match the installed file name'
    }
    if (Test-Path -LiteralPath $destination) {
        Copy-Item -LiteralPath $destination -Destination ($destination + '.backup-' + (Get-Date -Format yyyyMMddHHmmss))
    }
    Copy-Item -LiteralPath $temporaryAssembly -Destination $destination -Force
    & icacls.exe $destination /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F' "${accountIdentity}:RX" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Cannot protect the native shutdown bridge' }
    & icacls.exe $destination /setowner '*S-1-5-32-544' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Cannot assign the native shutdown bridge owner' }
} finally {
    if (Test-Path -LiteralPath $temporaryAssembly) { Remove-Item -LiteralPath $temporaryAssembly -Force }
    if (Test-Path -LiteralPath $temporaryDirectory) { Remove-Item -LiteralPath $temporaryDirectory -Force }
}
Write-Output 'Local shutdown API installed; no shutdown was requested'
