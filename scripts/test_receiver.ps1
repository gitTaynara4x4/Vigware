param(
  [Parameter(Mandatory=$true)][string]$BaseUrl,
  [Parameter(Mandatory=$false)][string]$BridgeId = "activenet-matriz",
  [Parameter(Mandatory=$true)][string]$BridgeSecret
)

$BodyObject = @{
  source = "TESTE_HMAC"
  events = @(
    @{
      account_code = "0073"
      event_code = "1250"
      description = "Falha de keep alive"
      info_1 = "---"
      info_2 = "---"
      date_time = "06/07/26 04:48:10"
      row = @{ origem = "teste_receiver.ps1" }
    }
  )
}

$Body = $BodyObject | ConvertTo-Json -Depth 10 -Compress
$Timestamp = [string][int][double]::Parse((Get-Date -UFormat %s))
$Nonce = [guid]::NewGuid().ToString("N")
$Message = "$Timestamp.$Nonce.$Body"

$KeyBytes = [System.Text.Encoding]::UTF8.GetBytes($BridgeSecret)
$MsgBytes = [System.Text.Encoding]::UTF8.GetBytes($Message)
$Hmac = New-Object System.Security.Cryptography.HMACSHA256
$Hmac.Key = $KeyBytes
$HashBytes = $Hmac.ComputeHash($MsgBytes)
$HashHex = -join ($HashBytes | ForEach-Object { $_.ToString("x2") })
$Signature = "sha256=$HashHex"

$Headers = @{
  "X-Vigware-Bridge-Id" = $BridgeId
  "X-Vigware-Timestamp" = $Timestamp
  "X-Vigware-Nonce" = $Nonce
  "X-Vigware-Signature" = $Signature
}

Invoke-RestMethod `
  -Uri "$($BaseUrl.TrimEnd('/'))/api/receiver/activenet/batch" `
  -Method POST `
  -Headers $Headers `
  -ContentType "application/json; charset=utf-8" `
  -Body $Body
