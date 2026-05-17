$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE"
    }
}

Invoke-Checked { python -m pip install --upgrade pip }
Invoke-Checked { python -m pip install -e "apps/api[test]" }
Invoke-Checked { python -m pip install -e "packages/python-sdk" }
Invoke-Checked { python -m pip install -e "packages/cli" }
Invoke-Checked { python -m pip install -e "adapters/base" }
Invoke-Checked { python -m pip install -e "adapters/openclaw" }
