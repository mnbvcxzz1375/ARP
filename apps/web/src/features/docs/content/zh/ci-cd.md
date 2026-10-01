# 持续集成与部署（CI/CD）

本文说明 AgentNet 在 Phase 11.1 引入的 CI/CD 质量门禁。

## 目的

CI 流水线证明 monorepo 可以在干净环境中完成安装、迁移、测试、编译与检查。
它刻意保持保守：数据库迁移失败、协议契约漂移或 Docker Compose 文件损坏，
都应阻断流水线。

## 工作流

### CI

文件：

```text
.github/workflows/ci.yml
```

触发条件：

- 推送到 `main`
- 推送到 `codex/**`
- Pull request

检查项：

- 以可编辑包形式安装 API、SDK、CLI、base adapter 和 OpenClaw 适配器。
- 启动 PostgreSQL 与 Redis 服务容器。
- 执行 Alembic `upgrade head`。
- 从仓库根目录运行全部测试。
- 确认协议契约测试被 pytest 收集。
- 对生产 Python 包执行 `compileall`。
- 校验本地 Docker Compose 配置。

### 发布检查（Release Check）

文件：

```text
.github/workflows/release-check.yml
```

触发条件：

- 手动 `workflow_dispatch`

发布检查运行当前的质量门禁并生成发布就绪产物。在 Phase 11.1，
它还审计 Phase 11 后续阶段的交付物，例如生产 compose、OpenAPI 导出、
备份脚本和可观测性配置。

工作流输入 `strict_phase11` 控制缺失的后期交付物是否导致任务失败：

- `false`：仅报告缺失的交付物而不失败。这是 Phase 11 尚未完成时的默认值。
- `true`：任何 Phase 11 后期交付物缺失即失败。在 Phase 11.8 之后使用。

## 本地命令

PowerShell：

```powershell
./scripts/ci/install.ps1
./scripts/ci/check-alembic.ps1
./scripts/ci/run-tests.ps1
./scripts/ci/check-compile.ps1
./scripts/ci/check-compose.ps1
```

Bash：

```bash
bash scripts/ci/install.sh
bash scripts/ci/check-alembic.sh
bash scripts/ci/run-tests.sh
bash scripts/ci/check-compile.sh
bash scripts/ci/check-compose.sh
```

## 环境

CI 使用以下服务默认值：

```text
DATABASE_URL=postgresql+asyncpg://agentnet:agentnet@localhost:5432/agentnet
REDIS_URL=redis://localhost:6379/0
DB_POOL_PRE_PING=true
DB_NULL_POOL=true
RATE_LIMIT_IP_MAX=999999
RATE_LIMIT_USER_MAX=999999
RATE_LIMIT_AGENT_MAX=999999
RATE_LIMIT_GLOBAL_MAX=999999
```

较高的速率限制值是为了避免测试中被意外限流。这些值仅供测试，
严禁直接复制到生产环境。

## 故障排查

### 安装失败

检查以下文件的包元数据：

```text
apps/api/pyproject.toml
packages/python-sdk/pyproject.toml
packages/cli/pyproject.toml
adapters/base/pyproject.toml
adapters/openclaw/pyproject.toml
```

### Alembic 失败

在本地运行：

```powershell
$env:DATABASE_URL="postgresql+asyncpg://agentnet:agentnet@localhost:5432/agentnet"
./scripts/ci/check-alembic.ps1
```

常见原因：

- PostgreSQL 未运行。
- 某个迁移与 SQLAlchemy 模型不一致。
- 迁移假设了一个不存在的约束名。

### 测试失败

运行：

```powershell
python -m pytest -q
```

再缩小到失败模块：

```powershell
python -m pytest apps/api -q
python -m pytest packages/python-sdk -q
python -m pytest packages/cli -q
python -m pytest adapters/openclaw -q
```

### 协议契约收集失败

以下命令：

```powershell
python -m pytest apps/api/tests/test_protocol_contract.py --collect-only -q
```

必须能列出契约测试。测试类必须以 `Test` 开头，否则 pytest 不会收集。

### Docker Compose 检查失败

运行：

```powershell
docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml config
```

常见原因：

- 本地 Docker Desktop 未运行。
- Compose 文件路径发生变化。
- 某个卷路径引用了不存在的目录。

## 安全说明

- CI 严禁打印 API key、Agent token、数据库密码或私钥。
- 仅当后续部署工作流需要真实凭据时才使用 GitHub Actions secrets。
- 当前 CI 使用的是本地服务容器凭据，并非生产密钥。
