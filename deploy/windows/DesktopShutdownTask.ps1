function script:Get-DesktopShutdownTask {
    $scheduler = New-Object -ComObject 'Schedule.Service'
    $scheduler.Connect()
    $task = $scheduler.GetFolder('\SshDiscordBotDesktopPower').GetTask('DesktopShutdown')
    $definition = $task.Definition
    $worker = Join-Path $PSScriptRoot 'DesktopShutdownWorker.exe'
    if ($definition.RegistrationInfo.Source -cne 'ssh-discord-bot desktop shutdown' -or
        $definition.Actions.Count -ne 1 -or $definition.Actions.Item(1).Path -ine $worker -or
        $definition.Triggers.Count -ne 0) {
        throw 'Unexpected shutdown task definition'
    }
    return $task
}

function script:Test-DesktopShutdownTask {
    try { Get-DesktopShutdownTask | Out-Null; return $true } catch { return $false }
}

function script:Invoke-DesktopShutdownTask {
    param([Parameter(Mandatory=$true)][ValidatePattern('\A[0-9]{10,20}\z')][string]$ExpectedBoot)
    $gate = [Threading.Mutex]::new($false, 'Global\SshDiscordBotDesktopPowerRequest')
    $acquired = $false
    try {
        $acquired = $gate.WaitOne(0)
        if (-not $acquired) { throw 'A desktop request is already pending' }
        $task = Get-DesktopShutdownTask
        $requestId = [guid]::NewGuid().ToString('N')
        $resultPath = Join-Path (Join-Path $PSScriptRoot 'results') ($requestId + '.json')
        $task.Run([string[]]@($ExpectedBoot, $requestId)) | Out-Null
        $timer = [Diagnostics.Stopwatch]::StartNew()
        while ($timer.Elapsed.TotalSeconds -lt 8) {
            if (Test-Path -LiteralPath $resultPath) {
                $result = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
                if ($result.request_id -cne $requestId -or $result.boot -cne $ExpectedBoot) {
                    throw 'Shutdown result does not match the request'
                }
                return $result
            }
            Start-Sleep -Milliseconds 100
        }
        throw 'Shutdown result was not received; delivery is uncertain'
    } finally {
        if ($acquired) { $gate.ReleaseMutex() }
        $gate.Dispose()
    }
}
