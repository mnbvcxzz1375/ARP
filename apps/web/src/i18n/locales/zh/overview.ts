/**
 * 概览页（命名空间 `overview`）- 中文。
 *
 * 覆盖 src/features/overview/OverviewPage.tsx：KPI 统计卡片、
 * 近期任务 / 近期审批表格与页面级错误状态。
 *
 * 并行翻译分片：概览页文案扩展本文件即可，不要新建注册表文件
 * （locales 由 ../core.ts 的 import.meta.glob 自动汇聚）。
 * 翻译规则见 src/i18n/glossary.md。
 */
const overview = {
  // 页面标题
  'title': '概览',
  'error.load': '加载概览失败',

  // KPI 统计卡片
  'stat.onlineAgents': '在线智能体',
  'stat.tasksToday': '今日任务',
  'stat.failedTasks': '失败任务',
  'stat.pendingApprovals': '待审批',
  'stat.pendingMessages': '待处理消息',

  // 区块标题
  'section.recentTasks': '近期任务',
  'section.recentApprovals': '近期审批',

  // 表格共用列头
  'table.id': 'ID',
  'table.status': '状态',
  'table.created': '创建时间',
  'table.risk': '风险',
};

export default overview;
