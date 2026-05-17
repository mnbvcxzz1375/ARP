$ErrorActionPreference = "Stop"

docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml config
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose config check failed with exit code $LASTEXITCODE"
}
