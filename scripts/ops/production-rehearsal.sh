#!/usr/bin/env bash
# =============================================================================
# AgentNet 生产演练脚本（production rehearsal）
#
# 一次可复用、幂等、可重入的生产演练：compose 起栈 → 迁移 → 种子 → 冒烟 → 拆栈。
#
# 用法（仓库根目录或任意目录执行）:
#   bash scripts/ops/production-rehearsal.sh                     # 完整演练（结束自动拆栈）
#   bash scripts/ops/production-rehearsal.sh --dry-run           # 只校验，不起容器、不写产物
#   bash scripts/ops/production-rehearsal.sh --teardown          # 只拆除演练栈（down -v）
#   bash scripts/ops/production-rehearsal.sh --resume            # 按状态文件跳过已完成步骤
#   bash scripts/ops/production-rehearsal.sh --with-mcp          # 起mcp profile并做MCP端到端冒烟
#   bash scripts/ops/production-rehearsal.sh --with-observability # 加占回环9090/9093/3000
#   bash scripts/ops/production-rehearsal.sh --with-baseline     # 拆栈后在宿主跑回归基线
#   bash scripts/ops/production-rehearsal.sh --reset-env / --reset-certs
#   bash scripts/ops/production-rehearsal.sh --no-teardown       # 演练后保留栈以便排查
#   bash scripts/ops/production-rehearsal.sh --full              # 实验模式（额外提示，不跑特权用例）
#
# 安全约束：
#   * 凭据一律运行时用 openssl rand 生成（或从环境读取），脚本与模板不含可用凭据字面量。
#   * 演练栈只绑 80/443（observability 仅绑 127.0.0.1:9090/9093/3000），
#     绝不占用 dev compose 的 5432/6379/8000/5173，也绝不停 agentnet-test-pg/-redis。
#   * 演练库为一次性库：拆栈时 down -v 一并销毁，杜绝残留污染重入断言。
# =============================================================================
set -euo pipefail

# -----------------------------------------------------------------------------
# 常量
# -----------------------------------------------------------------------------
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"   # 仓库脚本普遍以仓库根为工作目录（check-compile/run-tests 依赖相对路径）
COMPOSE_FILE="$REPO_ROOT/infra/docker-compose.prod.yml"
ENV_TEMPLATE="$REPO_ROOT/infra/.env.production.example"
ENV_FILE="$REPO_ROOT/infra/.env.production"
STATE_DIR="$REPO_ROOT/.rehearsal"
STATE_FILE="$STATE_DIR/state"
CERT_DIR="$STATE_DIR/ssl"
CERT_DOMAIN="andrewhyc.top"           # 与 infra/nginx/agentnet.conf 的 server_name 一致
CERT_LIVE_DIR="$CERT_DIR/live/$CERT_DOMAIN"
PROJECT_NAME="agentnet-rehearsal"     # 独立 compose project，与 dev 栈完全隔离
# 演练栈对外端口（nginx）；observability 附加端口（仅回环）
PROD_PORTS=(80 443)
OBS_PORTS=(9090 9093 3000)
# dev compose 占用端口——演练绝不可抢占，也不可被演练项目的容器占用
DEV_PORTS=(5432 6379 8000 5173)
# 协议冒烟的显式测试文件（容器内 /app/tests 下），覆盖 -k 关键字：
#   public_keys      -> tests/test_agent_public_keys.py
#   egress_policy    -> tests/test_egress_policy_point.py
#   encrypted_payload-> tests/test_e2ee_noninteractive.py, tests/test_envelope_e2ee_schema.py
#   relay_forwarder  -> 仓库中尚无匹配文件（4 个关键字覆盖 3 个，见交付报告）
PROTOCOL_SMOKE_TESTS=(
  tests/test_agent_public_keys.py
  tests/test_egress_policy_point.py
  tests/test_e2ee_noninteractive.py
  tests/test_envelope_e2ee_schema.py
)

# 演练用 API 端点根（自签证书 + curl -k；80 端口被 nginx 重定向到 HTTPS，见 smoke_http 说明）
SMOKE_BASE_URL="https://localhost"

# -----------------------------------------------------------------------------
# 参数
# -----------------------------------------------------------------------------
DRY_RUN=0
TEARDOWN_ONLY=0
RESUME=0
WITH_MCP=0
WITH_OBSERVABILITY=0
WITH_BASELINE=0
FULL=0
RESET_ENV=0
RESET_CERTS=0
NO_TEARDOWN=0

usage() {
  cat >&2 <<'EOF'
usage: bash scripts/ops/production-rehearsal.sh [flags]
  (default)       完整演练：起栈 → 迁移 → 种子 → 冒烟 → 拆栈
  --dry-run       只校验（env/证书/compose 配置、端口），不起容器、不写产物
  --teardown      只拆除演练栈（down -v，含一次性演练库）
  --resume        按状态文件跳过已完成步骤（env/证书存在即保留，容器存在即复用）
  --with-mcp      起 mcp profile 并做 MCP 端到端冒烟（PUBLIC 链路）
  --with-observability  附加 observability profile（回环 9090/9093/3000）
  --with-baseline 拆栈后在宿主跑 scripts/ci/run-tests.sh 回归基线
  --reset-env     强制重新生成 infra/.env.production
  --reset-certs   强制重新生成自签证书
  --no-teardown   演练后保留栈以便排查（手动拆除用 --teardown）
  --full          实验模式：打印 authenticated.spec.ts 的另行搭建提示（仍不纳入演练）
EOF
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --teardown) TEARDOWN_ONLY=1 ;;
    --resume) RESUME=1 ;;
    --with-mcp) WITH_MCP=1 ;;
    --with-observability) WITH_OBSERVABILITY=1 ;;
    --with-baseline) WITH_BASELINE=1 ;;
    --full) FULL=1 ;;
    --reset-env) RESET_ENV=1 ;;
    --reset-certs) RESET_CERTS=1 ;;
    --no-teardown) NO_TEARDOWN=1 ;;
    -h|--help) usage ;;
    *) echo "unknown flag: $1" >&2; usage ;;
  esac
  shift
done

# -----------------------------------------------------------------------------
# 日志 / 状态
# -----------------------------------------------------------------------------
CURRENT_STEP="init"
log()  { printf '[rehearsal %s] [%s] %s\n' "$(date +%H:%M:%S)" "$CURRENT_STEP" "$*"; }
warn() { printf '[rehearsal %s] [%s] WARNING: %s\n' "$(date +%H:%M:%S)" "$CURRENT_STEP" "$*" >&2; }
die()  { printf '[rehearsal %s] [%s] FATAL: %s\n' "$(date +%H:%M:%S)" "$CURRENT_STEP" "$*" >&2; exit 1; }
trap 'echo "[rehearsal] ERROR at line $LINENO of step $CURRENT_STEP (see messages above)" >&2' ERR

step() { CURRENT_STEP="$1"; log "== $1 =="; }

mkdir -p "$STATE_DIR"
chmod 700 "$STATE_DIR" 2>/dev/null || true

mark_done() { printf '%s=done\n' "$1" >> "$STATE_FILE"; }
is_done()   { [[ -f "$STATE_FILE" ]] && grep -q "^$1=done$" "$STATE_FILE"; }

# -----------------------------------------------------------------------------
# 工具函数
# -----------------------------------------------------------------------------

# Windows(mingw/cygwin) 下把 POSIX 路径转成 docker 挂载可用的混合路径（E:/...）
docker_path() {
  local p="$1"
  if command -v cygpath >/dev/null 2>&1; then cygpath -m "$p"; else printf '%s' "$p"; fi
}

# 端口是否被监听（netstat 输出兼容 Windows/cygwin 与 Linux）
port_listening() {
  local port="$1"
  netstat -an 2>/dev/null | grep -E "[:.]${port}[^0-9]" | grep -iq listen
}

# 演练项目的容器是否占用了某端口
project_owns_port() {
  local port="$1"
  docker ps --filter "label=com.docker.compose.project=$PROJECT_NAME" \
             --format '{{.Ports}}' 2>/dev/null | grep -q ":${port}->"
}

# 演练栈是否在运行
stack_running() {
  [[ -n "$(docker ps --filter "label=com.docker.compose.project=$PROJECT_NAME" -q 2>/dev/null)" ]]
}

# compose 调用（独立 project；env 文件存在时才传 --env-file，使 --teardown 在 env 缺失时仍可用）
compose_base() {
  local -a args=(-p "$PROJECT_NAME" -f "$COMPOSE_FILE")
  if [[ -f "$ENV_FILE" ]]; then args+=(--env-file "$ENV_FILE"); fi
  (( WITH_OBSERVABILITY )) && args+=(--profile observability)
  (( WITH_MCP )) && args+=(--profile mcp)
  docker compose "${args[@]}" "$@"
}

gen_secret() { openssl rand -hex 24; }   # URL 安全，可直接拼入 DATABASE_URL

# =============================================================================
# 步骤 0：环境自检
# =============================================================================
step "preflight"
command -v docker >/dev/null 2>&1 || die "docker not found"
command -v openssl >/dev/null 2>&1 || die "openssl not found"
command -v curl >/dev/null 2>&1 || die "curl not found"
docker compose version >/dev/null 2>&1 || die "docker compose plugin not found"
[[ -f "$COMPOSE_FILE" ]] || die "missing $COMPOSE_FILE"
[[ -f "$ENV_TEMPLATE" ]] || die "missing $ENV_TEMPLATE"

# =============================================================================
# 步骤 1：门禁（check-compose / openapi / compile）
# =============================================================================
step_gate() {
  step "gate"
  bash "$REPO_ROOT/scripts/ci/check-compose.sh"
  python "$REPO_ROOT/scripts/export_openapi.py" --check
  bash "$REPO_ROOT/scripts/ci/check-compile.sh"
  log "门禁通过（dev+prod compose config、OpenAPI 契约、编译）"
}

# =============================================================================
# 步骤 2：生成 infra/.env.production（openssl rand，缺失即空串回退必败）
# =============================================================================
step_env() {
  step "env"
  if [[ -f "$ENV_FILE" ]] && (( ! RESET_ENV )); then
    log "infra/.env.production 已存在，保留（--reset-env 可重新生成）"
  else
    rm -f "$ENV_FILE"
    local pg_pwd redis_pwd grafana_pwd
    pg_pwd=$(gen_secret)
    redis_pwd=$(gen_secret)
    grafana_pwd=$(gen_secret)
    # 从模板复制，只替换 CHANGE_ME 凭据位；其余值为模板内已记录的非敏感默认值
    sed \
      -e "s|CHANGE_ME_POSTGRES_PASSWORD|${pg_pwd}|g" \
      -e "s|CHANGE_ME_REDIS_PASSWORD|${redis_pwd}|g" \
      -e "s|CHANGE_ME_GRAFANA_PASSWORD|${grafana_pwd}|g" \
      "$ENV_TEMPLATE" > "$ENV_FILE"
    chmod 600 "$ENV_FILE" 2>/dev/null || true
    # 由生成的凭据重算派生 URL，避免与凭据漂移（POSTGRES_USER/DB 取自模板替换后的值）
    local pg_user pg_db
    pg_user=$(grep -E '^POSTGRES_USER=' "$ENV_FILE" | head -1 | cut -d= -f2)
    pg_db=$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | head -1 | cut -d= -f2)
    [[ -n "$pg_user" && -n "$pg_db" ]] || die "模板缺少 POSTGRES_USER/POSTGRES_DB"
    sed -i \
      -e "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+asyncpg://${pg_user}:${pg_pwd}@postgres:5432/${pg_db}|" \
      -e "s|^REDIS_URL=.*|REDIS_URL=redis://:${redis_pwd}@redis:6379/0|" \
      "$ENV_FILE"
    # 注入证书目录（compose 挂载 ${SSL_CERT_DIR}:/etc/ssl/agentnet:ro）
    printf 'SSL_CERT_DIR=%s\n' "$(docker_path "$CERT_DIR")" >> "$ENV_FILE"
    log "已生成 infra/.env.production（3 个凭据 openssl rand 落位，其余沿用模板默认值）"
  fi

  # 校验：每个 KEY= 行必须非空且不含 CHANGE_ME（空串回退会让 postgres 初始化失败）
  local bad=0
  while IFS= read -r line; do
    [[ "$line" =~ ^[A-Z_]+=$ ]] && { warn "空值变量: ${line%%=*}"; bad=1; }
    [[ "$line" == *CHANGE_ME* ]] && { warn "未替换的 CHANGE_ME: $line"; bad=1; }
  done < <(grep -E '^[A-Z_]+=' "$ENV_FILE")
  (( bad == 0 )) || die "env 校验失败（变量缺失/空串回退）"

  # 用生成的 env 实跑一次 compose config，立刻暴露插值/挂载问题
  docker compose --env-file "$ENV_FILE" -p "$PROJECT_NAME" -f "$COMPOSE_FILE" config -q
  log "env 与 compose 插值校验通过"
}

# =============================================================================
# 步骤 3：自签证书（按 nginx 期望布局：live/<domain>/{fullchain,privkey}.pem）
# =============================================================================
validate_cert_layout() {
  [[ -f "$CERT_LIVE_DIR/fullchain.pem" ]] || { warn "missing $CERT_LIVE_DIR/fullchain.pem"; return 1; }
  [[ -f "$CERT_LIVE_DIR/privkey.pem" ]]   || { warn "missing $CERT_LIVE_DIR/privkey.pem"; return 1; }
  openssl x509 -noout -in "$CERT_LIVE_DIR/fullchain.pem" 2>/dev/null || { warn "fullchain.pem 不是合法证书"; return 1; }
  openssl rsa  -noout -in "$CERT_LIVE_DIR/privkey.pem"   2>/dev/null || { warn "privkey.pem 不是合法私钥"; return 1; }
  openssl x509 -checkend 86400 -noout -in "$CERT_LIVE_DIR/fullchain.pem" >/dev/null 2>&1 \
    || { warn "证书将在 24 小时内过期"; return 1; }
  local san
  san=$(openssl x509 -in "$CERT_LIVE_DIR/fullchain.pem" -noout -ext subjectAltName 2>/dev/null || true)
  [[ "$san" == *"$CERT_DOMAIN"* ]] || { warn "证书 SAN 未覆盖 $CERT_DOMAIN"; return 1; }
  return 0
}

step_certs() {
  step "certs"
  if [[ -f "$CERT_LIVE_DIR/fullchain.pem" ]] && (( ! RESET_CERTS )); then
    log "证书已存在，跳过生成（--reset-certs 可重新生成）"
    validate_cert_layout || die "已存在的证书布局非法"
    return 0
  fi
  mkdir -p "$CERT_LIVE_DIR"
  # git-bash/MSYS 会把 "-subj /CN=..." 误转成 Windows 路径；用 MSYS_NO_PATHCONV=1
  # 关闭参数转换，输出文件改用混合路径（E:/...），两种平台通用。
  MSYS_NO_PATHCONV=1 openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
    -keyout "$(docker_path "$CERT_LIVE_DIR/privkey.pem")" \
    -out "$(docker_path "$CERT_LIVE_DIR/fullchain.pem")" \
    -subj "/CN=$CERT_DOMAIN/O=AgentNet Rehearsal (self-signed)" \
    -addext "subjectAltName=DNS:$CERT_DOMAIN,DNS:localhost,IP:127.0.0.1" >/dev/null 2>&1
  chmod 600 "$CERT_LIVE_DIR/privkey.pem" 2>/dev/null || true
  validate_cert_layout || die "自签证书生成失败"
  log "自签证书已落位 $CERT_LIVE_DIR（SAN: $CERT_DOMAIN, localhost, 127.0.0.1）"
}

# =============================================================================
# 端口冲突保护（mode=check 时冲突即拒绝；mode=report 时只报告，供 --dry-run）
# =============================================================================
guard_ports() {
  local mode="${1:-check}"
  step "ports"
  # 静态保护：prod compose 自身不得发布 dev 端口
  if grep -E '^[[:space:]]*- "?(5432|6379|8000|5173):' "$COMPOSE_FILE" >/dev/null; then
    die "$COMPOSE_FILE 发布了 dev compose 端口（5432/6379/8000/5173），拒绝演练"
  fi
  # 运行时保护：演练项目的容器绝不得占用 dev 四端口（显式告警拒绝）
  local p
  for p in "${DEV_PORTS[@]}"; do
    if project_owns_port "$p"; then
      die "演练项目 ($PROJECT_NAME) 的容器占用了 dev compose 端口 $p——为保护在跑的 dev 栈（含 agentnet-test-pg/-redis），拒绝继续"
    fi
  done
  # 演练需要 80/443（--with-observability 另加回环 9090/9093/3000）
  local -a need=("${PROD_PORTS[@]}")
  (( WITH_OBSERVABILITY )) && need+=("${OBS_PORTS[@]}")
  for p in "${need[@]}"; do
    if port_listening "$p"; then
      if [[ "$mode" == "report" ]]; then
        warn "端口 $p 被占用（dry-run 仅报告；实跑将被拒绝）"
      elif project_owns_port "$p"; then
        log "端口 $p 已由演练项目自身占用（--resume 复用栈）"
      else
        die "端口 $p 被非演练进程占用——拒绝抢端口；dev 栈使用 5432/6379/8000/5173，与演练互不冲突，请释放 80/443 后重试"
      fi
    fi
  done
  log "端口检查通过：80/443 可用；dev 栈四端口（5432/6379/8000/5173）不受影响"
}

# =============================================================================
# 步骤 4：拉起演练栈
# =============================================================================
step_up() {
  step "up"
  if stack_running; then
    log "演练栈已在运行，复用（幂等迁移将重跑）"
    return 0
  fi
  mkdir -p "$REPO_ROOT/infra/certbot/www"
  compose_base up -d --wait
  # --wait 只保证容器 started/healthy；再对 API 做 readiness 轮询
  local i
  for i in $(seq 1 60); do
    if curl -fsSk "$SMOKE_BASE_URL/healthz" >/dev/null 2>&1; then
      log "演练栈已就绪（nginx + api + web + postgres + redis）"
      return 0
    fi
    sleep 2
  done
  die "演练栈拉起后 120s 内 /healthz 无响应——检查: docker compose -p $PROJECT_NAME logs"
}

# =============================================================================
# 步骤 5：迁移（幂等；alembic 由 compose env 注入 DATABASE_URL，不再 -e 传值）
# =============================================================================
step_migrate() {
  step "migrate"
  log "alembic upgrade head（幂等，可重入）"
  compose_base exec -T api alembic upgrade head
  local current
  current="$(compose_base exec -T api alembic current | tail -1 | tr -d ' ')"
  [[ "$current" == *"(head)"* ]] || die "迁移未停在 head：alembic current => '$current'"
  log "迁移停留在 head: $current"
  if [[ "$current" != 0031* && "$current" != 0032* ]]; then
    warn "head 已超越 0031/0032（当前 $current）——确认是否为新交付迁移，必要时同步更新本脚本预期"
  fi
}

# =============================================================================
# 步骤 6：种子（复用 scripts/seed_e2e_user.py，exec 进 api 容器跑，幂等）
# =============================================================================
step_seed() {
  step "seed"
  # 脚本本体在宿主；容器内 WORKDIR /app 已在 sys.path（python - 的 sys.path[0] 为 cwd），
  # 用 stdin 灌入即可，DATABASE_URL 由 compose env 注入。
  # 种子仅给冒烟用；MCP 冒烟与协议冒烟共用同一库时不做跨步骤状态依赖断言。
  local seed_out api_key username
  seed_out="$(compose_base exec -T api python - < "$REPO_ROOT/scripts/seed_e2e_user.py" 2>&1)"
  api_key="$(printf '%s\n' "$seed_out" | grep -oE 'E2E_DASHBOARD_API_KEY=ak_[A-Za-z0-9_-]+' | head -1 | cut -d= -f2)"
  username="$(printf '%s\n' "$seed_out" | grep -oE 'E2E_DASHBOARD_USERNAME=[A-Za-z0-9_-]+' | head -1 | cut -d= -f2)"
  [[ -n "$api_key" ]] || die "种子未返回 API key；seed 输出:\n$seed_out"
  printf '%s\n' "$username" > "$STATE_DIR/seed_username"
  printf '%s\n' "$api_key"  > "$STATE_DIR/seed_api_key"
  chmod 600 "$STATE_DIR/seed_api_key" 2>/dev/null || true
  log "种子完成（用户 $username，临时 key 已记入 $STATE_DIR/seed_api_key，仅本机演练用）"
}

# =============================================================================
# 步骤 7a：HTTP 冒烟
# -----------------------------------------------------------------------------
# 说明（与任务书验收命令的差异）：infra/nginx/agentnet.conf 的 80 端口把所有非
# ACME 请求 301 重定向到 HTTPS，且 FastAPI 暴露的健康端点是 /healthz、/readyz
# （不存在 /health）。因此脚本用 "curl -fsSk https://localhost/healthz" 做真校验；
# "curl -fsS http://localhost/health" 只能证明 nginx 80 在听（301），无 API 语义。
# /v1/agents 需要鉴权（未认证 401），故冒烟携带种子 key。
# =============================================================================
smoke_http() {
  step "smoke-http"
  local api_key
  api_key="$(cat "$STATE_DIR/seed_api_key")"

  curl -fsSk "$SMOKE_BASE_URL/healthz" | grep -q '"status"' || die "/healthz 未返回状态"
  log "GET /healthz OK"

  local ready
  ready="$(curl -fsSk "$SMOKE_BASE_URL/readyz")"
  printf '%s' "$ready" | grep -q '"status":"healthy"' || die "/readyz 非健康: $ready"
  log "GET /readyz OK: $ready"

  local agents
  agents="$(curl -fsSk -H "Authorization: Bearer $api_key" "$SMOKE_BASE_URL/v1/agents")"
  printf '%s' "$agents" | grep -q 'agents' || die "/v1/agents 未返回集合: $agents"
  log "GET /v1/agents OK（带种子 Bearer key）"
}

# =============================================================================
# 步骤 7b：协议冒烟（容器内显式测试文件，参数化数据访问）
# =============================================================================
smoke_protocol() {
  step "smoke-protocol"
  # 容器内 WORKDIR /app、tests 已 COPY 进镜像，路径为 tests/（而非宿主 apps/api/tests/）。
  # 显式文件避免整目录收集与无关模块的模块级 DB 连接。
  compose_base exec -T api python -m pytest -q -p no:cacheprovider "${PROTOCOL_SMOKE_TESTS[@]}"
  log "协议冒烟通过（4 个显式测试文件；relay_forwarder 尚无交付文件，4 个关键字覆盖 3 个）"
}

# =============================================================================
# 步骤 7c：前端 E2E（smoke.spec.ts，纯前端，TLS 自签友好）
# =============================================================================
smoke_web() {
  step "smoke-web"
  if ! (cd "$REPO_ROOT/apps/web" && npx playwright --version >/dev/null 2>&1); then
    die "apps/web 下未找到 playwright；先 'cd apps/web && npm install'"
  fi
  # 生成演练专用 config：忽略自签证书错误，并允许 BASE_URL 覆盖。
  # http://localhost 会被 nginx 301 到 https://localhost，playwright 跟随重定向后
  # 由 ignoreHTTPSErrors 放行，故 BASE_URL=http://localhost 与任务书一致可用。
  cat > "$REPO_ROOT/apps/web/playwright.rehearsal.config.ts" <<'EOF'
// AUTO-GENERATED by scripts/ops/production-rehearsal.sh — 演练专用，勿提交。
import { defineConfig, devices } from '@playwright/test';
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  reporter: 'list',
  use: {
    baseURL: process.env.BASE_URL || 'https://localhost',
    ignoreHTTPSErrors: true, // 演练使用自签证书
    locale: 'en-US',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
EOF
  local base_url="${BASE_URL:-http://localhost}"
  (cd "$REPO_ROOT/apps/web" && BASE_URL="$base_url" \
     npx playwright test --config playwright.rehearsal.config.ts e2e/smoke.spec.ts)
  log "前端 E2E smoke 通过（BASE_URL=$base_url）"

  if (( FULL )); then
    cat >&2 <<'EOF'
[rehearsal] --full 实验模式提示：authenticated.spec.ts 未纳入演练。
  该用例要求 localhost:8000 直连 api 容器 + 播种凭据（E2E_DASHBOARD_*），
  与 prod 栈架构（api 不暴露宿主端口，仅经 nginx）不符，需另行搭建：
    docker compose -p agentnet-rehearsal --env-file infra/.env.production \
      -f infra/docker-compose.prod.yml exec -T api python - < scripts/seed_e2e_user.py
  导出 E2E_DASHBOARD_USERNAME / E2E_DASHBOARD_API_KEY 后单跑该用例。
EOF
  else
    log "authenticated.spec.ts 不纳入默认演练（与 prod 栈架构不符；--full 查看提示）"
  fi
}

# =============================================================================
# 步骤 7d：MCP 端到端（--with-mcp）
# =============================================================================
smoke_mcp() {
  step "smoke-mcp"
  # 前置检查：compose 必须真的定义了 mcp profile 的服务
  # （直接用原生 docker compose，不经过 compose_base——后者已按 --with-mcp 附加了 profile）
  local with without
  with="$(docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" --profile mcp config --services 2>/dev/null | sort)"
  without="$(docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" config --services 2>/dev/null | sort)"
  if [[ "$with" == "$without" ]]; then
    cat >&2 <<'EOF'
[rehearsal] FATAL: --with-mcp 需要 compose 中存在 mcp profile 的服务（adapters/mcp
  镜像含 packages/python-sdk + stub server），但 infra/docker-compose.prod.yml 当前
  未定义任何 mcp profile 服务（adapters/mcp 仅有 README.md/TODO.md）。请先交付 MCP
  adapter 服务定义，再重跑 --with-mcp。
EOF
    die "--with-mcp 前置失败：compose 缺少 mcp profile"
  fi
  # PUBLIC 链路断言：create_task → task.request → tools/call → task.result completed。
  # 在 mcp adapter 服务交付前，本段保持显式失败而非空跑（不伪造通过）。
  die "MCP 端到端冒烟（create_task→task.request→tools/call→task.result completed）尚未实现：等待 adapters/mcp 服务交付"
}

# =============================================================================
# 步骤 8：拆除（down -v 销毁一次性演练库，验证端口释放）
# =============================================================================
step_teardown() {
  step "teardown"
  if stack_running; then
    compose_base down -v
    log "docker compose down -v 完成（agentnet_postgres_data 等演练卷已销毁）"
  else
    log "演练栈未运行，无需拆除（幂等）"
  fi
  local p still=()
  for p in "${PROD_PORTS[@]}"; do
    if port_listening "$p"; then still+=("$p"); fi
  done
  if (( ${#still[@]} > 0 )); then
    die "拆栈后宿主端口 ${still[*]} 仍未释放——请检查占用进程"
  fi
  rm -f "$STATE_DIR/seed_api_key" "$STATE_DIR/seed_username"
  mark_done teardown
  log "宿主 80/443 已释放；dev 栈与 agentnet-test-pg/-redis 未受影响"
}

# =============================================================================
# 步骤 9：回归基线（拆栈后宿主执行，文件级记账 + 单点重试）
# =============================================================================
step_baseline() {
  step "baseline"
  local p
  for p in 5432 6379; do
    port_listening "$p" || die "宿主 $p 未监听——agentnet-test-pg/-redis 未运行，run-tests.sh 无法跑（本脚本不会代你启动它们，也不停它们）"
  done
  if stack_running; then
    die "基线须在拆栈后执行（演练栈仍在运行；--no-teardown 下请先 --teardown）"
  fi
  log "bash scripts/ci/run-tests.sh（宿主直连 agentnet-test-pg/-redis）"
  local out
  if out="$(bash "$REPO_ROOT/scripts/ci/run-tests.sh" 2>&1)"; then
    printf '%s\n' "$out" | tail -5
    log "回归基线通过（按文件级集合记账）"
    return 0
  fi
  printf '%s\n' "$out" | tail -20 >&2
  # 文件级记账：提取失败文件，整文件单跑重试一次（已知单点 flaky 项同样适用）
  local -a files=()
  while IFS= read -r node; do
    files+=("${node%%::*}")
  done < <(printf '%s\n' "$out" | grep -E '^(FAILED|ERROR)' | awk '{print $2}')
  if (( ${#files[@]} == 0 )); then
    die "基线失败但无法定位失败文件（见上方输出）"
  fi
  local -a retry_files=() still=()
  while IFS= read -r f; do retry_files+=("$f"); done \
    < <(printf '%s\n' "${files[@]}" | sort -u)
  warn "失败文件（去重）: ${retry_files[*]}——整文件单跑重试一次"
  local f
  for f in "${retry_files[@]}"; do
    if python -m pytest -q "$f" >/dev/null 2>&1; then
      warn "重试通过（单跑 1 次）：$f —— 记为待决策项（一次通过无法证实/证伪 flaky）"
    else
      still+=("$f")
    fi
  done
  if (( ${#still[@]} > 0 )); then
    die "基线仍有文件失败: ${still[*]}"
  fi
  warn "全部失败文件单跑重试通过——按文件级记账规则记为待决策项（flaky 未证实）"
}

# =============================================================================
# 主流程
# =============================================================================
if (( TEARDOWN_ONLY )); then
  log "--teardown：跳过其余步骤，直接拆除演练栈"
  step_teardown
  exit 0
fi

step_gate

if (( DRY_RUN )); then
  log "--dry-run：只做校验，不起容器、不写 env/证书、不记状态"
  if [[ -f "$ENV_FILE" ]]; then
    docker compose --env-file "$ENV_FILE" -p "$PROJECT_NAME" -f "$COMPOSE_FILE" config -q && log "env 有效"
  else
    log "env 未生成（实跑时由步骤 2 生成，3 个凭据 openssl rand 落位）"
  fi
  if [[ -f "$CERT_LIVE_DIR/fullchain.pem" ]]; then
    validate_cert_layout && log "证书布局有效"
  else
    log "证书未生成（实跑时由步骤 3 按布局生成）"
  fi
  guard_ports report || true
  log "--dry-run 结束"
  exit 0
fi
mark_done gate

step_env
mark_done env
step_certs
mark_done certs
guard_ports check
step_up
mark_done up
step_migrate
mark_done migrate
step_seed
mark_done seed

smoke_http
mark_done smoke_http
if (( RESUME )) && is_done smoke_protocol; then
  log "--resume：协议冒烟已完成，跳过"
else
  smoke_protocol
  mark_done smoke_protocol
fi
if (( RESUME )) && is_done smoke_web; then
  log "--resume：前端 E2E 已完成，跳过"
else
  smoke_web
  mark_done smoke_web
fi
if (( WITH_MCP )); then
  if (( RESUME )) && is_done smoke_mcp; then
    log "--resume：MCP 冒烟已完成，跳过"
  else
    smoke_mcp
    mark_done smoke_mcp
  fi
fi

if (( NO_TEARDOWN )); then
  log "--no-teardown：演练栈保留在运行态（手动拆除: bash scripts/ops/production-rehearsal.sh --teardown）"
  exit 0
fi
step_teardown

if (( WITH_BASELINE )); then
  step_baseline
  mark_done baseline
else
  log "回归基线未启用（拆栈后宿主执行: bash scripts/ci/run-tests.sh，或加 --with-baseline）"
fi

log "演练完成"
