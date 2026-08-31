$ErrorActionPreference = "Continue"
$base = "http://localhost:3000"
$id = "4ed01c57-9446-4dd9-a7fd-488395f6eaed"
$root = "D:\.cursor\Cursor-projects\AutoExport\2_Processed_AI\drafts"

$patchPath = Join-Path $root "_c26089_patch.json"
$patchBytes = [System.IO.File]::ReadAllBytes($patchPath)

Write-Host "=== PATCH UTF8 FILE ==="
$patchResp = Invoke-WebRequest -Uri "$base/api/jobs/$id/patch" -Method POST -ContentType "application/json; charset=utf-8" -Body $patchBytes -UseBasicParsing
Write-Host "STATUS" $patchResp.StatusCode
[System.IO.File]::WriteAllText((Join-Path $root "_c26089_patch_resp.json"), $patchResp.Content, [System.Text.UTF8Encoding]::new($false))

Write-Host "=== RUN after_plan ==="
$runBytes = [System.Text.Encoding]::UTF8.GetBytes('{"wave":"after_plan"}')
try {
  $runResp = Invoke-WebRequest -Uri "$base/api/jobs/$id/run" -Method POST -ContentType "application/json; charset=utf-8" -Body $runBytes -UseBasicParsing
  Write-Host "STATUS" $runResp.StatusCode
  [System.IO.File]::WriteAllText((Join-Path $root "_c26089_run_resp.json"), $runResp.Content, [System.Text.UTF8Encoding]::new($false))
} catch {
  Write-Host "RUN_FAIL status-ish"
  $ex = $_.Exception
  Write-Host $ex.Message
  if ($ex.Response) {
    $stream = $ex.Response.GetResponseStream()
    $reader = New-Object System.IO.StreamReader($stream, [System.Text.Encoding]::UTF8)
    $body = $reader.ReadToEnd()
    [System.IO.File]::WriteAllText((Join-Path $root "_c26089_run_resp.json"), $body, [System.Text.UTF8Encoding]::new($false))
    Write-Host "BODY_LEN" $body.Length
  }
  exit 2
}
Write-Host "DONE"
