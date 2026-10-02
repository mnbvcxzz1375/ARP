/**
 * 个人路由页（命名空间 `routing`）- 中文。
 *
 * 覆盖 features/routing/PersonalRoutingPage.tsx（路由范围开关、
 * 路由模式条、边缘中继健康卡片、最近路由决策）。
 * 翻译规则：src/i18n/glossary.md。
 */
const routing = {
  // 页面框架
  'page.title': '我的路由',
  'error.loadScope': '加载路由范围失败',
  'error.loadEdgeRelays': '加载边缘中继失败',
  'error.loadRouteDecisions': '加载路由决策失败',
  'error.updateScope': '更新范围失败',

  // 路由范围区
  'section.scope': '路由范围',
  'field.defaultRelayType': '默认中继类型',
  'field.edgeRelay': '边缘中继',
  'field.edgeRelayHint': '开启后，发送时将使用个人边缘中继节点。任意可用的个人边缘中继均可能被使用——中继不按用户隔离。',
  'field.secureChannel': '安全通道',
  'field.secureChannelHint': '启用端到端加密通道',

  // 路由模式区
  'section.mode': '路由模式',
  'mode.fast': '快速',
  'mode.fastDescription': '延迟最低，可能跳过可靠性检查',
  'mode.normal': '均衡',
  'mode.normalDescription': '兼顾延迟与可靠性',
  'mode.reliable': '可靠',
  'mode.reliableDescription': '最高投递保障，延迟较高',
  'mode.switchHint': '路由模式可随时切换，立即生效',

  // 边缘中继健康区
  'section.edgeHealth': '边缘中继健康',
  'empty.noEdgeRelays': '尚未配置个人边缘中继',
  'relay.load': '负载',
  'relay.latency': '延迟',
  'relay.successRate': '成功率',
  'relay.healthy': '健康',
  'fieldValue.yes': '是',
  'fieldValue.no': '否',

  // 最近路由决策区
  'section.recentDecisions': '最近路由决策',
  'table.taskId': '任务 ID',
  'table.routeType': '路由类型',
  'table.risk': '风险',
  'table.fallbackFrom': '回退来源',
  'table.fallbackReason': '回退原因',
  'table.shadow': '影子模式',
  'table.decisionTime': '决策耗时 (ms)',
  'table.created': '创建时间',
};

export default routing;
