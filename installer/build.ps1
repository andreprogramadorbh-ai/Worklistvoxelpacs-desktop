[CmdletBinding()]
param(
  [string]$PythonCommand = "py",
  [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

if ($env:OS -ne "Windows_NT") {
  throw "O build do EXE deve ser executado no Windows para gerar binários Windows."
}

$repositoryRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
  $OutputDirectory = Join-Path $repositoryRoot "dist\windows"
}

$venvDirectory = Join-Path $repositoryRoot ".venv-build"
$venvPython = Join-Path $venvDirectory "Scripts\python.exe"
$workDirectory = Join-Path $repositoryRoot "build\pyinstaller"
$specDirectory = Join-Path $repositoryRoot "build\spec"

$pythonSelector = @()
if ($PythonCommand -eq "py") {
  $pythonSelector = @("-3.12")
}

& $PythonCommand @pythonSelector --version
if ($LASTEXITCODE -ne 0) {
  throw "Python 3.12 não está disponível por meio de '$PythonCommand'."
}
if (Test-Path $venvDirectory) {
  Remove-Item -Recurse -Force $venvDirectory
}
& $PythonCommand @pythonSelector -m venv $venvDirectory
if ($LASTEXITCODE -ne 0) {
  throw "Falha ao criar o ambiente de build com Python 3.12."
}

& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Falha ao atualizar pip." }
& $venvPython -m pip install -e ".[packaging]"
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar as dependências de empacotamento." }

Remove-Item -Recurse -Force $OutputDirectory, $workDirectory, $specDirectory -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $OutputDirectory, $workDirectory, $specDirectory | Out-Null

$commonArguments = @(
  "--noconfirm",
  "--clean",
  "--onedir",
  "--distpath", $OutputDirectory,
  "--workpath", $workDirectory,
  "--specpath", $specDirectory,
  "--hidden-import", "win32timezone",
  "--hidden-import", "pythoncom",
  "--hidden-import", "pywintypes",
  "--hidden-import", "win32crypt"
)

& $venvPython -m PyInstaller @commonArguments "--console" "--name" "VOXELRouterService" "app\windows_service.py"
if ($LASTEXITCODE -ne 0) { throw "Falha ao gerar VOXELRouterService.exe." }

& $venvPython -m PyInstaller @commonArguments "--windowed" "--uac-admin" "--name" "VOXELRouterDesktop" "desktop\main_window.py"
if ($LASTEXITCODE -ne 0) { throw "Falha ao gerar VOXELRouterDesktop.exe." }

$setupArguments = @($commonArguments | Where-Object { $_ -ne "--onedir" })
$setupArguments += "--onefile"
& $venvPython -m PyInstaller @setupArguments "--windowed" "--uac-admin" "--name" "VOXELRouterSetup" "installer\setup_windows.py"
if ($LASTEXITCODE -ne 0) { throw "Falha ao gerar VOXELRouterSetup.exe." }

& $venvPython -m PyInstaller @commonArguments "--console" "--name" "VOXELRouterDicomTest" "tools\test_reception.py"
if ($LASTEXITCODE -ne 0) { throw "Falha ao gerar VOXELRouterDicomTest.exe." }

$packageDirectory = Join-Path $OutputDirectory "VOXELRouterPackage"
New-Item -ItemType Directory -Force -Path $packageDirectory | Out-Null
Copy-Item -Recurse -Force (Join-Path $OutputDirectory "VOXELRouterService") (Join-Path $packageDirectory "service")
Copy-Item -Recurse -Force (Join-Path $OutputDirectory "VOXELRouterDesktop") (Join-Path $packageDirectory "desktop")
Copy-Item -Force (Join-Path $OutputDirectory "VOXELRouterSetup.exe") (Join-Path $packageDirectory "INSTALAR-VOXEL-ROUTER.exe")
Copy-Item -Recurse -Force (Join-Path $OutputDirectory "VOXELRouterDicomTest") (Join-Path $packageDirectory "test")
Copy-Item -Force (Join-Path $repositoryRoot "installer\install.ps1") $packageDirectory
Copy-Item -Force (Join-Path $repositoryRoot "installer\uninstall.ps1") $packageDirectory
Copy-Item -Force (Join-Path $repositoryRoot "installer\test-reception.ps1") $packageDirectory
Copy-Item -Force (Join-Path $repositoryRoot "installer\repair.ps1") $packageDirectory
Copy-Item -Force (Join-Path $repositoryRoot "installer\config.template.json") $packageDirectory
Copy-Item -Force (Join-Path $repositoryRoot "docs\WINDOWS_INSTALL.md") $packageDirectory
$commit = "local-source"
if (Get-Command git -ErrorAction SilentlyContinue) {
  $detectedCommit = & git -C $repositoryRoot rev-parse --short HEAD 2>$null
  if ($LASTEXITCODE -eq 0 -and $detectedCommit) {
    $commit = $detectedCommit.Trim()
  }
}
@(
  "VOXEL Router Windows Package",
  "Build UTC: $([DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ'))",
  "Commit: $commit",
  "Components: Windows Service, Visual Desktop, Graphic Installer, Local API, C-ECHO and C-STORE",
  "Validation: service, local API health, C-ECHO and C-STORE"
) | Set-Content -Path (Join-Path $packageDirectory "PACKAGE_INFO.txt") -Encoding UTF8

$archivePath = Join-Path $OutputDirectory "VOXELRouterPackage.zip"
@(
  "VOXEL ROUTER - INSTALACAO VISUAL",
  "",
  "1. Clique com o botao direito em INSTALAR-VOXEL-ROUTER.exe.",
  "2. Escolha Executar como administrador.",
  "3. Confirme o aviso do Windows e clique em INSTALAR E ABRIR PAINEL.",
  "",
  "Nao e necessario executar scripts PowerShell para a instalacao visual."
) | Set-Content -Path (Join-Path $packageDirectory "LEIA-PRIMEIRO.txt") -Encoding UTF8

Compress-Archive -Path (Join-Path $packageDirectory "*") -DestinationPath $archivePath -Force

Write-Host "Build concluído." -ForegroundColor Green
Write-Host "Pacote para distribuição: $archivePath" -ForegroundColor Green
Write-Host "Instalação: extraia o ZIP e execute install.ps1 em PowerShell elevado." -ForegroundColor Cyan
