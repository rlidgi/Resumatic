# ── Configuration ─────────────────────────────────────────────────
$RESOURCE_GROUP = "resumerevamp2_group"
$WEB_APP_NAME = "resumerevamp2"
$ZIP_NAME = "deploy.zip"

# Define all patterns to exclude
$EXCLUDE_LIST = @(
    "*node_modules*",
    "*venv*",
    "*.venv*",
    "*.git*",
#    "*dist*",
    "*data_backups*",
    "*.zip",
    "*__pycache__*",
    "*.DS_Store*",
    "*scripts\temp_uploads*",
    "*.env*",
    ".env",".
    env.local"
)


# ── Cleanup ───────────────────────────────────────────────────────
if (Test-Path $ZIP_NAME)
{
    Remove-Item $ZIP_NAME -Force
}

# ── Zipping ───────────────────────────────────────────────────────
Write-Host "Creating clean archive (filtering dist and backups)..." -ForegroundColor Yellow

$stagingDir = "temp_deploy_staging"
if (Test-Path $stagingDir)
{
    Remove-Item $stagingDir -Recurse -Force
}
New-Item -Path $stagingDir -ItemType Directory | Out-Null

# Get all items recursively
$allFiles = Get-ChildItem -Path . -Recurse

foreach ($item in $allFiles)
{
    $path = $item.FullName
    $isExcluded = $false

    # Check if the file path contains any of the excluded patterns
    foreach ($pattern in $EXCLUDE_LIST)
    {
        if ($path -like "*$pattern*")
        {
            $isExcluded = $true
            break
        }
    }

    if (-not $isExcluded)
    {
        # Calculate relative path
        $relativePath = $item.FullName.Substring($PWD.Path.Length + 1)
        $destPath = Join-Path $stagingDir $relativePath

        if ($item.PSIsContainer)
        {
            if (!(Test-Path $destPath))
            {
                New-Item -ItemType Directory -Path $destPath | Out-Null
            }
        }
        else
        {
            $parent = Split-Path $destPath
            if (!(Test-Path $parent))
            {
                New-Item -ItemType Directory -Path $parent | Out-Null
            }
            Copy-Item $item.FullName -Destination $destPath
        }
    }
}

$zipSourcePath = Join-Path $PWD.Path $stagingDir
$zipDestPath = Join-Path $PWD.Path $ZIP_NAME

Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($zipSourcePath, $zipDestPath)
# -----------------------------------------------------------

# Cleanup staging
Remove-Item $stagingDir -Recurse -Force

Write-Host "Archive created: $ZIP_NAME" -ForegroundColor Green

# ── Deploy ────────────────────────────────────────────────────────
Write-Host "Uploading to Azure..." -ForegroundColor Cyan
az webapp deploy --resource-group $RESOURCE_GROUP --name $WEB_APP_NAME --src-path $ZIP_NAME --type zip

if ($LASTEXITCODE -eq 0)
{
    Write-Host "Deployment successful!" -ForegroundColor Green
}
else
{
    Write-Host "Deployment failed." -ForegroundColor Red
}

# ── Cleanup ───────────────────────────────────────────────────────
Remove-Item $ZIP_NAME -Force