param(
  [string]$InstallRoot = "C:\Program Files\VOXEL\Router",
  [string]$DataRoot = "C:\ProgramData\VOXEL\Router"
)

$ErrorActionPreference = 'Stop'
if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "Execute este instalador em PowerShell elevado."
}

New-Item -ItemType Directory -Force -Path $InstallRoot, $DataRoot, "$DataRoot\spool", "$DataRoot\quarantine", "$DataRoot\database", "$DataRoot\logs", "$DataRoot\config" | Out-Null
# A ACL final deve ser aplicada à conta de serviço escolhida durante a instalação.
$serviceName = 'VOXELRouterService'
$binary = "`"$InstallRoot\voxel-router-service.exe`""
if (Get-Service -Name $serviceName -ErrorAction SilentlyContinue) {
  Stop-Service $serviceName -Force
  sc.exe delete $serviceName | Out-Null
}
sc.exe create $serviceName binPath= $binary start= auto DisplayName= "VOXEL Router Service" | Out-Null
sc.exe failure $serviceName reset= 86400 actions= restart/5000/restart/15000/restart/60000 | Out-Null
Set-Service -Name $serviceName -StartupType Automatic
Write-Host "VOXEL Router preparado. Configure AE Title, Cloud e allowlists antes de iniciar o serviço." -ForegroundColor Green
