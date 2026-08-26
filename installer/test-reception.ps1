[CmdletBinding()]
param(
  [string]$InstallRoot = "C:\Program Files\VOXEL\Router",
  [string]$RouterAETitle = "VOXEL_ROUTER",
  [int]$DicomPort = 11112,
  [string]$CallingAETitle = "VOXEL_TEST_SCU"
)

$ErrorActionPreference = "Stop"
$serviceName = "VOXELRouterService"
$testExecutable = Join-Path $InstallRoot "test\VOXELRouterDicomTest.exe"

$service = Get-Service -Name $serviceName -ErrorAction Stop
if ($service.Status -ne "Running") {
  throw "O serviço $serviceName está $($service.Status). Inicie-o antes do teste: Start-Service $serviceName"
}
if (-not (Test-Path $testExecutable)) {
  throw "Cliente de teste não encontrado: $testExecutable"
}

Write-Host "Executando C-ECHO e C-STORE sintéticos em 127.0.0.1:$DicomPort..." -ForegroundColor Cyan
& $testExecutable --host "127.0.0.1" --port $DicomPort --called-ae $RouterAETitle --calling-ae $CallingAETitle
if ($LASTEXITCODE -ne 0) {
  throw "Teste de recebimento falhou com código $LASTEXITCODE. Consulte C:\ProgramData\VOXEL\Router\logs\router.log."
}

Write-Host "Teste concluído: C-ECHO e C-STORE foram aceitos pelo Router." -ForegroundColor Green
