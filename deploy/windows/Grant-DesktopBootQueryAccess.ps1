#Requires -RunAsAdministrator
param([string]$AccountName = 'desktopbot')
$ErrorActionPreference = 'Stop'

$account = Get-LocalUser -Name $AccountName
if (Get-LocalGroupMember -SID 'S-1-5-32-544' | Where-Object { $_.SID -eq $account.SID }) {
    throw 'Use a non-administrator desktop control account'
}
$sidBytes = New-Object byte[] $account.SID.BinaryLength
$account.SID.GetBinaryForm($sidBytes, 0)
$sidEncoded = [Convert]::ToBase64String($sidBytes)
$security = Invoke-CimMethod -Namespace root/cimv2 -ClassName __SystemSecurity -MethodName GetSecurityDescriptor
if ($security.ReturnValue -ne 0 -or -not $security.Descriptor) {
    throw 'Cannot read the existing WMI namespace security descriptor'
}
$descriptor = $security.Descriptor
if (-not $descriptor.DACL) { throw 'Refusing to replace an empty or absent WMI DACL' }
$entries = @($descriptor.DACL)
$hasRead = $entries | Where-Object {
    $_.AceType -eq 0 -and ($_.AccessMask -band 33) -eq 33 -and $_.Trustee.SID -and
    [Convert]::ToBase64String([byte[]]$_.Trustee.SID) -eq $sidEncoded
}
if (-not $hasRead) {
    $trustee = New-CimInstance -Namespace root/cimv2 -ClassName Win32_Trustee -ClientOnly -Property @{
        SID = [byte[]]$sidBytes
        SidLength = [uint32]$sidBytes.Length
    }
    # WBEM_ENABLE (1) + WBEM_REMOTE_ACCESS (32) allow query connections from
    # SSH network logons. No execute-methods, provider-write or ACL-write rights.
    $ace = New-CimInstance -Namespace root/cimv2 -ClassName Win32_ACE -ClientOnly -Property @{
        AccessMask = [uint32]33
        AceFlags = [uint32]0
        AceType = [uint32]0
        Trustee = $trustee
    }
    $descriptor.CimInstanceProperties['DACL'].Value = [Microsoft.Management.Infrastructure.CimInstance[]]@($entries + $ace)
    $result = Invoke-CimMethod -Namespace root/cimv2 -ClassName __SystemSecurity -MethodName SetSecurityDescriptor -Arguments @{ Descriptor = $descriptor }
    if ($result.ReturnValue -ne 0) { throw 'Cannot grant WMI query access' }
}
Write-Output 'WMI boot query read access: ready'
