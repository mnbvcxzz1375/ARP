/**
 * 智能体页面（命名空间 `agents`）- 中文。
 *
 * 覆盖 features/agents/AgentsPage.tsx（列表）与 AgentDetailPage.tsx（详情）。
 * 共享文案放在 `common`；此处仅放置智能体页面专属文案。
 * 翻译规则：src/i18n/glossary.md。
 */
const agents = {
  // 页面框架
  'page.title': '智能体',
  'error.load': '加载智能体失败',
  'error.loadDetail': '加载智能体详情失败',
  'action.backToList': '返回智能体',

  // 故事化空状态（AgentsPage，列表为空时）
  'empty.title': '第一个伙伴还没上岗',
  'empty.subtitle': '接入第一个智能体，中继站就开始营业了',
  // 指向接入指南；/app/agents/new 路由尚不存在，入口先指接入指南。
  'empty.action.quickstart': '查看接入指南',

  // 列表表格（AgentsPage）
  'table.name': '名称',
  'table.agentNumber': '智能体编号',
  'table.view': '查看',
  'table.runtime': '运行时',
  'table.status': '状态',
  'table.policy': '策略',
  'table.created': '创建时间',

  // 详情页（AgentDetailPage）
  'section.coreIdentity': '核心身份',
  'field.agentNumber': '智能体编号',
  'field.name': '名称',
  'field.runtime': '运行时',
  'field.status': '状态',
  'field.inboundPolicy': '入站策略',
  'field.discoverable': '可发现',
  'field.created': '创建时间',
  'field.updated': '更新时间',
  'fieldValue.yes': '是',
  'fieldValue.no': '否',
  'fieldValue.never': '从未',

  // 能力区
  'section.capabilities': '能力',
  'empty.noCapabilities': '无',

  // 令牌元数据区
  'section.tokenMetadata': '令牌元数据',
  'field.tokenPrefix': '令牌前缀',
  'field.tokenCreated': '令牌创建时间',
  'field.tokenRotated': '令牌轮换时间',
};

export default agents;
