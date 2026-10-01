/**
 * 导航标签（命名空间 `nav`）- 中文。
 *
 * 翻译规则见 src/i18n/glossary.md：术语必须使用对照表译法，禁用 em-dash，
 * 短句优先。新增导航项时，en/nav.ts 与本文件必须同步添加同一 key。
 */
const nav = {
  // 个人控制台分组标题
  'group.home': '主页',
  'group.agents': '智能体',
  'group.work': '工作',
  'group.trust': '信任',
  'group.access': '访问',
  'group.network': '网络',

  // 企业控制台分组标题
  'group.commandCenter': '指挥中心',
  'group.topology': '拓扑',
  'group.traffic': '流量',
  'group.governance': '治理',
  'group.continuity': '连续性',
  'group.audit': '审计',
  'group.system': '系统',

  // 个人控制台入口
  'item.overview': '概览',
  'item.agents': '智能体',
  'item.agentDetail': '智能体详情',
  'item.tasks': '任务',
  'item.taskDetail': '任务详情',
  'item.approvals': '审批',
  'item.connections': '连接',
  'item.apiKeys': 'API 密钥',
  'item.localRouting': '本地路由',
  'item.settings': '设置',

  // 企业控制台入口
  'item.networkScopes': '网络范围',
  'item.networkZones': '网络区域',
  'item.relayNodes': '中继节点',
  'item.routePolicies': '路由策略',
  'item.routeDecisions': '路由决策',
  'item.egressGateway': '出口网关',
  'item.dedicatedChannels': '专属通道',
  'item.users': '用户',
  'item.accessRequests': '访问请求',
  'item.approvalQueues': '审批队列',
  'item.slaContinuity': 'SLA 与连续性',
  'item.auditLogs': '审计日志',
  'item.systemHealth': '系统健康',
  'item.orgMembers': '组织成员',

  // 组织域分组标题（组织管理员；无成员关系的账号不显示）
  'group.organization': '组织',
};

export default nav;
