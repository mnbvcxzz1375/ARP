# 平台拆分：阶段 4 观测节奏与复核流程

范围：apps/web（单 Vite + React 应用）何时重新评估「不拆分」的结论。
上游决策文档：[platform-split-decision.md](./platform-split-decision.md)（选项 A：维持单应用、深化平台边界；阶段 4 = 持续观测触发条件）。
本文档承载阶段 4：定义四类拆分触发条件、其中唯一可脚本化的度量方法（bundle 膨胀），以及每季度复核的流程与产物。任何修订必须同步更新 decision 文档第 4 节的阶段 4 条目。

---

## 1. 拆分触发条件（四类，任一成立即立案）

「立案」= 在 decision 文档开设 v(n+1) 修订章节，正式评估选项 B（按平台多构建）/ C（多应用），而非默认继续选项 A。四类条件尽量可证伪：前三类是组织与安全姿态的定性信号（给出可核对的观察项），第四类是定量脚本门槛（第 2 节）。

### 1.1 团队分化

- 观察：apps/web 的实际贡献者分化为边界清晰的两组（个人控制台 vs 企业/管理控制台），且跨组代码冲突率上升（每周 merge conflict 中涉及对方目录的比例）。
- 可核对命令：`git log --since="3 months ago" --format="%an" -- apps/web/src | sort | uniq -c`，配合 `git log --stat` 统计每位作者实际改动的目录分布。
- 立案线：连续两个季度，贡献者重叠度低于 30%（同一作者同时改动 `src/features/{public,agents,tasks,approvals,connections,api-keys,routing,settings,overview}` 与 `src/features/{admin,enterprise}` 两组）。

### 1.2 独立发布节奏

- 观察：某个平台域需要独立于主前端的发布窗口（热修、A/B、客户私有分支），而主仓的发布列车（镜像构建 + nginx 同域部署）成为瓶颈。
- 可核对项：季度内因「只敢动一个域」而推迟或回滚的发布次数；任何为单域热修而人工重出镜像的记录。
- 立案线：季度内出现 2 次及以上「单域变更被迫随全量构建/部署一起走」的事故或延迟。

### 1.3 安全姿态分化

- 观察：某一平台的信任模型与另一平台不可调和——例如企业域需要租户隔离的 cookie/session 域、附加的 CSP/合规约束，或企业域页面不得与个人域共享同一 chunk（防权限面经由 chunk 交集泄露）。
- 可核对项：`apps/web/nginx.default.conf` 与 `infra/nginx/agentnet.conf` 的例外规则数量；RBAC 变更（`apps/api/app/services/rbac_service.py` 的 ROLE/ORG 权限集）引发的前端守卫/导航级联改动规模。
- 立案线：任一平台要求的运行时隔离约束在「单应用同域同源 chunk」下无法满足（而非仅仅不便）。

### 1.4 bundle 膨胀超阈值（唯一脚本化度量）

- 度量对象：`dist/assets` 下每个 `.js`/`.css` chunk 的**原始字节数**（非 gzip——直接对应 `ls`/CI 可见体积与决策文档 4.5 节「首屏字节预算」口径）。
- 脚本：`apps/web/scripts/bundle-budget.mjs`。
- 阈值（默认，可用 `--single/--total` 或 `BUNDLE_SINGLE_KIB/BUNDLE_TOTAL_KIB` 覆盖）：
  - 单 chunk ≤ 800 KiB（2026-10-01 校准：基线最大 chunk 为 docsSite 516 KiB，留约 50% 余量）；
  - `dist/assets` 总量 ≤ 2400 KiB（基线 1171 KiB，约 2 倍空间）。
- 脚本失败即说明「单应用继续堆叠的体积成本已超过拆分的迁移成本」，进入立案；阈值本身只能按第 3 节流程调整，不允许随当次构建临时放宽。

---

## 2. bundle 度量的脚本化核对方法

### 2.1 本地核对（每次涉及 src/ 的合并前）

```bash
cd apps/web
npm run build            # tsc -b && vite build
npm run bundle-budget    # node scripts/bundle-budget.mjs
```

输出形态：

```
[bundle-budget] .../apps/web/dist/assets: N chunks, total XXXX.X KiB
   1234.5 KiB  index-AbCdEf.js
      45.2 KiB  EnterpriseOverviewPage-D1e2f3.js
      ...
[bundle-budget] within budget        # 或 BUDGET BREACH: ...（退出码 1）
```

### 2.2 CI 中的核对（阶段 -1 建立最小前端 CI 后强制执行）

在 `npx vite build` 之后追加 `npm run bundle-budget` 作为独立步骤；失败即红灯。CI 与本地必须使用同一脚本与同一默认阈值——阈值改动只能来自季度复核（第 3 节），随提交一并进入仓库，禁止用环境变量在某个流水线上临时调宽。

### 2.3 阈值校准节奏

- 每季度复核时重新跑一次脚本并记录 top-8 chunk（脚本直接打印）。
- 阈值上调的正当理由只有两类：(a) 依赖或功能经过评审确认属于该平台，体积不可逆；(b) gzip 后首屏字节（浏览器实际支付）经路由级懒加载验收后仍下降。纯堆砌新页面不构成理由。
- 阈值下调总是允许的（收紧预算），且鼓励在懒加载/分包优化后立即提出。

### 2.4 与懒加载验收的关系

decision 文档阶段 0 已把验收标准从「chunk 个数」改为「首屏字节预算」。本脚本是其可执行载体：拆分与否的体积论证一律以本脚本输出为准，不再用 chunk 计数、`du` 总量这类不可复现的口径（4.5 节记录过早期用「数 chunk 个数」充当验收标准的错误）。

---

## 3. 每季度复核流程

**负责人**：前端方向负责人（缺位时为最近一个季度改动 apps/web 最多的提交者）。**时间**：每季度首月第二周。**产物**：在本文档「复核记录」追加一节，并按结论回写 decision 文档。

### 3.1 复核步骤（按序）

1. **bundle 度量**：清空 `dist`，`npm run build && npm run bundle-budget`，记录 chunk 数、总量、top-8 chunk 与上季度的差值。任何 breach 立即按 1.4 立案，本季度复核结论即为「建议进入拆分评估」。
2. **触发条件 1-3 的观察项核对**：按 1.1/1.2/1.3 的可核对命令或记录收集数据，逐条给出「成立/不成立 + 证据」。
3. **边界健康度**：确认前端守卫与导航仍由后端权限串驱动（`apps/web/src/lib/permissions.ts`、`src/app/navigation.ts`、`src/app/DashboardShell.tsx`），无新增硬编码 role 字符串；`GLOBAL_ADMIN_PERMISSIONS`/`ORG_DOMAIN_PERMISSIONS` 与后端 `rbac_service.py` 的 ROLE_PERMISSIONS/ORG_ROLE_PERMISSIONS 逐串比对（漂移本身就是 1.3 的安全姿态信号）。
4. **回归面**：上季度 `npx vitest run` 与 e2e 的通过/跳过情况；快照基线（`apps/web/e2e/visual-regression.spec.ts-snapshots/`）的变更是否都有对应的设计变更记录。
5. **结论**：四类条件无一成立 → 「维持选项 A，记录观测值」；任一成立 → 「立案，进入 decision 文档 v(n+1) 评估」，并在该章节引用本季度的证据。

### 3.2 复核记录模板

```
## 复核记录 · 2026Q4 · 负责人 <name>
- bundle：N chunks / total XXXX KiB / largest <chunk> YYYY KiB（上季度差值 +ZZ%）
- 单 chunk 预算：1400 KiB（或本季度调整值 + 理由）
- 1.1 团队分化：不成立（贡献者重叠 XX%，git log 证据）
- 1.2 发布节奏：不成立（单域变更随全量发布 0 次）
- 1.3 安全姿态：不成立（守卫/导航无硬编码 role；权限串与 rbac_service 一致）
- 1.4 bundle 阈值：通过 / BREACH
- 结论：维持选项 A / 立案进入拆分评估
```

---

## 4. 复核记录

### 2026-09-30（决策基线，引用 decision 文档实测）

- 依据 decision 文档 v2 §1 实测（懒加载落地前）：`du -cb dist/assets/*` → 4,505,229 字节（约 4396 KiB），单 JS chunk（index-*.js，约 1086 KiB）。

### 2026-10-01（阶段 0 落地后的实测校准，随脚本建立）

- 实测：`npm run build && npm run bundle-budget` → 82 chunks / total 1171.1 KiB / largest docsSite 516 KiB（markdown 渲染链，仅文档子站消费）、index 321 KiB。路由级懒加载（阶段 0）已把入口从单 chunk 1086 KiB 压到 321 KiB、总量降到约四分之一。
- 阈值校准：单 chunk 800 KiB（docsSite + 约 50% 余量，markdown 链属阶段 0 已确认的不可逆体积）、总量 2400 KiB（基线约 2 倍）。收紧优先：任何新的单一懒 chunk 超过 docsSite 即应立案说明理由。
- 四类触发条件均未成立（单团队、单发布列车、RBAC 并行推进中、体积在预算内）。结论：维持选项 A，下季度按 §3 流程复核。
