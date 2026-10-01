# AgentNet 控制台「分平台」方案决策文档

日期：2026-09-30（v2，吸收两轮独立评审后修订）
范围：apps/web（单 Vite + React 应用）是否拆分为个人 / 管理员 / 企业三套独立构建单元。
结论先行：**推荐选项 A——维持单应用，深化平台边界**，但「深化」的范围经评审修订后大幅扩展：前端边界强化的同时，**后端 RBAC/企业实体扩展必须与阶段 0 并行启动**，否则 A 对企业管理者 persona 的收益接近零。此外评审发现一组 **P0 现存缺陷**（生产 sourcemap 全量公开、前端零 CI、企业路由 nginx fallback 缺失、/docs 路径冲突、运行时依赖错放 devDependencies），它们不改变「不拆分」的结论，但**在修复前，A 相对 B/C 的隔离论证不成立**，且迁移路线的验收标准当前没有执行载体。

> **本次修订要点（v2）**：原文档的「不拆分」结论不变，理由（共享资产单一真源、共享页面归属、部署同源、MVP 规模、不锁死未来）经复核全部成立；但修正了三处论证缺陷——(1) 原文把「非管理员不下载管理 UI」列为 A 首要收益，却未发现生产 sourcemap 把全部源码（含 admin/enterprise）原样公开，隔离论证在修复前不成立；(2) 原文把 RBAC 排在阶段 3，与理由 4「正确顺序是先补 RBAC」自相矛盾，现改为并行；(3) 原文验收标准（数 chunk 个数）错误，i18n 分包与 B/C 的 effort 被低估。全部修订基于本会话实测复核（见下表「复核方式」列）。

---

## 1. 现状（实测复核）

| 指标 | 数值 | 复核方式 |
|---|---|---|
| 构建产物 | assets=21，totalBytes=4,505,229 | `du -cb dist/assets/*` → `4505229 total` |
| JS chunk 数 | **1 个**（index-BbM2v4LN.js，1,111,704 字节） | `ls dist/assets/*.js \| wc -l` → 1 |
| **生产 sourcemap** | **index-BbM2v4LN.js.map，3,194,879 字节，含全部页面源码与 node_modules 路径，随镜像公开** | `ls -la dist/assets`；vite.config.ts:28 `sourcemap:true`；Dockerfile.prod:13 `COPY --from=builder /app/dist ...` 原样打入；nginx.default.conf:25-28 对 `/assets/` 放 `public, immutable` 且无 .map 拒绝规则 |
| 路由级懒加载 | **0 处** | `grep -rn "React.lazy\|lazy(" src --include="*.tsx" \| grep -v __tests__ \| wc -l` → 0 |
| **bundle 内容构成** | 465 模块：node_modules 319、src-other 70、i18n 34、admin 10、enterprise 11、other 21；sourcesContent 总计 2,145,866 字符，**admin+enterprise 源码仅 157,573 字符（7.3%）**，**markdown 渲染链（react-markdown/remark/micromark/mdast/hast/unist 等）560,922 字符（26%）且仅被 DocsMarkdown.tsx 消费** | 本次 python 解析 dist/assets/index-BbM2v4LN.js.map 并按模块路径分类计数 |
| features→components 共享 import | 147 行 | `grep -rn "from '../../components" src/features --include="*.tsx" \| grep -v __tests__ \| wc -l` → 147 |
| 共享组件引用（Top） | LoadingState 31、ErrorState 29、DataTable 22、StatusBadge 15、Pagination 14、ConfirmDialog 13 | `grep ... \| grep -o "components/[A-Za-z]*" \| sort \| uniq -c` |
| 非测试页面（admin+enterprise） | 21 个 | `find src/features/admin src/features/enterprise -name "*.tsx" \| grep -v __tests__ \| wc -l` → 21 |
| 单元测试 / e2e | 38 个测试文件 / 10 个 e2e spec | `find src -name "*.test.*" \| wc -l`；`ls e2e` |
| i18n locale 文件 | 28（en/zh × 14 namespace）+ 7 个 .mimosa 工具文件（非源码） | `find src/i18n/locales -type f \| sort` |
| **前端 CI** | **不存在**：ci.yml / release-check.yml 全部为 Python 后端步骤（install/alembic/tests/compile/openapi/compose），无任何 apps/web 的 build/vitest/e2e/lint/typecheck；且 ci.yml push 只监听 `main` + `codex/**`，而仓库默认分支是 `master`（`git branch -a` → origin/HEAD -> origin/master）——推送到 master 不触发任何 CI | 通读 .github/workflows/ci.yml 与 release-check.yml 全文；`git branch -a` |
| index.css / tokens.ts | 255 行 / 73 行，tokens 消费者 13 文件 | `grep -c "" src/index.css`；`grep -rln "lib/tokens" src \| wc -l` → 13 |
| 依赖盘点（**修正**） | 原文称「生产依赖 9 个」不准确：dependencies 实为 8 个非字体依赖 + 3 个 @fontsource 像素字体；另有 **react-markdown ^10.1.0 与 remark-gfm ^4.0.1 被生产源码 `src/features/docs/DocsMarkdown.tsx:2-3` import 却错放 devDependencies（package.json:45-46）**——当前可构建仅因 Dockerfile.prod:5 用 `npm ci`（装 dev 依赖），任何 `--production` 剪枝或包拆分即断构建 | `sed -n '15,50p' package.json`；`head -5 src/features/docs/DocsMarkdown.tsx` |
| 仓库底座 | **无根 package.json**（`ls package.json` → No such file）；packages/ 下全为 Python 包；Dockerfile 用 npm ci | `ls` 仓库根；`ls packages` |
| 守卫消费 permissions | 后端 /me 已返回 `permissions: string[]`（useAuth.ts:8 类型声明），但**前端零消费**——src 中 permissions 仅出现在该类型声明，App.tsx:56 守卫仍硬编码 role 字符串 | `grep -rn "permissions" apps/web/src --include="*.tsx" --include="*.ts" \| grep -v __tests__` |

**路由结构**（`src/App.tsx:62-157`，本会话完整读取）：三个路由组 + 一个公共文档子站——公共组 `/`（PublicLayout）、个人组 `/app`（10 条叶子路由）、`/admin` 与 `/enterprise`（均 RequireAdmin→AdminLayout）。`/enterprise` 注册 20 条路由，其中 9 条复用 admin 页面组件（:146-153，注释 "Reuse admin pages for shared resources"），`/admin` 注释自称 "compatibility alias: enterprise routes preferred"。

**平台边界现状（四层，运行时逻辑隔离而非构建隔离）**：路由层（RequireAuth/RequireAdmin，App.tsx:45-60）、导航层（navigation.ts 拆 PERSONAL_NAV/ENTERPRISE_NAV，但 /admin 组渲染的是 ENTERPRISE_NAV——别名页侧栏链接全指 /enterprise/*）、外壳层（DashboardShell scope prop）、后端 RBAC（rbac_service.py 三级角色，fail-closed）。

**部署与 nginx（评审修订，配置阅读结论，未起容器运行时验证）**：部署是同域路径前缀（docker-compose.prod.yml 三服务 api/web/nginx）。但**两层 nginx 均有缺口**：
- 外层 `infra/nginx/agentnet.conf`：有 `location /` catch-all 兜底（:157-162），但 :120 `location = /docs` 精确代理给 FastAPI——而 App.tsx:73-77 在该路径注册公开文档子站，精确匹配优先，**生产上 `/docs` 永远到不了 SPA**。
- 容器内 `apps/web/nginx.default.conf:14-23`：**只有 `/app/`、`/admin/`、`/login` 三条 try_files，无 `location /`、无 `/enterprise/`**——`/enterprise/xxx` 深链或刷新按 nginx 语义做静态查找失败即 404（外层 catch-all 把请求转发到 web 容器，但容器内无 fallback）。

**鉴权 cookie（复核通过）**：dashboard_auth.py:37-55 的 session/CSRF cookie 为 `samesite=lax`、`path=/`、无 Domain 属性（host-only）——同域路径前缀方案确无跨子域 cookie 罐问题；但正因 host-only，任何子域变体必须重设 `Domain=.x.com`（带来 RFC 6265bis §8.6 的兄弟子域 cookie 污染面）。此点双向成立，原文对 B/C 的判断方向正确。

**角色与权限缺口**（引代码路径可核）：
- UserRole 枚举只有 user/admin/super_admin，DB CHECK 约束写死三值（user.py:14-17、22-27）；User **无 org/tenant 字段**。
- 企业普通员工：完全不覆盖（role=user 只有 own 前缀权限，前端被 RequireAdmin 重定向，后端企业端点一律 403）。
- 企业管理者：**部分覆盖且范畴错误**——企业开通直接把人升级为平台级 admin（access_request_service.py:152 `user.role = "admin"`），而 admin 的 PERM_READ_GLOBAL_* 对应全表无过滤查询（越权跨企业）；`services/auth.py:36-37` 注释把 admin 称作 "enterprise access"，即设计上就是用平台 admin 冒充企业管理者。
- **企业实体挂在个人账号上且级联消亡**：NetworkScope.user_id 非空、`ondelete=CASCADE`（network_scope.py:19-21），User.network_scopes `cascade="all, delete-orphan"`（user.py:77-80），建 scope 时 owner 即申请者本人（access_request_service.py:156-162）——企业管理者离职被 disable 或账号被删，整个企业网络定义随之删除；**无 org 成员表**。
- **登录态按 personal 单一默认设计**：useAuth.ts:36 登录成功 `window.location.href='/app/overview'`（硬刷新、无条件、不携带来源）；LoginPage 全文无 next/redirect target；PublicLayout.tsx:25 已登录用户一律重定向 /app/overview。仅为企业目的开通的用户首屏落在个人控制台，须自行发现 DashboardShell 的 scope 切换按钮；未登录深链 `/enterprise/xxx` 登录后丢失。
- 附带缺陷：`/enterprise/approvals` 挂个人审批页（查 `/v1/dashboard/approvals`，权限 `approval:handle:own`），名不副实且**前端修不了**（后端无企业审批队列）；EgressGatewaysPage 的网关 CRUD 调 `/v1/egress/gateways`，后端无此路由（egress.py 仅 GET egress-logs），写操作不可用；非 admin 访问 `/enterprise/*` 被静默重定向、无任何反馈。

---

## 2. 选项评估

### 选项 A：维持单应用，深化平台边界（推荐，范围经评审扩展）

在现有单 Vite 应用内做构建期与运行时的边界强化，不改部署形态、不拆包。**修订后的范围**（原文仅含懒加载 + i18n 分包 + alias 收敛 + 守卫收敛，评审补充了登录入口与 P0 修复项）：

1. **P0 修复（先行）**：生产 sourcemap 收敛（`sourcemap:'hidden'` 或 .map 不进镜像/ nginx 拒绝）；react-markdown/remark-gfm 移入 dependencies；nginx 两层补齐 `/enterprise/` 与通用 SPA fallback；解决 `/docs` 外层 location 与 SPA 文档子站路径冲突。**在 sourcemap 修复前，「非管理员不下载管理 UI」的隔离论证不成立**——当前任何人可下载 3.19MB 的 .map 直接读到全部 admin/enterprise 源码。
2. **路由级懒加载**：按路由组 `React.lazy` + Suspense（public/docs → personal → admin/enterprise）。**量化收益修正**：admin+enterprise 源码仅占 bundle 的 7.3%，懒加载它们的字节收益有限；真正的字节大头是 markdown 渲染链（26%，仅 DocsMarkdown 使用）——**docs 子站必须一并懒加载**才有实质首屏收益。拆 admin/enterprise chunk 的首要价值是权限泄露面收敛（配合 sourcemap 修复），不是体积。
3. **i18n 按平台 namespace 懒加载**：core.ts:28-31 是 eager `import.meta.glob` 同步构建 CATALOG，translate() 同步英文回退（core.ts:93-99），外部存储为同步契约——**改为按路由组动态加载需重做异步加载与 fallback 语义并改 src/i18n/__tests__ 的同步断言**，且须处理 navigation.ts:82-84 自述的跨 namespace 键依赖（/app/settings 标签键落在 settings 命名域）与 DashboardShell scope 软切换瞬间需 nav+shell+common+目标组 namespace 全就绪的问题。**effort 由「约 1 天」上调为约 3-5 天**。
4. **收敛 /admin alias**：`/admin/*` 改为 301 重定向到 `/enterprise/*`。
5. **守卫收敛**：RequireAdmin 消费 `/me` 已返回的 `permissions`（当前前端零消费），为 RBAC 扩展铺路。
6. **登录入口与深链保持**（评审 B-P3 补充）：登录增加 next/redirect target，未登录深链 `/enterprise/xxx` 登录后回到原页——纯前端，A 范围内可做，是 A 对企业管理者 persona 几乎唯一的直接收益项。

**Effort**：小→中。P0 修复约 2-3 天 + 懒加载与字节预算约 2 天 + i18n 分包 3-5 天 + alias/守卫/登录入口约 3 天，合计 **约 2 周**（原文估 3-5 天被低估，主要因 i18n 同步契约与 P0 项）。

**Pros**：共享资产零成本保单一真源（index.css + tailwind.config + tokens.ts、14 个共享组件、28 个 i18n 文件全部直接 import，无发包、无 peerDependency 双 React 风险）；同源 cookie 零变更；不锁死未来（chunk 边界即未来拆分线）。
**Cons**：客户端门控只是 UX（chunk 存在性可被翻到，但 fail-closed 后端已强制）；三类受众共享发布周期；单体随三端膨胀。

### 选项 B：Monorepo 多应用（apps/web-personal / web-admin / web-enterprise + packages/ui、api-client、i18n、tokens）

**Effort（上调）**：大。原文低估了底座成本——仓库**无根 package.json、无 workspace 文件**，packages/ 全为 Python 包，Dockerfile 用 npm ci：选项 B 意味着 npm→pnpm/workspace **从零搭建**与 Docker 构建链改写；「CI filter ×3」实为**从 0 建 1**（前端 CI 不存在）；还要处理 react-markdown/remark-gfm 错放 devDep 导致的包间依赖断裂。保守 **4-6 周** + 持续包治理。

**Pros**：真正独立部署与发布节奏；共享代码改一处全应用生效；安全姿态可分应用差异化。
**Cons**（每条落具体代码）：共享耦合无法干净切分（/enterprise 20 条路由中 9 条复用 admin 页面；DataTable 22 处跨三组；ApprovalsPage 与 DashboardShell 跨组）；设计系统与 i18n 分裂风险高（单一真源刚建成）；**不解决 RBAC 缺口**，反而把「admin 冒充企业管理者」的错误边界固化成仓库边界；触发条件未达成（一个团队、一个发布周期）。

### 选项 C：单仓多入口 / 构建时按平台拆入口

**Effort（上调）**：中。除原文的多入口配置 + 各自路由树 + basename/try_files + assetPrefix 外，**try_files/basename 需同时改外层 agentnet.conf 与容器内 nginx.default.conf 两层**（原文只讨论外层），且C 的「同域路径前缀零冲突」断言已有现存反证：`/docs` 外层精确 location 与 SPA 文档子站冲突就是活例。约 **2-3 周**。
**Pros**：构建期真隔离；同源优势保留；共享源码同仓。
**Cons**：共享页面归属更尴尬（9 条 /enterprise 路由直接 import features/admin/ 组件，移动则循环引用、共享则拆了个寂寞）；路径前缀四坑；跨入口硬导航破坏 DashboardShell 的运行时 scope 软切换；不解决 RBAC 缺口。

### 选项 D：单应用 + 企业端 RBAC 先行 + 前端权限位分组

**修订：由「并行推荐项」升格为「与阶段 0 并行的强制前置项」**。原文理由 4 自认「正确顺序是先补 RBAC」却把 RBAC 排在阶段 3，自相矛盾——A 的「深化平台边界」只有「个人 vs 平台 admin」两层边界可深化，**没有企业层**；若 D 不与阶段 0 并行，推荐前提失败。

**内容**：后端新增企业/组织实体（解决 NetworkScope 挂个人账号 + 级联消亡：user.py:77-80 cascade="all, delete-orphan"、network_scope.py ondelete=CASCADE）+ enterprise 维度权限 + UserRole 枚举/DB CHECK 迁移 + 企业成员表 + 降级路径（当前企业开通即平台 admin 且不可逆，解除合作只能 disable 整个账号）；前端守卫消费 permissions、ENTERPRISE_NAV 按 has_permission 拆管理者组/员工只读组、沿用 isSuperAdmin 按钮级隐藏范式。
**Effort**：中偏大且主要在后端；前端约 1 周。
**Pros**：唯一直接解决 persona 缺口；与 A 完全兼容（A 的守卫收敛正是 D 的前端部分）。
**Cons**：fail-closed 下漏配即 403 风暴；企业实体建模是产品级决策（开放问题 1）；不解决独立部署诉求。

---

## 3. 推荐与理由（修订后）

**推荐选项 A，且强制要求 D 的后端 RBAC 部分与阶段 0 并行启动。**

1. ~~规模不支持拆分~~（不变）：21 个非测试页面、1 个 JS chunk、MVP 小团队，拆分管理开销远超收益。
2. ~~单一真源是刚建成的核心资产~~（不变）：拆分要么复制漂移要么发包治理，单应用直接 import 最便宜。
3. ~~共享页面归属无干净答案~~（不变）：/enterprise 20 条路由中 9 条复用 admin 页面、ApprovalsPage 跨组、DashboardShell 唯一共用外壳。
4. ~~企业端缺口在后端不在前端~~（**结论不变，但执行顺序修订**）：B/C 拆完不增任何能力反而固化错误边界。**但原文把 RBAC 排在阶段 3 与此自相矛盾——现修订为与阶段 0 并行**，否则 A 对企业管理者 persona 收益接近零（B-P1、B-P3 成立）。
5. ~~部署同源最优~~（结论不变，补充缺陷）：cookie host-only 复核通过、路径前缀保持同源；**但「零冲突」断言被 /docs 反证推翻，且容器内 nginx 对 /enterprise/ 无 fallback 是现存 404 缺陷**，属 P0 修复项。
6. ~~当前最大实际问题是性能~~（**量化修正**）：bundle 中 admin+enterprise 仅 7.3%，markdown 链 26%——首屏收益主要来自懒加载 docs 子站与 markdown 链，admin/enterprise chunk 的价值主要是权限泄露面收敛，**且该收敛以 sourcemap 修复为前提**。
7. ~~不锁死未来~~（不变）。
8. **（新增）P0 缺陷不修复则 A 的论证链断裂**：sourcemap 全量公开使「非管理员看不到管理 UI」为假；前端零 CI 使迁移路线的验收与回归缓解无执行载体——这两项必须先行。

---

## 4. 迁移路线（分阶段，修订后）

- **阶段 -1（P0，约 2-3 天，先行）**：sourcemap 收敛（`sourcemap:'hidden'` + .map 不进镜像或 nginx 拒绝）；react-markdown/remark-gfm 移入 dependencies；nginx 两层补齐 `/enterprise/` 与通用 SPA fallback；解决 `/docs` 路径冲突（重命名 SPA 文档路由或调整外层 location）。**建立最小前端 CI**（build + typecheck + vitest，修正 ci.yml 的 main/master 分支监听），否则后续所有验收无载体。
- **阶段 0（约 2 天，与阶段 3 后端并行启动）**：路由级懒加载——三个路由组 + **docs 子站 + markdown 渲染链**一并 React.lazy；验收标准**从「chunk 个数 >1」改为首屏字节预算**（如 gzip 后首屏 JS 不含 admin/enterprise/docs-markdown 符号，且字节数有量化目标）；加构建后 bundle 分析 CI 护栏。
- **阶段 1（约 3-5 天，上调）**：i18n 按组动态加载——重做 core.ts 的 eager glob 为异步契约与同步回退，处理跨 namespace 键依赖与 scope 软切换就绪集，同步改 src/i18n/__tests__ 断言。
- **阶段 2（约 2 天）**：`/admin/*` 301 重定向；e2e 与 13 张快照基线同步；`/enterprise/approvals` 名不副实——**前端只能隐藏或改名，真正企业审批队列需后端（归入阶段 3）**；处理 EgressGatewaysPage 调不存在路由的缺陷。
- **阶段 3（后端为主，与阶段 0 起并行）**：企业实体建模 + enterprise 维度权限 + UserRole 枚举迁移 + 成员表 + 降级路径；前端守卫消费 permissions、NAV 按权限位拆管理者/员工组。
- **阶段 2.5（约 1 天，可并入阶段 2）**：登录 next/redirect + 深链保持 + 静默重定向反馈页。
- **阶段 4（持续观测）**：拆分触发条件（团队分化、独立发布节奏、安全姿态分化、bundle 膨胀超阈值）每季度复核。

## 5. 风险（修订后，细到后果）

1. **（P0，评审新增）sourcemap 泄露**：3.19MB .map 含全部源码与 node_modules 路径，`public, immutable` 公开——任何访客可读全部 admin/enterprise 源码。后果：全部前端逻辑泄露（含调不存在端点的证据）。缓解：阶段 -1 先修。
2. **（评审新增）前端零 CI**：38 单测/10 e2e/13 快照仅本地运行，playwright webServer 仅 CI 变量存在时配置且无工作流设置。后果：阶段 0-3 的验收与回归缓解无执行载体。缓解：阶段 -1 建最小前端 CI 并修分支监听。
3. **（评审新增）企业实体级联消亡**：owner 被 disable/删除→企业网络定义整体删除，无 org 成员表。后果：阶段 3 的「NAV 按权限位拆组」无可挂载的数据关系。缓解：阶段 3 必须先建实体与成员表。
4. **（评审新增）登录入口默认 personal**：硬刷新无条件跳 /app/overview，深链丢失。后果：A 对企业管理者 persona 收益接近零。缓解：阶段 2.5。
5. 客户端门控被绕过（原有，补充：**以 sourcemap 修复为前提**）。
6. chunk 加载失败白屏：401 拦截器未覆盖 chunk fetch 失败路径。
7. /admin 重定向破坏契约：保留 301 + e2e 同步。
8. 共享页面拆双份漂移（B/C 诱导）。
9. RBAC 迁移：枚举 + CHECK 约束改动，漏配即 403 风暴。
10. EgressGatewaysPage 写操作无后端（现存缺陷）。
11. （评审补充）i18n 分包风险面扩大：除语言切换回退外，**scope 软切换路径**（/admin↔/enterprise 共用 AdminLayout 与 nav.ts，切换瞬间需多 namespace 就绪）与跨 namespace 键依赖。
12. （评审补充）静默重定向无反馈：未来有部分权限的用户将「有权限却找不到入口」。
13. 若现在选 B/C 的叠加风险（双 React、transpilePackages、路径前缀、两层 nginx 重排、13 张快照重做、**另加：无根 package.json 从零搭 workspace、Docker npm ci 链改写、react-markdown/remark-gfm 包依赖断裂**）。

## 6. 开放问题（证据不足以裁决）

1. **企业实体建模**：新增 enterprise_manager 角色还是 org/tenant 字段？NetworkScope 已有 scope_type='enterprise' 但归属单 user——是否升级为一等实体 + 成员表？产品级决策，未裁决。
2. **/admin 与 /enterprise 谁是正统**：注释说 "enterprise routes preferred"，但 8 个页面组件物理上在 features/admin/；alias 收敛方向待定。
3. **EgressGatewaysPage 的 /v1/egress/gateways 契约**：后端缺路由还是前端调错？未运行 e2e 验证实际行为。
4. **首屏性能基线缺失**：仅有产物体积与 sourcemap 模块构成，无 LCP/TTV 实测；字节预算目标需真实数据校准。
5. **企业审批队列语义**：/enterprise/approvals 应改为「我的审批」还是新建企业级队列（需后端权限与数据模型）。
6. **企业员工的产品入口完全缺失**：唯一开通路径是 super_admin+step-up 审批的 RequestAccessPage enterprise 模式，无企业管理者邀请同事流程——属后端+产品决策。
7. **企业端是否有独立部署的业务诉求**：当前无证据；若有，B/C 触发条件提前成立。

## 附：选项对比矩阵（修订后）

| 维度 | A 单应用深化边界 | B monorepo 多应用 | C 多入口/构建拆分 | D RBAC 先行+权限分组 |
|---|---|---|---|---|
| Effort | 小→中（约 2 周，上调） | 大（4-6 周+底座从零+治理，上调） | 中（2-3 周+两层 nginx，上调） | 中（后端为主） |
| 解决 persona 缺口 | 需配 D 后端（并行） | 否 | 否 | **是** |
| 设计系统/i18n 单一真源 | 保持 | 风险高 | 保持 | 保持 |
| 10 个共享文件归属 | 无问题 | 必须进共享包=意义被对冲 | 强行切分循环引用 | 无问题 |
| 独立部署/发布节奏 | 无 | 有 | 有 | 无 |
| 鉴权 | 同源零变更（cookie 复核通过） | 同源或跨域（子域需 Domain=.x.com） | 同源+路径前缀四坑 | 同源零变更 |
| bundle 收益 | docs/markdown 懒加载为主（量化） | 拆三包 | 三产物 | 无 |
| **P0 前置依赖** | sourcemap 修复 + 前端 CI 先行 | 同左+底座 | 同左+两层 nginx | — |
| 锁死未来 | 否（chunk 即拆分线） | — | — | 否 |

**最终裁决（v2）：A 先行，但必须同时完成阶段 -1 的 P0 修复（否则隔离论证不成立）并使 D 的后端 RBAC 部分与阶段 0 并行（否则推荐前提失败）；B/C 在阶段 4 触发条件达成前不启动。**

---

## 评审意见裁决记录（本节为 v2 修订依据，非 diff）

**完全采纳（工程 blocker）**：
- 生产 sourcemap 全量公开——实测复核成立（3,194,879 字节 .map、Dockerfile 原样打入、`public, immutable` 无拒绝规则）。原文第 53 行收益论证与第 145 行验收工具自相矛盾，已修正为 P0 先修。
- 前端零 CI——实测复核成立（ci.yml 纯后端、push 只监听 main 而默认分支 master）。迁移路线验收无载体，已增「阶段 -1 建最小前端 CI」。

**采纳（concern 修正论证）**：
- web 容器 nginx 缺 /enterprise fallback 与通用 fallback（配置阅读结论，未起容器验证）——已纠正原文对 catch-all 的误读并列为 P0。
- /docs 外层 location 精确匹配与 SPA 子站冲突——「路径前缀零冲突」断言撤回。
- chunk 拆分收益量化（7.3% vs 26%）与验收标准错误——已改为字节预算并纳入 docs/markdown 懒加载。
- i18n 分包工程量低估——上调至 3-5 天，补 scope 软切换与跨 namespace 键依赖风险。
- react-markdown/remark-gfm 错放 devDependencies——已修正依赖盘点并列为 P0。
- B/C effort 缺底座成本——上调。
- cookie host-only 双向成立——复核通过，结论方向不变。

**采纳（产品 blocker，改变执行顺序而非结论）**：
- persona 缺口与排序矛盾——D 的后端部分由「并行推荐」升为「与阶段 0 并行的强制前置」。
- 企业实体级联消亡——增为风险 3 与阶段 3 必做项。
- 登录入口 personal 默认——增阶段 2.5。

**部分保留**：chunk 拆分的「未授权不下载」价值仍成立，但其定位从体积收益改为权限泄露面收敛且依赖 sourcemap 修复——与评审判断一致，仅表述更精确。
**无不同意项**：两轮评审的可复核断言全部经本会话实测验证成立；未验证项（nginx 运行时行为、e2e 实跑）已如实标注为「配置阅读结论/未运行」。
