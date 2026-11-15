"""Exercise fixed task dispatch and fake native policy; never shut down Windows."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


WINDOWS = Path(os.environ.get("SystemRoot", "C:/Windows"))
POWERSHELL = WINDOWS / "System32/WindowsPowerShell/v1.0/powershell.exe"
COMPILER = WINDOWS / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
DISPATCHER = Path(__file__).resolve().parents[1] / "deploy/windows/DesktopPower.ps1"
NATIVE_SOURCE = DISPATCHER.with_name("DesktopShutdown.cs")
WORKER_SOURCE = DISPATCHER.with_name("DesktopShutdownWorker.cs")
BOOT = "638712864000000000"  # UTC 2025-01-01


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


@unittest.skipUnless(os.name == "nt" and POWERSHELL.is_file() and COMPILER.is_file(),
                     "Windows PowerShell and the .NET Framework compiler are required")
class WindowsDesktopDispatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        cls.calls = cls.root / "shutdown-calls.txt"
        cls.fake_broker = cls.root / "FakeBroker.ps1"
        cls.fake_broker.write_text('''function script:Test-DesktopShutdownTask { return $env:DESKTOP_TEST_BROKER_FOUND -ceq '1' }
function script:Invoke-DesktopShutdownTask {
    param([string]$ExpectedBoot)
    [IO.File]::AppendAllText($env:DESKTOP_TEST_CALLS, "task`n")
    $errorCode = [int]$env:DESKTOP_TEST_EXIT
    $status = if ($errorCode -eq 0) { 'REQUESTED' } else { 'REJECTED' }
    if ($env:DESKTOP_TEST_TASK_STATUS) { $status = $env:DESKTOP_TEST_TASK_STATUS }
    return [pscustomobject]@{ status=$status; error=$errorCode; boot=$ExpectedBoot }
}
''', encoding="utf-8")
        harness = cls.root / "NativePolicyTests.cs"
        harness.write_text('''using System;
using DiscordDesktopPower;
class FakeNative : IShutdownNative, IDisposable {
    internal int EnableError, ShutdownError, Calls, Disposals;
    internal bool ThrowOnRequest;
    public int EnablePrivilege(out IDisposable scope) { scope = this; return EnableError; }
    public int RequestShutdown(string machine, uint timeout, bool force, bool reboot, uint reason) {
        if (machine != null || timeout != 0 || force || reboot || reason != 0x80000000)
            throw new Exception("Unsafe native shutdown arguments");
        Calls++;
        if (ThrowOnRequest) throw new InvalidOperationException("test error");
        return ShutdownError;
    }
    public void Dispose() { Disposals++; }
}
class FakeWorker : IWorkerPlatform {
    internal string Boot = "638712864000000000", Status;
    internal int Calls, BootQueries, Error, ResultError;
    internal bool ThrowShutdown;
    public string GetBootId() { BootQueries++; return Boot; }
    public int Shutdown() { Calls++; if (ThrowShutdown) throw new Exception("test error"); return Error; }
    public void WriteResult(string id, string boot, string status, int error) { Status = status; ResultError = error; }
}
class NativePolicyTests {
    static void Check(bool condition) { if (!condition) throw new Exception("Native policy check failed"); }
    static int Main() {
        FakeNative probe = new FakeNative();
        Check(ShutdownOperations.Execute(probe, false) == 0 && probe.Calls == 0 && probe.Disposals == 1);
        FakeNative accepted = new FakeNative();
        Check(ShutdownOperations.Execute(accepted, true) == 0 && accepted.Calls == 1 && accepted.Disposals == 1);
        FakeNative missing = new FakeNative(); missing.EnableError = 1300;
        Check(ShutdownOperations.Execute(missing, true) == 1300 && missing.Calls == 0 && missing.Disposals == 1);
        FakeNative denied = new FakeNative(); denied.ShutdownError = 5;
        Check(ShutdownOperations.Execute(denied, true) == 5 && denied.Calls == 1 && denied.Disposals == 1);
        FakeNative throwing = new FakeNative(); throwing.ThrowOnRequest = true;
        try { ShutdownOperations.Execute(throwing, true); throw new Exception("Exception was lost"); }
        catch (InvalidOperationException) { Check(throwing.Disposals == 1); }
        string id = "0123456789abcdef0123456789abcdef";
        FakeWorker good = new FakeWorker();
        Check(WorkerOperations.Execute(new string[] {good.Boot, id}, good) == 0 && good.Calls == 1 && good.Status == "REQUESTED");
        FakeWorker stale = new FakeWorker();
        Check(WorkerOperations.Execute(new string[] {"000000000000000000", id}, stale) == 1 && stale.Calls == 0 && stale.Status == "BOOT_CHANGED");
        foreach (string[] args in new string[][] {
            new string[] {"638712864000000000;whoami", id}, new string[] {good.Boot, "../../escape"},
            new string[] {good.Boot, id, "extra"}, new string[] {null, id},
            new string[] {good.Boot + "\\n", id}}) {
            FakeWorker invalid = new FakeWorker();
            Check(WorkerOperations.Execute(args, invalid) == 87 && invalid.Calls == 0 && invalid.BootQueries == 0);
        }
        FakeWorker rejected = new FakeWorker(); rejected.Error = 5;
        Check(WorkerOperations.Execute(new string[] {rejected.Boot, id}, rejected) == 5 && rejected.Status == "REJECTED" && rejected.ResultError == 5);
        FakeWorker uncertain = new FakeWorker(); uncertain.ThrowShutdown = true;
        Check(WorkerOperations.Execute(new string[] {uncertain.Boot, id}, uncertain) == 31 && uncertain.Status == "UNKNOWN");
        Console.WriteLine("Native shutdown policy checks: OK");
        return 0;
    }
}
''', encoding="utf-8")
        cls.native_tests = cls.root / "NativePolicyTests.exe"
        subprocess.run([str(COMPILER), "/nologo", "/target:exe", "/main:NativePolicyTests", "/reference:System.Management.dll",
                        "/out:" + str(cls.native_tests), str(NATIVE_SOURCE), str(WORKER_SOURCE), str(harness)],
                       check=True, capture_output=True, text=True, timeout=30)
        cls.installed = cls.root / "installed"
        cls.installed.mkdir()
        production_library = cls.installed / "DesktopShutdown.dll"
        cls.installed_worker = cls.installed / "DesktopShutdownWorker.exe"
        subprocess.run([str(COMPILER), "/nologo", "/target:library", "/out:" + str(production_library), str(NATIVE_SOURCE)],
                       check=True, capture_output=True, text=True, timeout=30)
        subprocess.run([str(COMPILER), "/nologo", "/target:exe", "/main:DiscordDesktopPower.ShutdownWorker",
                        "/out:" + str(cls.installed_worker), "/reference:" + str(production_library),
                        "/reference:System.Management.dll", str(WORKER_SOURCE)],
                       check=True, capture_output=True, text=True, timeout=30)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def dispatch(self, command, exit_code=0, fail_probe=False, broker_found=True, task_status=""):
        self.calls.unlink(missing_ok=True)
        source = DISPATCHER.read_text(encoding="utf-8")
        broker_path = "(Join-Path $PSScriptRoot 'DesktopShutdownTask.ps1')"
        self.assertEqual(source.count(broker_path), 1)
        source = source.replace(broker_path, ps_quote(self.fake_broker))
        script = "\n".join([
            "$env:DESKTOP_TEST_CALLS = " + ps_quote(self.calls),
            "$env:DESKTOP_TEST_EXIT = " + ps_quote(exit_code),
            "$env:DESKTOP_TEST_BROKER_FOUND = " + ps_quote(int(broker_found)),
            "$env:DESKTOP_TEST_TASK_STATUS = " + ps_quote(task_status),
            "$env:SSH_ORIGINAL_COMMAND = " + ps_quote(command),
            "function global:Add-Type { throw 'Dispatcher must not load the shutdown API' }",
            "function global:Get-CimInstance { param($ClassName) " + (
                "throw 'test probe failure' }" if fail_probe else
                "[pscustomobject]@{LastBootUpTime = [datetime]::new(2025, 1, 1, 0, 0, 0, [DateTimeKind]::Utc)} }"
            ),
            "& ([scriptblock]::Create(" + ps_quote(source) + "))",
        ])
        result = subprocess.run([str(POWERSHELL), "-NoLogo", "-NoProfile", "-NonInteractive",
                                 "-ExecutionPolicy", "Bypass", "-Command", script],
                                capture_output=True, text=True, timeout=15)
        calls = self.calls.read_text().splitlines() if self.calls.exists() else []
        return result, calls

    def test_check_reports_boot_id_without_invoking_shutdown(self):
        result, calls = self.dispatch("desktop-check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "DESKTOP_READY " + BOOT)
        self.assertEqual(calls, [])

    def test_shutdown_reports_fixed_task_acceptance(self):
        result, calls = self.dispatch("desktop-off " + BOOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "DESKTOP_SHUTDOWN_REQUESTED " + BOOT)
        self.assertEqual(calls, ["task"])

    def test_diagnose_checks_task_without_loading_native_api_or_requesting_shutdown(self):
        result, calls = self.dispatch("desktop-diagnose")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "DESKTOP_DIAGNOSTICS BROKER_FOUND=1")
        self.assertEqual(calls, [])

    def test_diagnose_reports_missing_task_without_requesting_shutdown(self):
        result, calls = self.dispatch("desktop-diagnose", broker_found=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "DESKTOP_DIAGNOSTICS BROKER_FOUND=0")
        self.assertEqual(calls, [])

    def test_native_operations_preserve_apps_and_never_reboot_or_shutdown_during_probe(self):
        result = subprocess.run([str(self.native_tests)], check=True, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.stdout.strip(), "Native shutdown policy checks: OK")

    def test_installed_worker_dependencies_match_physical_assembly_file_names(self):
        # Inspect metadata only: never invoke this production worker or its API.
        script = "\n".join([
            "$assembly = [Reflection.Assembly]::ReflectionOnlyLoadFrom(" + ps_quote(self.installed_worker) + ")",
            "$references = @($assembly.GetReferencedAssemblies() | Where-Object Name -like 'DesktopShutdown*')",
            "if ($references.Count -ne 1 -or $references[0].Name -cne 'DesktopShutdown') { exit 1 }",
            "$dependency = Join-Path " + ps_quote(self.installed) + " ($references[0].Name + '.dll')",
            "if (-not (Test-Path -LiteralPath $dependency)) { exit 2 }",
            "if ([Reflection.AssemblyName]::GetAssemblyName($dependency).Name -cne $references[0].Name) { exit 3 }",
            "Write-Output 'Worker dependency identity: OK'",
        ])
        result = subprocess.run([str(POWERSHELL), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script],
                                check=True, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.stdout.strip(), "Worker dependency identity: OK")

    def test_uncertain_task_delivery_is_not_reported_as_rejected_or_accepted(self):
        result, calls = self.dispatch("desktop-off " + BOOT, exit_code=31, task_status="UNKNOWN")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout.strip(), "")
        self.assertEqual(calls, ["task"])

    def test_restart_between_probe_and_request_is_rejected(self):
        old_boot = "638712863000000000"
        result, calls = self.dispatch("desktop-off " + old_boot)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout.strip(), "DESKTOP_SHUTDOWN_REJECTED " + old_boot)
        self.assertEqual(result.stderr.strip(), "DESKTOP_BOOT_CHANGED")
        self.assertEqual(calls, [])

    def test_windows_rejection_is_not_reported_as_accepted(self):
        result, calls = self.dispatch("desktop-off " + BOOT, exit_code=5)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout.strip(), "DESKTOP_SHUTDOWN_REJECTED " + BOOT)
        self.assertEqual(result.stderr.strip(), "DESKTOP_WINDOWS_ERROR 5")
        self.assertEqual(calls, ["task"])

    def test_probe_failure_never_invokes_shutdown(self):
        result, calls = self.dispatch("desktop-off " + BOOT, fail_probe=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout.strip(), "")
        self.assertEqual(calls, [])

    def test_shell_commands_and_malformed_requests_are_rejected(self):
        for command in ("", "whoami", "desktop-check; whoami", "desktop-off",
                        "desktop-off " + BOOT + "; whoami", "desktop-off " + BOOT + "\nwhoami",
                        "desktop-off " + BOOT + "\n"):
            with self.subTest(command=command):
                result, calls = self.dispatch(command)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout.strip(), "")
                self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
