[CmdletBinding()]
param(
  [string]$InstallRoot = "C:\Program Files\VOXEL\Router",
  [string]$DataRoot = "C:\ProgramData\VOXEL\Router",
  [switch]$RemoveData
)

$ErrorActionPreference = "Stop"
$serviceName = "VOXELRouterService"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "Execute a desinstalação em um PowerShell elevado (Executar como administrador)."
}

$service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if ($service) {
  if ($service.Status -ne "Stopped") {
    Stop-Service -Name $serviceName -Force
  }
  & sc.exe delete $serviceName | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "Falha ao remover o serviço Windows." }
}

Get-NetFirewallRule -DisplayName "VOXEL Router DICOM C-STORE (*)" -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
Get-NetFirewallRule -DisplayName "VOXEL Router MWL (*)" -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
$shortcutPath = Join-Path $env:ProgramData "Microsoft\Windows\Start Menu\Programs\VOXEL PACS\VOXEL Router Desktop.lnk"
Remove-Item -LiteralPath $shortcutPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $InstallRoot -Force -Recurse -ErrorAction SilentlyContinue

if ($RemoveData) {
  Remove-Item -LiteralPath $DataRoot -Force -Recurse -ErrorAction SilentlyContinue
  Write-Host "Desinstalação concluída e dados locais removidos." -ForegroundColor Yellow
} else {
  Write-Host "Desinstalação concluída. Dados, fila e logs foram preservados em $DataRoot." -ForegroundColor Green
  Write-Host "Use -RemoveData somente após confirmar que não há estudos pendentes no spool/fila." -ForegroundColor Yellow
}
