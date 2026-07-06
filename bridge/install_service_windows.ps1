# Instala o Vigware Bridge como serviço Windows usando NSSM.
# Baixe o NSSM: https://nssm.cc/download
# Coloque nssm.exe em C:\nssm\nssm.exe ou ajuste o caminho abaixo.

$ErrorActionPreference = "Stop"
$BridgeDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Nssm = "C:\nssm\nssm.exe"
$ServiceName = "VigwareBridgeActiveNet"

if (!(Test-Path $Nssm)) {
  throw "nssm.exe não encontrado em $Nssm"
}

if (!(Test-Path "$BridgeDir\.venv")) {
  Set-Location $BridgeDir
  py -m venv .venv
  . .\.venv\Scripts\Activate.ps1
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
}

& $Nssm install $ServiceName "$BridgeDir\.venv\Scripts\python.exe" "$BridgeDir\vigware_bridge.py"
& $Nssm set $ServiceName AppDirectory $BridgeDir
& $Nssm set $ServiceName Start SERVICE_AUTO_START
& $Nssm start $ServiceName

Write-Host "Serviço instalado e iniciado: $ServiceName"
