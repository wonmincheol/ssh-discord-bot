#Requires -RunAsAdministrator
param([string]$AccountName = 'desktopbot')
$ErrorActionPreference = 'Stop'
$controlPath = 'C:\ProgramData\DiscordBot'
$source = 'ssh-discord-bot desktop shutdown'
$account = Get-LocalUser -Name $AccountName
$accountIdentity = "$env:COMPUTERNAME\$AccountName"
$sddl = 'D:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;GRGX;;;' + $account.SID.Value + ')'
$worker = Join-Path $controlPath 'DesktopShutdownWorker.exe'
$library = Join-Path $controlPath 'DesktopShutdown.dll'
$results = Join-Path $controlPath 'results'
if (-not (Test-Path -LiteralPath $library -PathType Leaf)) { throw 'Install the native shutdown API first' }
$compiler = Join-Path ([Runtime.InteropServices.RuntimeEnvironment]::GetRuntimeDirectory()) 'csc.exe'
& $compiler /nologo /target:exe /main:DiscordDesktopPower.ShutdownWorker ("/out:$worker") ("/reference:$library") /reference:System.Management.dll (Join-Path $PSScriptRoot 'DesktopShutdownWorker.cs')
if ($LASTEXITCODE -ne 0) { throw 'Shutdown worker compilation failed' }
& icacls.exe $worker /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F' "${accountIdentity}:RX" | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Cannot protect the worker' }
& icacls.exe $worker /setowner '*S-1-5-32-544' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Cannot assign worker owner' }
New-Item -ItemType Directory -Path $results -Force | Out-Null
& icacls.exe $results /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' "${accountIdentity}:(OI)(CI)RX" | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Cannot protect task results' }
& icacls.exe $results /setowner '*S-1-5-32-544' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Cannot assign results owner' }
[Reflection.Assembly]::LoadFrom($worker) | Out-Null
$workerBoot = [DiscordDesktopPower.ShutdownWorker]::ProbeBoot()
$expectedBoot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().Ticks.ToString([Globalization.CultureInfo]::InvariantCulture)
if ($workerBoot -cne $expectedBoot -or $workerBoot -eq '0') { throw 'Worker boot query does not match the dispatcher' }

$scheduler = New-Object -ComObject 'Schedule.Service'
$scheduler.Connect()
try { $folder = $scheduler.GetFolder('\SshDiscordBotDesktopPower') } catch { $folder = $null }
if ($folder) {
    foreach ($existing in $folder.GetTasks(1)) {
        if ($existing.Name -ne 'DesktopShutdown' -or $existing.Definition.RegistrationInfo.Source -ne $source) {
            throw 'Existing task folder contains an unrelated task'
        }
    }
} else {
    $folder = $scheduler.GetFolder('\').CreateFolder('SshDiscordBotDesktopPower', $sddl)
}
$folder.SetSecurityDescriptor($sddl, 0)
$definition = $scheduler.NewTask(0)
$definition.RegistrationInfo.Source = $source
$definition.RegistrationInfo.Description = 'On-demand local normal shutdown only; no force and no reboot.'
$definition.Principal.UserId = 'S-1-5-18'
$definition.Principal.LogonType = 5
$definition.Principal.RunLevel = 1
$definition.Settings.Enabled = $true
$definition.Settings.AllowDemandStart = $true
$definition.Settings.StartWhenAvailable = $false
$definition.Settings.DisallowStartIfOnBatteries = $false
$definition.Settings.StopIfGoingOnBatteries = $false
$definition.Settings.MultipleInstances = 2
$definition.Settings.ExecutionTimeLimit = 'PT1M'
$action = $definition.Actions.Create(0)
$action.Path = $worker
$action.WorkingDirectory = $controlPath
$action.Arguments = '"$(Arg0)" "$(Arg1)"'
# No triggers: registration and Windows boot never request a shutdown.
$task = $folder.RegisterTaskDefinition('DesktopShutdown', $definition, 6, 'S-1-5-18', $null, 5, $sddl)
if ($task.Definition.Triggers.Count -ne 0 -or $task.Definition.Actions.Count -ne 1 -or $task.Definition.Actions.Item(1).Path -ne $worker) {
    throw 'Registered task does not match the fixed worker definition'
}

# A deliberately stale boot ID tests worker execution without calling shutdown.
$probeId = [guid]::NewGuid().ToString('N')
$task.Run([string[]]@('000000000000000000', $probeId)) | Out-Null
$probePath = Join-Path $results ($probeId + '.json')
$deadline = [DateTime]::UtcNow.AddSeconds(15)
while (-not (Test-Path -LiteralPath $probePath) -and [DateTime]::UtcNow -lt $deadline) { Start-Sleep -Milliseconds 100 }
if (-not (Test-Path -LiteralPath $probePath)) { throw 'Worker validation result was not received' }
$probe = Get-Content -LiteralPath $probePath -Raw | ConvertFrom-Json
if ($probe.status -cne 'BOOT_CHANGED' -or $probe.request_id -cne $probeId) { throw 'Stale boot validation did not reject safely' }
Write-Output 'On-demand shutdown task installed; stale-boot probe rejected without shutdown'
