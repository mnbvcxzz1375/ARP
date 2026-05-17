$ErrorActionPreference = "Stop"

python -m compileall `
  adapters/openclaw/agentnet_openclaw `
  packages/python-sdk/agentnet `
  packages/cli/agentnet_cli `
  apps/api/app
if ($LASTEXITCODE -ne 0) {
    throw "compileall failed with exit code $LASTEXITCODE"
}
