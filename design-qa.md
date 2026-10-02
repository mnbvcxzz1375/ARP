# 像素群岛视觉验收

final result: passed

日期：2026-10-01。范围：个人概览与共用机器人头像。目标是按用户选定的像素群岛方向修复现有产品，不宣称逐像素复刻概念图。

## 比较对象与证据

- source visual truth path: E:/Obsidian/llm-wiki-lab/agentnet-relay-mvp/raw/2026-10-01--browser--creative-review-assets/concept-01-relay-archipelago-pixel-v2.png
- implementation URL: http://127.0.0.1:5188/app/overview
- implementation screenshot path: E:/Obsidian/llm-wiki-lab/agentnet-relay-mvp/raw/2026-10-01--browser--archipelago-repair-assets/final-desktop.png
- viewport: 1487 × 1058 CSS px；源图与实际截图均为 1487 × 1058 像素，截图密度 1；比较页等宽缩放两图，无密度差异。
- state: 中文、深色、个人用户、地图模式、Atlas Worker 选中。源图是概念虚构数据；实现展示实际 Demo fixture 的 5 个自有 Agent、2 在线、10 今日任务，因此数量、任务、时间与源图不同。
- full-view and focused-region comparison: E:/Obsidian/llm-wiki-lab/agentnet-relay-mvp/raw/2026-10-01--browser--archipelago-repair-assets/comparison-final.png
- 两图确实放入同一 HTML 比较页并一起截图；下半部分是两图地图区域的放大取景。载体：reports/archipelago-visual-repair/comparison-final.html。
- 另有 final-mobile-list.png、final-mobile-detail.png（375 × 812）；tablet-map.png（1100 × 900）；short-window-list.png（1487 × 650）；light-desktop.png、english-desktop.png 为过程主题/语言检查。

## 修复与比较历史

1. [P0] 地图高度塌缩：before-desktop.png 与 DOM 测量显示视口仅 52px，缩放 0.0722。修复 DashboardShell 的剩余高度链与概览 grid。最终地图 999 × 712，缩放约 0.989，内容和标签可正常查看。
2. [P1] 岛屿、灯塔和机器人为简陋矩形占位：替换为原创生成的 PNG 海面、两类岛屿、灯塔，后续按用户“机器人好丑”的反馈加入快递员、操作员、侦察员三个配套角色。最终实景与 comparison-final.png 可见完整建筑和有表情的角色；SVG 仅承载原始 PNG 的取景，不绘制替代插画。
3. [P2] 信息栏头像与操作挤在同一行、长 UUID 换行：改身份网格、独立完整宽度入口、两列字段与短 ID/full-title。final-mobile-detail.png 可读。
4. [P2] 手机待处理连接占据列表，详情关闭后焦点丢失：手机初始折叠待处理区；抽屉卸载时恢复焦点，补齐 Tab 环绕。最终浏览器 Escape 后焦点回到 Atlas Worker；回归测试通过。
5. [P2] 小头像身体过小：28/32px 使用半身取景；64px 保留完整角色。final-mobile-list.png 与 final-desktop.png 显示更清楚的头部表情。
6. [P2] 手机列表使用宽展示字体，名字严重截断：最后一轮改 Pixelify Sans 17px、左对齐与可读编号。final-mobile-list.png 中 Atlas/Beacon/Cipher 名称可读，列表可滚动。
7. [P2] 矮窗口地图进一步缩小：低于 700px 高度默认使用列表；短窗口实测 1487 × 650 无水平溢出。

comparison-iteration.png 是群岛和单个新机器人接入后的第一次并排复核；随后增加三个角色、半身取景，压低海面亮度、调整手机字体和短窗口策略，再以相同桌面尺寸和选择状态生成 comparison-final.png。最后比较没有发现剩余可行动的 P0/P1/P2 问题。

## 必查视觉表面

| 表面 | 最终检查 |
| --- | --- |
| 字体与排版 | AgentNet 标题使用 Press Start 2P；节点、详情标题与手机名单使用 Pixelify Sans；中文回落 Microsoft YaHei/CJK 字体。字段与编号使用更紧凑字体。长名称按既有截断规则处理。 |
| 留白与布局 | 左侧 168px；足够宽高时右栏 320px；头部、摘要、地图、动态分开占用 grid 行。手机/中等宽度使用抽屉，短窗口默认列表。实测无水平溢出。 |
| 色彩与状态 | 深蓝夜海、橙色选择与任务线、青色辅助连线；在线/离线保留文字和状态点，避免只靠颜色。外围控件与地图跟随浅/深主题，海面与标签同步换配色。 |
| 图片质量 | 原创 raster 图片，透明背景、完整肢体，无明显遮罩光晕。原图透明留白通过 viewBox 取景处理；角色是粗像素风高分辨率图片，不声称严格 32×40 原生像素网格。 |
| 内容与文案 | 保留真实查询和权限范围。明确连线是任务关系；未伪造实时拓扑、位置、预计完成时间或任务进度。“创建任务”误导入口改为“任务接入指南”，指向原有快速入门。 |
| 图标与交互 | 控件使用现有 Lucide 图标与真实按钮/链接；选择态、键盘方向导航、列表切换、手机抽屉、Escape/焦点返回已检查。小站长仅 hover/focus 触发一次短跳跃，保留减少动态偏好。 |

## 验证

- 全前端 Vitest：648 passed，0 failed。记录：reports/archipelago-visual-repair/vitest.json 与 frontend-tests.log。
- npm run typecheck：退出 0；最终 npm run build:demo：退出 0。
- 新回归覆盖地图选中项不在可见槽位时的 Tab 入口、抽屉条件卸载焦点恢复与 Tab 环绕。
- 实际浏览器：地图/列表、Agent 选择、ArrowRight/ArrowLeft 与焦点、手机抽屉/Escape、深浅主题、中英文、375/1100/1487 宽度及矮窗口。智能体页面的概览专属布局类已移除，页面无水平溢出。
- console errors: 开发中写入顺序曾产生短暂 HMR 缺失导出错误；导出已补全。2026-10-01T14:46:56.209Z 后完整重新加载没有新增 error。
- 最终桌面原生 img 全部加载，地图高度已测量；头像与建筑均已人工看图确认。

## 预期差异、P3 和边界

概念图的六岛与示例数据不作为伪造业务数据的依据。现有地图最多显示六个节点，多余节点经列表访问；尚未做真实后端/生产验收。保持现有外围主题、导航及 Demo 提示，而不是复刻概念的虚构任务面板。新增角色形象是用户明确要求的后续创作变化。

P3：可继续增加岛屿变体；PNG 合计约 6.37 MB，后续可专门做资源编码/缓存与网络性能测量。本次未进行加载性能量化。构建仍有既有文档 chunk 大小/i18n 混合导入提示，测试有既有 act() 提示；退出码与测试结果正常。

## 实现检查清单

- [x] 实际页面接入素材与角色
- [x] 桌面/手机/矮窗口及键盘操作检查
- [x] 同一输入中的完整页面与局部视觉对比
- [x] 前端测试、类型检查、Demo 构建
- [x] 项目知识、素材来源与交接记录写回

## 海面主题与微动增量验收（2026-10-02）

final result: passed

用户新要求：海面微微运动，亮/暗主题对应亮/暗海面。此前“始终夜景”的设计约定已被该请求更新。

- source visual truth path: E:/Obsidian/llm-wiki-lab/agentnet-relay-mvp/raw/2026-10-01--browser--archipelago-repair-assets/light-desktop.png（旧版亮控件/夜海问题基线）；day-sea.png 为本轮白天素材，night-sea.png 为深色目标素材。
- implementation screenshot path: E:/Obsidian/llm-wiki-lab/agentnet-relay-mvp/raw/2026-10-02--browser--sea-theme-motion-assets/light-qa.png；同目录 dark-qa.png。
- viewport / density: 源与当前对照均1487×1058像素，1487×1058 CSS px、密度1。另检查用户原始1877×1244尺寸。主题为亮色、中文、个人Demo、Atlas选中；fixture时间和头像与较早截图存在阶段差异，本轮比较重点是海面、标签与布局。
- full-view / focused comparison evidence: 同目录 comparison.png；由 reports/sea-theme-motion/comparison.html 在同一输入中并排呈现完整页面与地图放大区域。已打开该合成比较图审阅。
- [P1] 亮主题仍用夜海：新增同构图白天海纹理，按全局主题/自动媒体规则切换。最终亮主题清晰青蓝，暗主题仍为夜海。
- [P2] 亮海上旧暗标签/连线不协调：标签改浅底深字，任务线使用更深橙色，辅助线改深蓝；最新light-qa.png可见修复。地图位置和比例保持。
- 微动：独立背景::before层，16秒 steps(8) 往返8px范围；边缘留12px余量，无露底。两次实时观察背景transform不同，岛屿bbox完全一致。
- 可访问性：系统与账户减少动态均得到animation=none。已存偏好用临时独立Demo测试；系统CDP媒体模拟已恢复、临时页已关闭。新的回归确认背景停止时节点仍可选择。
- 字体、间距、图标/文案：沿用已验收结构；地图固定，背景无点击命中，标签依旧有状态文字。色彩/图片质量：两张真实像素纹理一致，亮标签和橙色路径可读，无占位图或额外场景代码绘画。
- 验证：全前端649通过、0失败；最终Demo构建含TS检查通过。原页面console error为空，未验证后端/生产或GPU/网络性能。
- 最终没有剩余可行动P0/P1/P2问题。P3仍为PNG资源编码/性能量化与更多岛屿变体。当前8张原始PNG总计8,201,366字节。

## 任务规模展示增量验收（2026-10-02）

final result: passed

本轮新增数据/交互功能；保持已有像素群岛美术方向。

- source visual truth path: E:/Obsidian/llm-wiki-lab/agentnet-relay-mvp/raw/2026-10-02--browser--sea-theme-motion-assets/dark-desktop.png。
- implementation screenshot path: E:/Obsidian/llm-wiki-lab/agentnet-relay-mvp/raw/2026-10-02--browser--archipelago-scale-assets/final-desktop.png。
- 两原图1877×1244像素/1877×1244 CSS px、密度1；中文/深色/个人Demo/Atlas选中。源为原全部关系展示，实现按用户新需求聚焦并显示活跃/异常；新增工具条和计数属于明确功能变化，fixture时间不同。
- full-view / focused-region comparison evidence: 同目录comparison.png，HTML载体reports/archipelago-scale/comparison.html。已打开同输入的完整/地图区域并排比较；同图还包含375×812手机表格修复前后。
- [P2] 聚焦条出现使地图缩小跳位：改为地图模式内固定区域，点击前后bbox完全一致；初版focus-iteration.png留存，当前final-desktop.png已修复。
- [P2] 线路计数被灯塔盖住：独立高层标签，沿线路1/3处取景，避开中央塔；完整信息具有可访问列表/悬浮提示。当前计数完整可读。
- [P2] 手机任务表格文字竖排：改为局部横向滚动和nowrap，加入滑动提示；tasks-mobile-accepted.png可读，页面无水平溢出。
- [P2] 手机概览工具条过多、仅一行Agent可见：列表不显示地图聚焦工具条，单群岛不显示无用翻页按钮，说明折叠、动态区域更紧凑；overview-mobile-accepted.png显示3个完整Agent与计数。
- 字体/层级：沿用原像素字体和CJK回落，计数/工具条保持适当字号；手机标题左对齐。间距/布局：稳定地图框、六Actor分页、320px详情，窄/矮窗口列表；没有全页面横向溢出。
- 色彩：深/浅主题保留；无关岛屿仅图片淡化，标签可读；当前Actor橙色强调。图片：复用原PNG，没有用代码替换美术。文案：明确收发相关任务、异常24h、当前群岛内路线、有限详情样本和完整列表。
- 图标/交互：真实按钮/下拉/搜索、群岛翻页、聚焦/清除、任务链接和空结果恢复已测。计数标签有完整方向/状态可访问文本，装饰不截获点击。
- 全前端656通过；完整API最终815通过；类型检查/最终Demo构建通过。console error为空。旧任务不受最近50窗口遗漏，接口没有泄露外部对端身份。
- 最终没有剩余可行动P0/P1/P2。P3：更多自定义群岛/坐标持久化、资源优化/负载量化尚可继续；当前是稳定分页，删除前序Actor会收拢。没有修改执行器并发/限流/重试或进行生产部署。

## 动态可读性与文档入口增量（2026-10-02）

final result: passed

源：用户浏览器评论1803×1244深色概览；实现截图 E:/Obsidian/llm-wiki-lab/agentnet-relay-mvp/raw/2026-10-02--browser--activity-readability-assets/desktop.png 与 mobile.png（375×812）。共用侧栏三种状态去除文档按钮，桌面概览保留唯一右上角指南；近期动态时间/事件18px、名称20px，标题与查看全部15px；手机事件16px/底栏128px。实际桌面列表89px、手机85px，scrollHeight=clientHeight，无多余滚动，手机页面宽375无水平溢出；console error为空。检查图像未改美术/色彩，文字无重叠。26项现有相关测试和类型检查通过；仅本地Demo，未重跑全量测试/后端或部署。
