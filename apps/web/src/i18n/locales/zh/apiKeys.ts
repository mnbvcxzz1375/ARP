/**
 * API 密钥页（命名空间 `apiKeys`）- 中文。
 *
 * 覆盖 src/features/api-keys/ApiKeysPage.tsx：创建密钥表单、
 * 新密钥成功面板、密钥表格与吊销确认对话框。共用操作标签
 * （关闭 / 取消）来自 `common` 命名空间，直接复用，不再重复定义。
 *
 * 并行翻译分片：API 密钥页文案扩展本文件即可，不要新建注册表
 * 文件（locales 由 ../core.ts 的 import.meta.glob 自动汇聚）。
 * 翻译规则见 src/i18n/glossary.md。
 */
const apiKeys = {
  // 页面标题
  'title': 'API 密钥',
  'error.load': '加载 API 密钥失败',

  // 创建 API 密钥表单
  'create.title': '创建 API 密钥',
  'create.field.name': '名称',
  'create.field.namePlaceholder': '我的 API 密钥',
  'create.field.expires': '过期时间（选填）',
  'create.action.creating': '创建中...',
  'create.action.submit': '创建密钥',
  'error.create': '创建 API 密钥失败',

  // 新密钥成功面板
  'created.title': '已创建 API 密钥：{{name}}',
  'created.note': '请立即复制此密钥。之后将无法再次查看。',

  // 密钥表格
  'table.name': '名称',
  'table.keyPrefix': '密钥前缀',
  'table.created': '创建时间',
  'table.expires': '过期时间',
  'table.revoked': '吊销时间',
  'table.actions': '操作',
  'action.revoke': '吊销',

  // 吊销确认对话框
  'confirm.revokeTitle': '吊销 API 密钥',
  'confirm.revokeMessage': '确定要吊销“{{name}}”吗？此操作无法撤销。',
  'error.revoke': '吊销 API 密钥失败',
};

export default apiKeys;
