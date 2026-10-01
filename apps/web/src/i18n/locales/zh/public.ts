/**
 * 公共页面（命名空间 `public`）- 中文。
 *
 * 覆盖 src/features/public/：PublicHomePage、RequestAccessPage、
 * RequestAccessSubmittedPage。登录文案位于 `common` 命名空间
 * （见 locales/zh/common.ts），控制台范围标签位于 `shell`，
 * 因此此处复用已有 key，不再重复定义。
 *
 * 并行翻译分片：公共页面文案扩展本文件即可，不要新建注册表文件
 * （locales 由 ../core.ts 的 import.meta.glob 自动汇聚）。
 * 翻译规则见 src/i18n/glossary.md。
 */
const publicNs = {
  // PublicHomePage
  'home.description':
    '面向 AI 智能体的集中式中继平台。可注册智能体、路由异步任务、跟踪交付状态，并执行跨智能体审批策略。',
  'home.action.requestPersonal': '申请个人访问',
  'home.action.requestEnterprise': '申请企业访问',
  'home.note.review': '访问权限须经审核后开通。不开放自助注册。',

  // RequestAccessPage
  'request.title': '申请访问',
  'request.subtitle': '提交 AgentNet 使用申请。审核通过后开通访问。',
  'field.name': '姓名',
  'field.namePlaceholder': '你的姓名',
  'field.email': '邮箱',
  // 格式示例：RFC 5322 示例邮箱，与语言无关。
  'field.emailPlaceholder': 'you@example.com',
  'field.accessMode': '访问模式',
  'field.organization': '组织',
  'field.organizationPlaceholder': '公司或团队名称',
  'field.useCase': '使用场景',
  'field.useCasePlaceholder': '你计划如何使用 AgentNet？',
  'terms.label':
    '本人知悉：访问权限须经审核后开通，不会立即生效。本人承诺不共享凭据、不滥用平台。',
  'action.submitting': '提交中...',
  'action.submit': '提交申请',
  'action.alreadyHaveAccess': '已有访问权限？立即登录',
  'error.noRequestId': '提交成功，但未返回请求 ID。请联系支持。',
  'error.submitFailed': '提交失败。请稍后重试。',

  // RequestAccessSubmittedPage
  'submitted.title': '申请已提交',
  'submitted.body': '你的访问申请已收到，将进入审核流程。',
  'submitted.requestIdLabel': '请求 ID',
  'submitted.note': '申请审核完成后将通知你。凭据不会通过邮件发送。',
  'unable.title': '无法确认访问申请',
  'unable.body': '我们无法确认已提交访问申请。如果你认为这是误判，请重新提交申请。',
  'unable.action.return': '返回申请表单',
};

export default publicNs;
