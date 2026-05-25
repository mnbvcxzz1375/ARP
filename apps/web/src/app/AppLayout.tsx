import DashboardShell from './DashboardShell';
import { PERSONAL_NAV } from './navigation';

export default function AppLayout() {
  return <DashboardShell navGroups={PERSONAL_NAV} scope="personal" />;
}