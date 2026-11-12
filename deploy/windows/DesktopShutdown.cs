// Local-only shutdown bridge. No remote target, forced closure, or restart.
using System;
using System.Runtime.InteropServices;

namespace DiscordDesktopPower
{
    public static class DesktopShutdown
    {
        public static int CheckPrivilege()
        {
            return ShutdownOperations.Execute(new Win32ShutdownNative(), false);
        }

        public static int Shutdown()
        {
            return ShutdownOperations.Execute(new Win32ShutdownNative(), true);
        }
    }

    internal interface IShutdownNative
    {
        int EnablePrivilege(out IDisposable scope);
        int RequestShutdown(string machine, uint timeout, bool force, bool reboot, uint reason);
    }

    internal static class ShutdownOperations
    {
        internal static int Execute(IShutdownNative native, bool requestShutdown)
        {
            IDisposable scope = null;
            try
            {
                int error = native.EnablePrivilege(out scope);
                if (error != 0) return error;
                if (!requestShutdown) return 0;
                // NULL means this computer. FALSE preserves unsaved apps.
                return native.RequestShutdown(null, 0, false, false, 0x80000000);
            }
            finally
            {
                if (scope != null) scope.Dispose();
            }
        }
    }

    internal sealed class Win32ShutdownNative : IShutdownNative
    {
        [StructLayout(LayoutKind.Sequential)]
        private struct Luid { public uint Low; public int High; }

        [StructLayout(LayoutKind.Sequential)]
        private struct TokenPrivileges
        {
            public uint Count;
            public Luid Privilege;
            public uint Attributes;
        }

        [DllImport("kernel32.dll")] private static extern IntPtr GetCurrentProcess();
        [DllImport("kernel32.dll")] private static extern IntPtr GetCurrentThread();
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CloseHandle(IntPtr handle);
        [DllImport("advapi32.dll", SetLastError = true)]
        private static extern bool OpenProcessToken(IntPtr process, uint access, out IntPtr token);
        [DllImport("advapi32.dll", SetLastError = true)]
        private static extern bool OpenThreadToken(IntPtr thread, uint access, bool asSelf, out IntPtr token);
        [DllImport("advapi32.dll", EntryPoint = "LookupPrivilegeValueW", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool LookupPrivilegeValue(string system, string name, out Luid privilege);
        [DllImport("advapi32.dll", SetLastError = true)]
        private static extern bool AdjustTokenPrivileges(IntPtr token, bool disableAll,
            ref TokenPrivileges state, uint size, out TokenPrivileges previous, out uint returned);
        [DllImport("advapi32.dll", EntryPoint = "AdjustTokenPrivileges", SetLastError = true)]
        private static extern bool RestoreTokenPrivileges(IntPtr token, bool disableAll,
            ref TokenPrivileges state, uint size, IntPtr previous, IntPtr returned);
        [DllImport("advapi32.dll", EntryPoint = "InitiateSystemShutdownExW", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool InitiateSystemShutdownEx(string machine, string message,
            uint timeout, bool force, bool reboot, uint reason);

        private sealed class PrivilegeScope : IDisposable
        {
            internal IntPtr Token;
            internal TokenPrivileges Previous;
            internal bool Restore;

            public void Dispose()
            {
                if (Token == IntPtr.Zero) return;
                try
                {
                    if (Restore && Previous.Count > 0)
                        RestoreTokenPrivileges(Token, false, ref Previous, 0, IntPtr.Zero, IntPtr.Zero);
                }
                finally
                {
                    CloseHandle(Token);
                    Token = IntPtr.Zero;
                }
            }
        }

        public int EnablePrivilege(out IDisposable scope)
        {
            scope = null;
            IntPtr token;
            const uint access = 0x20 | 0x08; // ADJUST_PRIVILEGES | QUERY
            if (!OpenThreadToken(GetCurrentThread(), access, true, out token))
            {
                int error = Marshal.GetLastWin32Error();
                if (error != 1008) return error; // ERROR_NO_TOKEN: use primary token
                if (!OpenProcessToken(GetCurrentProcess(), access, out token))
                    return Marshal.GetLastWin32Error();
            }
            PrivilegeScope owned = new PrivilegeScope();
            owned.Token = token;
            scope = owned;
            Luid privilege;
            if (!LookupPrivilegeValue(null, "SeShutdownPrivilege", out privilege))
                return Marshal.GetLastWin32Error();
            TokenPrivileges desired = new TokenPrivileges();
            desired.Count = 1;
            desired.Privilege = privilege;
            desired.Attributes = 2; // SE_PRIVILEGE_ENABLED
            uint returned;
            bool changed = AdjustTokenPrivileges(token, false, ref desired,
                (uint)Marshal.SizeOf(typeof(TokenPrivileges)), out owned.Previous, out returned);
            int result = Marshal.GetLastWin32Error();
            owned.Restore = changed;
            // A TRUE result can still report ERROR_NOT_ALL_ASSIGNED (1300).
            return changed ? result : (result == 0 ? 1314 : result);
        }

        public int RequestShutdown(string machine, uint timeout, bool force, bool reboot, uint reason)
        {
            if (InitiateSystemShutdownEx(machine, "Discord desktop shutdown", timeout, force, reboot, reason))
                return 0;
            return Marshal.GetLastWin32Error();
        }
    }
}
