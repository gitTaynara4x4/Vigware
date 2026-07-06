param(
  [Parameter(Mandatory=$true)][string]$BaseUrl,
  [Parameter(Mandatory=$true)][string]$Key
)

$body = @{
  account_code = "0073"
  event_code = "1250"
  description = "Falha de keep alive"
  info_1 = "---"
  info_2 = "---"
  date_time = "06/07/26 04:48:10"
  row = @{
    Conta = "0073"
    Evento = "1250"
    Descricao = "Falha de keep alive"
    "Informacao 1" = "---"
    "Informacao 2" = "---"
    "Data e hora" = "06/07/26 04:48:10"
  }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
  -Uri "$($BaseUrl.TrimEnd('/'))/api/receiver/activenet" `
  -Method POST `
  -Headers @{ "X-Vigware-Key" = $Key } `
  -ContentType "application/json" `
  -Body $body
