# ── Configuration ─────────────────────────────────────────────────
$RESOURCE_GROUP = "resumerevamp2_group"
$WEB_APP_NAME   = "resumerevamp2"
$ZIP_NAME       = "deploy.zip"

# Added "dist" and "data_backups" to the exclude list
$EXCLUDE_PATTERNS = @(
    "*\node_modules*",
    "*\venv*",
    "*\.venv*",
    "*\.git*",
    "*\dist*",
    "*\data_backups*",
    "*.zip",
    "*\__pycache__*",
    "*\.DS_Store*",
    "*\scripts\temp_uploads*"
)

# ── Cleanup ───────────────────────────────────────────────────────
if (Test-Path $ZIP_NAME) { Remove-Item $ZIP_NAME -Force }

# ── Zipping ───────────────────────────────────────────────────────
Write-Host "Creating clean archive (filtering dist and backups)..." -ForegroundColor Yellow

$files = Get-ChildItem -Path . -Recurse -File | Where-Object {
    $path = $_.FullName
    $keep = $true
    foreach ($pattern in $EXCLUDE_PATTERNS) {
        if ($path -like $pattern) {
            $keep = $false
            break
        }
    }
    $keep
}

# Zip the filtered files while maintaining directory structure
$files | Compress-Archive -DestinationPath $ZIP_NAME -Update

Write-Host "Archive created: $ZIP_NAME" -ForegroundColor Green

# ── Deploy ────────────────────────────────────────────────────────
Write-Host "Uploading to Azure..." -ForegroundColor Cyan
az webapp deploy --resource-group $RESOURCE_GROUP --name $WEB_APP_NAME --src-path $ZIP_NAME --type zip

if ($LASTEXITCODE -eq 0) {
    Write-Host "Deployment successful!" -ForegroundColor Green
} else {
    Write-Host "Deployment failed." -ForegroundColor Red
}

# ── Cleanup ───────────────────────────────────────────────────────
Remove-Item $ZIP_NAME -Force