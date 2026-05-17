$ErrorActionPreference = "Stop"

Push-Location apps/api
try {
    alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw "alembic upgrade head failed with exit code $LASTEXITCODE"
    }
    alembic current
    if ($LASTEXITCODE -ne 0) {
        throw "alembic current failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
