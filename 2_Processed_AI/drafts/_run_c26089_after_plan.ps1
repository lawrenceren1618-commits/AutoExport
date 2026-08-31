$ErrorActionPreference = "Stop"
$base = "http://localhost:3000"
$id = "4ed01c57-9446-4dd9-a7fd-488395f6eaed"

$patchObj = @{
  plan_mode    = "manual_lines"
  total_strips = 40000
  lines        = @(
    @{
      size               = "60X102inch"
      color              = "白色"
      qty_strips         = 40000
      qty_cartons        = 1000
      strips_per_pack    = 10
      packs_per_carton   = 4
      strips_per_carton  = 40
      fnsku              = "X004SJV9UF"
      gram_weight        = "90G"
    }
  )
}
$patchJson = $patchObj | ConvertTo-Json -Depth 8 -Compress
$utf8 = New-Object System.Text.UTF8Encoding $false
$patchBytes = $utf8.GetBytes($patchJson)

Write-Host "=== PATCH ==="
$patchResp = Invoke-WebRequest -Uri "$base/api/jobs/$id/patch" -Method POST -ContentType "application/json; charset=utf-8" -Body $patchBytes -UseBasicParsing
Write-Host "STATUS" $patchResp.StatusCode
Write-Host $patchResp.Content

Write-Host "=== RUN after_plan ==="
$runJson = '{"wave":"after_plan"}'
$runBytes = $utf8.GetBytes($runJson)
try {
  $runResp = Invoke-WebRequest -Uri "$base/api/jobs/$id/run" -Method POST -ContentType "application/json; charset=utf-8" -Body $runBytes -UseBasicParsing
  Write-Host "STATUS" $runResp.StatusCode
  Write-Host $runResp.Content
} catch {
  Write-Host "RUN_FAIL"
  Write-Host $_.Exception.Message
  if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
    Write-Host $_.ErrorDetails.Message
  }
  exit 2
}
