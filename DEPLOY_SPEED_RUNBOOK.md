# Deploy Speed Runbook (Azure App Service)

Use this after deploy package-size optimizations if deployment is still slow.

## What We Already Optimized

- Reduced VS Code ZipDeploy payload via `.vscode/settings.json` `appService.zipIgnorePattern`.
- Excluded local environments, temp data, logs, and frontend dev workspace folders.
- Excluded Node frontend project files not needed by runtime Flask app (serves prebuilt `static/react`).

## Fast Triage Checklist

1. In Azure Portal, open App Service -> Deployment Center -> Logs.
2. Identify where time is spent:
	- Upload/extract zip
	- Oryx detect/build
	- `pip install -r requirements.txt`
	- Startup / warmup
3. If Oryx is invoking Node steps, keep frontend files excluded from deploy package.
4. If startup is slow, inspect Log stream for `startup.sh` timing and Playwright install logs.

## App Settings to Verify

In App Service -> Configuration -> Application settings:

- `SCM_DO_BUILD_DURING_DEPLOYMENT=true`
  - Keep this true while runtime dependencies are installed by Oryx.

- `WEBSITE_HEALTHCHECK_MAXPINGFAILURES=10`
  - Optional: reduces false unhealthy cycles during cold starts.

## If Deploy Is Still >10 Minutes

1. Capture a single deployment log and note exact durations for each phase.
2. If `pip install` dominates:
	- Split non-critical heavy dependencies into optional runtime install path.
	- Keep only strict production dependencies in `requirements.txt`.
3. If startup dominates:
	- Gate optional startup work (e.g., browser/tooling bootstrap) behind env flags.
4. If upload dominates:
	- Expand zip ignores for any newly added large local folders.

## Expected Range After These Changes

- Typical: 4-9 minutes
- Slower runs (network/cache misses): up to ~12 minutes
- If still ~16 minutes consistently, logs are needed to isolate remaining bottleneck.
