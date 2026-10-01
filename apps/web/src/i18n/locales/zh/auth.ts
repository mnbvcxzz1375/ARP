/**
 * 登录页（命名空间 `auth`）- 中文。
 *
 * 覆盖 src/features/auth/LoginPage.tsx。该页的标签、错误与提交文案
 * 已位于 `common` 命名空间（登录页属于公共外壳界面，先于任何功能
 * 命名空间渲染，见 locales/zh/common.ts），直接复用；本命名空间仅
 * 存放其余页面专属字符串（输入框占位提示）。
 *
 * 并行翻译分片：登录页文案扩展本文件即可，不要新建注册表文件
 * （locales 由 ../core.ts 的 import.meta.glob 自动汇聚）。
 * 翻译规则见 src/i18n/glossary.md。
 */
const auth = {
  // LoginPage 输入框
  'login.usernamePlaceholder': '你的用户名',
  // 格式示例：真实 API key 的 'ak_' 前缀字面量。
  'login.apiKeyPlaceholder': 'ak_...',
};

export default auth;
