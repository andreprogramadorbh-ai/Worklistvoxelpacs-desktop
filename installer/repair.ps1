[CmdletBinding()]
param(
  [string]$InstallRoot = "C:\Program Files\VOXEL\Router",
  [string]$DataRoot = "C:\ProgramData\VOXEL\Router",
  [string]$RouterAETitle = "VOXEL_ROUTER",
  [int]$DicomPort = 11112,
  [string[]]$AllowedCallingAes = @("VOXEL_TEST_SCU"),
  [string[]]$AllowedSourceCidrs = @("127.0.0.1/32")
)

$ErrorActionPreference = "Stop"
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "Execute repair.ps1 em um PowerShell iniciado como administrador."
}

$installScript = Join-Path $PSScriptRoot "install.ps1"
$testScript = Join-Path $PSScriptRoot "test-reception.ps1"
if (-not (Test-Path $installScript) -or -not (Test-Path $testScript)) {
  throw "O pacote está incompleto. Extraia novamente VOXELRouterPackage.zip antes de executar o reparo."
}

Write-Host "Reinstalando o VOXEL Router..." -ForegroundColor Cyan
& $installScript `
  -InstallRoot $InstallRoot `
  -DataRoot $DataRoot `
  -RouterAETitle $RouterAETitle `
  -DicomPort $DicomPort `
  -AllowedCallingAes $AllowedCallingAes `
  -AllowedSourceCidrs $AllowedSourceCidrs
if ($LASTEXITCODE -ne 0) {
  throw "A reinstalação falhou. Consulte $DataRoot\logs\router.log."
}

Write-Host "Executando validação DICOM sintética..." -ForegroundColor Cyan
& $testScript -InstallRoot $InstallRoot -RouterAETitle $RouterAETitle -DicomPort $DicomPort
if ($LASTEXITCODE -ne 0) {
  throw "O serviço foi instalado, mas o teste DICOM falhou. Consulte $DataRoot\logs\router.log."
}

Write-Host "REPARO_E_TESTE_CONCLUIDOS" -ForegroundColor Green
