/**
 * 应用外壳字符串（命名空间 `shell`）- 中文。
 *
 * 覆盖 DashboardShell（侧边栏范围切换、页脚按钮、移动端底栏、企业横幅）、
 * PublicLayout 页脚组件以及 LanguageSwitcher 本身。翻译规则见
 * src/i18n/glossary.md。
 */
const shell = {
  // 范围切换
  'console.personal': '个人控制台',
  'console.enterprise': '企业控制台',
  'scope.personal': '个人',
  'scope.enterprise': '企业',
  'banner.enterprise': '企业控制台 -- 操作影响所有用户与中继基础设施',

  // 侧边栏控件
  'sidebar.expand': '展开侧边栏',
  'sidebar.collapse': '折叠侧边栏',
  'sidebar.open': '打开导航',
  'sidebar.close': '关闭导航',
  'sidebar.menu': '菜单',

  // 移动端底部导航
  'bottomNav.aria': '主导航',

  // 页脚 / 底栏按钮
  'theme.switchToLight': '切换到浅色主题',
  'theme.switchToDark': '切换到深色主题',
  'theme.label': '主题',
  'logout': '退出登录',
  'docs.entry': '打开文档站',
  'docs.label': '文档',

  // 用户页脚
  'user.defaultName': '用户',
  'user.unknownRole': '未知',
  'user.userIdTitle': '用户 ID：',

  // 语言切换
  'language.aria': '切换语言',
  'language.toggle': '切换语言',
  'language.en': 'EN',
  'language.zh': '中文',

  // 公共页脚
  'footer.poweredBy': 'AgentNet 中继平台',
};

export default shell;
