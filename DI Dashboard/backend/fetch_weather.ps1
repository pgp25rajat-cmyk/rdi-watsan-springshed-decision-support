param([Parameter(Mandatory=$true)][string]$Url)
$ErrorActionPreference = 'Stop'
$parsedUrl = [Uri]$Url
if ($parsedUrl.Scheme -ne 'https' -or $parsedUrl.Host -ne 'archive-api.open-meteo.com' -or $parsedUrl.AbsolutePath -ne '/v1/archive') { throw 'Unexpected rainfall provider URL.' }
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
# Uses normal Windows HTTPS certificate validation. Never override it.
$response = Invoke-WebRequest -Uri $parsedUrl -UseBasicParsing -TimeoutSec 18 -Headers @{'User-Agent'='WATSAN-DI-Dashboard/2.0'}
[Console]::Out.Write($response.Content)
