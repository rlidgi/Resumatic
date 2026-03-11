
# Deployment Safety Guide

This repo can be deployed to Azure App Service using the VS Code **Azure App Service** extension (ZipDeploy).

## VS Code ZipDeploy packaging (important)

VS Code ZipDeploy uploads a zip file containing your workspace (or a subfolder) to Azure. The contents of that zip are controlled by workspace settings in `.vscode/settings.json`.

Key settings:

- `appService.defaultWebAppToDeploy`: which App Service resource VS Code targets.
- `appService.deploySubpath`: which folder inside the workspace is zipped (often `.`).
- `appService.zipIgnorePattern`: glob patterns excluded from the zip.

### Why we exclude files

Some folders are very large or are local-only artifacts. Including them often causes ZipDeploy to fail (timeouts / upload failures) and can also upload OS-specific binaries that don't work on Linux App Service.

Common exclusions include:

- `.venv/`, `node_modules/`: local dependency folders (Azure/Oryx installs dependencies during build).
- `__pycache__/`, `.pytest_cache/`: dev caches.
- `temp_store/`, `temp_uploads/`, `flask_session/`, `data_backups/`: local/ephemeral data.

### If a deployment ever “needs a file” that was excluded

Symptom: the app deploys but fails at runtime because something expected at runtime wasn't uploaded.

Fast rollback test:

1. Temporarily remove (or empty) `appService.zipIgnorePattern` in `.vscode/settings.json`.
2. Redeploy from VS Code.

If that fixes it, add back ignores one-by-one until you find the specific required path.

## Notes

- `appService.zipIgnorePattern` affects **only** the VS Code ZipDeploy packaging step; it does not delete files from your repo.
- If you switch deployment methods (GitHub Actions, azd, etc.), those methods have their own include/exclude behavior.

