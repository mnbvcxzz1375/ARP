import DashboardShell from './DashboardShell';
import { ENTERPRISE_NAV } from './navigation';

export default function AdminLayout() {
  return <DashboardShell navGroups={ENTERPRISE_NAV} scope="enterprise" />;
}