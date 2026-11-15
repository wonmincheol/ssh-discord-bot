using System;
using System.Globalization;
using System.IO;
using System.Management;
using System.Text;
using System.Text.RegularExpressions;

namespace DiscordDesktopPower
{
    public static class ShutdownWorker
    {
        public static int Main(string[] args)
        {
            return WorkerOperations.Execute(args, new WindowsWorkerPlatform());
        }

        public static string ProbeBoot()
        {
            return new WindowsWorkerPlatform().GetBootId();
        }
    }

    internal interface IWorkerPlatform
    {
        string GetBootId();
        int Shutdown();
        void WriteResult(string requestId, string boot, string status, int error);
    }

    internal static class WorkerOperations
    {
        internal static int Execute(string[] args, IWorkerPlatform platform)
        {
            if (args == null || args.Length != 2 || String.IsNullOrEmpty(args[0]) || String.IsNullOrEmpty(args[1]) ||
                !Regex.IsMatch(args[0], @"\A[0-9]{10,20}\z") ||
                !Regex.IsMatch(args[1], @"\A[0-9a-fA-F]{32}\z")) return 87;
            string boot = args[0];
            string requestId = args[1].ToLowerInvariant();
            bool attempted = false;
            try
            {
                if (platform.GetBootId() != boot)
                {
                    platform.WriteResult(requestId, boot, "BOOT_CHANGED", 0);
                    return 1;
                }
                attempted = true;
                int error = platform.Shutdown();
                platform.WriteResult(requestId, boot, error == 0 ? "REQUESTED" : "REJECTED", error);
                return error;
            }
            catch
            {
                // Once request delivery is possible, never report a safe retry.
                try { platform.WriteResult(requestId, boot, attempted ? "UNKNOWN" : "FAILED", 31); }
                catch { }
                return 31;
            }
        }
    }

    internal sealed class WindowsWorkerPlatform : IWorkerPlatform
    {
        public string GetBootId()
        {
            // ProbeBoot and the stale-boot installation test must also validate
            // the real dependency and privilege path without requesting power-off.
            int privilegeError = DesktopShutdown.CheckPrivilege();
            if (privilegeError != 0) throw new InvalidOperationException("Shutdown privilege activation failed");
            using (ManagementObjectSearcher search = new ManagementObjectSearcher(
                "SELECT LastBootUpTime FROM Win32_OperatingSystem"))
            using (ManagementObjectCollection objects = search.Get())
            {
                foreach (ManagementObject instance in objects)
                using (instance)
                {
                    string value = (string)instance["LastBootUpTime"];
                    return ManagementDateTimeConverter.ToDateTime(value).ToUniversalTime().Ticks.ToString(
                        CultureInfo.InvariantCulture);
                }
            }
            throw new InvalidOperationException("Boot information is unavailable");
        }

        public int Shutdown()
        {
            return DesktopShutdown.Shutdown();
        }

        public void WriteResult(string requestId, string boot, string status, int error)
        {
            string directory = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "results");
            string destination = Path.Combine(directory, requestId + ".json");
            string temporary = Path.Combine(directory, requestId + ".tmp");
            string json = "{\"request_id\":\"" + requestId + "\",\"boot\":\"" + boot +
                "\",\"status\":\"" + status + "\",\"error\":" + error.ToString(CultureInfo.InvariantCulture) + "}";
            File.WriteAllText(temporary, json, new UTF8Encoding(false));
            File.Move(temporary, destination);
        }
    }
}
