param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$Email = "local-check@example.com"
)

$ErrorActionPreference = "Stop"

Write-Host "[1/6] Health check..."
$health = Invoke-RestMethod -Method Get -Uri "$BaseUrl/health"
if ($health.status -ne "ok") { throw "Health failed" }

Write-Host "[2/6] Dev login..."
$loginBody = @{ email = $Email } | ConvertTo-Json
$tokens = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/auth/dev/login" -ContentType "application/json" -Body $loginBody
$access = $tokens.access_token
if (-not $access) { throw "No access token" }
$headers = @{ Authorization = "Bearer $access" }

Write-Host "[3/6] Prepare FB2 file..."
$tmp = Join-Path $env:TEMP "reader_smoke.fb2"
@"
<?xml version='1.0' encoding='utf-8'?>
<FictionBook xmlns='http://www.gribuser.ru/xml/fictionbook/2.0'>
  <description><title-info><book-title>Smoke Book</book-title></title-info></description>
  <body>
    <section><title><p>One</p></title><p>Hello smoke</p></section>
    <section><title><p>Two</p></title><p>World smoke</p></section>
  </body>
</FictionBook>
"@ | Set-Content -Encoding UTF8 $tmp

Write-Host "[4/6] Upload via API..."
$form = @{ title = "Smoke Book"; author = "Smoke"; visibility = "private"; file = Get-Item $tmp }
$upload = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/books/upload" -Headers $headers -Form $form
$bookId = $upload.book_id
if (-not $bookId) { throw "Upload failed" }

Write-Host "[5/6] Wait for processing..."
$ready = $false
for ($i = 0; $i -lt 25; $i++) {
    Start-Sleep -Seconds 1
    $lib = Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/v1/library?page=1&page_size=30" -Headers $headers
    $item = $lib.items | Where-Object { $_.id -eq $bookId }
    if ($item -and ($item.status -eq "ready" -or $item.status -eq "failed")) {
        Write-Host "Status: $($item.status)"
        if ($item.status -eq "ready") { $ready = $true }
        break
    }
}
if (-not $ready) { throw "Book not ready in time" }

Write-Host "[6/6] Verify processed chapters endpoint..."
$chapters = Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/v1/books/$bookId/chapters" -Headers $headers
if (-not $chapters -or $chapters.Count -lt 1) { throw "No chapters returned" }

Write-Host "SMOKE CHECK PASSED. BookId=$bookId, chapters=$($chapters.Count)"
