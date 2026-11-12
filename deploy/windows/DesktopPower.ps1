# Install in C:\ProgramData\DiscordBot with administrator-owned, read-only ACLs
# for the SSH account. Run only through the sshd Match User ForceCommand.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$originalCommand = $env:SSH_ORIGINAL_COMMAND
$isCheck = $originalCommand -ceq 'desktop-check'
$isDiagnose = $originalCommand -ceq 'desktop-diagnose'
$isShutdown = $originalCommand -cmatch '\Adesktop-off ([0-9]{10,20})\z'
if (-not ($isCheck -or $isDiagnose -or $isShutdown)) {
    [Console]::Error.WriteLine('DESKTOP_COMMAND_DENIED')
    exit 2
}
$expectedBoot = if ($isShutdown) { $Matches[1] } else { $null }

function Initialize-DesktopShutdownTask {
    . (Join-Path $PSScriptRoot 'DesktopShutdownTask.ps1')
}

try {
    if ($isDiagnose) {
        Initialize-DesktopShutdownTask
        $taskFound = [int](Test-DesktopShutdownTask)
        [Console]::Out.WriteLine("DESKTOP_DIAGNOSTICS BROKER_FOUND=$taskFound")
        exit 0
    }
    $boot = (Get-CimInstance -ClassName Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().Ticks.ToString(
        [Globalization.CultureInfo]::InvariantCulture
    )
    if ($isCheck) {
        [Console]::Out.WriteLine("DESKTOP_READY $boot")
        exit 0
    }
    # A restart between check and shutdown must not shut down the new session.
    if ($expectedBoot -cne $boot) {
        [Console]::Error.WriteLine('DESKTOP_BOOT_CHANGED')
        [Console]::Out.WriteLine("DESKTOP_SHUTDOWN_REJECTED $expectedBoot")
        exit 1
    }

    # A fixed SYSTEM task performs only the local shutdown operation. The SSH
    # account can read/run that task but cannot edit its action or binaries.
    Initialize-DesktopShutdownTask
    $taskResult = Invoke-DesktopShutdownTask -ExpectedBoot $boot
    if ($taskResult.status -ceq 'BOOT_CHANGED') {
        [Console]::Error.WriteLine('DESKTOP_BOOT_CHANGED')
        [Console]::Out.WriteLine("DESKTOP_SHUTDOWN_REJECTED $boot")
        exit 1
    }
    if ($taskResult.status -cne 'REQUESTED' -and $taskResult.status -cne 'REJECTED' -and $taskResult.status -cne 'FAILED') {
        throw 'Shutdown task delivery is uncertain'
    }
    $shutdownExitCode = [int]$taskResult.error
    if ($taskResult.status -ceq 'REQUESTED' -and $shutdownExitCode -ne 0) { throw 'Invalid task result' }
    if ($taskResult.status -cne 'REQUESTED' -and $shutdownExitCode -eq 0) { throw 'Invalid task result' }
    if ($shutdownExitCode -ne 0) {
        [Console]::Error.WriteLine("DESKTOP_WINDOWS_ERROR $shutdownExitCode")
        [Console]::Out.WriteLine("DESKTOP_SHUTDOWN_REJECTED $boot")
        exit 1
    }
    [Console]::Out.WriteLine("DESKTOP_SHUTDOWN_REQUESTED $boot")
    exit 0
} catch {
    # A failed probe or uncertain shutdown never emits a success marker.
    [Console]::Error.WriteLine('DESKTOP_COMMAND_FAILED')
    exit 2
}
