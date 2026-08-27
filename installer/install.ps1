[CmdletBinding()]
param(
  [string]$InstallRoot = "C:\Program Files\VOXEL\Router",
  [string]$DataRoot = "C:\ProgramData\VOXEL\Router",
  [string]$RouterAETitle = "VOXEL_ROUTER",
  [int]$DicomPort = 11112,
  [string[]]$AllowedCallingAes = @("VOXEL_TEST_SCU"),
  [string[]]$AllowedSourceCidrs = @("127.0.0.1/32"),
  [switch]$UseLocalService,
  [switch]$OverwriteConfig,
  [switch]$OpenFirewallRule
)

$ErrorActionPreference = "Stop"
$serviceName = "VOXELRouterService"
$serviceDisplayName = "VOXEL Router Service"

function Assert-Administrator {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = [Security.Principal.WindowsPrincipal]::new($identity)
  if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Execute este instalador em um PowerShell elevado (Executar como administrador)."
  }
}

function Wait-ServiceRemoval {
  param([string]$Name)
  for ($attempt = 0; $attempt -lt 15; $attempt++) {
    if (-not (Get-Service -Name $Name -ErrorAction SilentlyContinue)) {
      return
    }
    Start-Sleep -Seconds 1
  }
  throw "O serviço $Name não foi removido no tempo esperado."
}

Assert-Administrator

$sourceServiceDirectory = Join-Path $PSScriptRoot "service"
$sourceDesktopDirectory = Join-Path $PSScriptRoot "desktop"
$sourceTestDirectory = Join-Path $PSScriptRoot "test"
$configTemplate = Join-Path $PSScriptRoot "config.template.json"
if (-not (Test-Path (Join-Path $sourceServiceDirectory "VOXELRouterService.exe"))) {
  throw "VOXELRouterService.exe não foi encontrado. Execute installer\build.ps1 e use o conteúdo de VOXELRouterPackage.zip."
}
if (-not (Test-Path (Join-Path $sourceDesktopDirectory "VOXELRouterDesktop.exe"))) {
  throw "VOXELRouterDesktop.exe não foi encontrado no pacote."
}
if (-not (Test-Path (Join-Path $sourceTestDirectory "VOXELRouterDicomTest.exe"))) {
  throw "VOXELRouterDicomTest.exe não foi encontrado no pacote."
}
if (-not (Test-Path $configTemplate)) {
  throw "config.template.json não foi encontrado no pacote."
}

$existingService = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if ($existingService) {
  if ($existingService.Status -ne "Stopped") {
    Stop-Service -Name $serviceName -Force -ErrorAction Stop
  }
  & sc.exe delete $serviceName | Out-Null
  Wait-ServiceRemoval -Name $serviceName
}

New-Item -ItemType Directory -Force -Path $InstallRoot, $DataRoot, (Join-Path $DataRoot "config"), (Join-Path $DataRoot "database"), (Join-Path $DataRoot "spool"), (Join-Path $DataRoot "quarantine"), (Join-Path $DataRoot "logs") | Out-Null
Copy-Item -Path (Join-Path $sourceServiceDirectory "*") -Destination $InstallRoot -Recurse -Force
Copy-Item -Path $sourceDesktopDirectory -Destination (Join-Path $InstallRoot "desktop") -Recurse -Force
Copy-Item -Path $sourceTestDirectory -Destination (Join-Path $InstallRoot "test") -Recurse -Force

$configPath = Join-Path $DataRoot "config\config.json"
if ($OverwriteConfig -or -not (Test-Path $configPath)) {
  $config = Get-Content -Raw -Path $configTemplate | ConvertFrom-Json
  $config.router_ae_title = $RouterAETitle.Trim().ToUpperInvariant()
  $config.dicom_port = $DicomPort
  $config.allowed_calling_aes = @($AllowedCallingAes | ForEach-Object { $_.Trim().ToUpperInvariant() } | Where-Object { $_ })
  $config.allowed_source_cidrs = @($AllowedSourceCidrs | ForEach-Object { $_.Trim() } | Where-Object { $_ })
  $configJson = $config | ConvertTo-Json -Depth 8
  [System.IO.File]::WriteAllText($configPath, $configJson, [System.Text.UTF8Encoding]::new($false))
}

# SYSTEM e Administradores têm controle total; LocalService tem somente modificação nos dados operacionais.
& icacls.exe $DataRoot /inheritance:r /grant:r "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-19:(OI)(CI)M" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Falha ao aplicar ACL em $DataRoot." }

$serviceExecutable = Join-Path $InstallRoot "VOXELRouterService.exe"
& $serviceExecutable --startup auto install
if ($LASTEXITCODE -ne 0) { throw "Falha ao registrar o serviço Windows." }

# Por compatibilidade, o serviço usa a conta LocalSystem padrão do Windows.
# LocalService pode ser habilitada explicitamente quando a política local permitir.
if ($UseLocalService) {
  & sc.exe config $serviceName obj= "NT AUTHORITY\LocalService" password= "" | Out-Null
  if ($LASTEXITCODE -ne 0) {
    Write-Warning "Não foi possível configurar LocalService; o serviço será mantido na conta padrão LocalSystem."
  }
}
& sc.exe failure $serviceName reset= 86400 actions= restart/5000/restart/15000/restart/60000 | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Falha ao configurar a recuperação automática do serviço." }

$shortcutDirectory = Join-Path $env:ProgramData "Microsoft\Windows\Start Menu\Programs\VOXEL PACS"
New-Item -ItemType Directory -Force -Path $shortcutDirectory | Out-Null
$shortcutPath = Join-Path $shortcutDirectory "VOXEL Router Desktop.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $InstallRoot "desktop\VOXELRouterDesktop.exe"
$shortcut.WorkingDirectory = Join-Path $InstallRoot "desktop"
$shortcut.Description = "Painel administrativo do VOXEL Router"
$shortcut.Save()

if ($OpenFirewallRule) {
  $storeRuleName = "VOXEL Router DICOM C-STORE ($DicomPort)"
  Get-NetFirewallRule -DisplayName $storeRuleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
  New-NetFirewallRule -DisplayName $storeRuleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $DicomPort -Profile Domain,Private | Out-Null
  $mwlRuleName = "VOXEL Router MWL ($($config.mwl_port))"
  Get-NetFirewallRule -DisplayName $mwlRuleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
  New-NetFirewallRule -DisplayName $mwlRuleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $config.mwl_port -Profile Domain,Private | Out-Null
}

Start-Service -Name $serviceName
for ($attempt = 0; $attempt -lt 15; $attempt++) {
  $currentService = Get-Service -Name $serviceName
  if ($currentService.Status -eq "Running") {
    Write-Host "Instalação concluída." -ForegroundColor Green
    Write-Host "AE Title: $RouterAETitle | Porta DICOM: $DicomPort" -ForegroundColor Green
    Write-Host "Configuração: $configPath" -ForegroundColor Cyan
    Write-Host "Painel visual: Menu Iniciar > VOXEL PACS > VOXEL Router Desktop" -ForegroundColor Cyan
    Write-Host "Teste local: .\test-reception.ps1" -ForegroundColor Cyan
    return
  }
  Start-Sleep -Seconds 1
}

throw "O serviço foi instalado, mas não entrou no estado Running. Consulte $DataRoot\logs\router.log."
