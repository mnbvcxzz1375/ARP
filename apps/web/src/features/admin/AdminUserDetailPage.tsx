import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../../api/client';
import { useT, useFormat } from '../../i18n';
import RoleBadge from '../../components/RoleBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import { PageHeader, Panel, Field, BackLink } from './PixelKit';

export default function AdminUserDetailPage() {
  const { userId } = useParams<{ userId: string }>();
  const t = useT();
  const { formatDateTime } = useFormat();

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin/user-detail', userId],
    queryFn: () => api.get(`/v1/dashboard/admin/users/${userId}`).then((r) => r.data),
    enabled: !!userId,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={t('admin.error.loadUserDetail')} />;

  const user = data;

  return (
    <div>
      <BackLink to="/admin/users">{t('admin.back.users')}</BackLink>
      <PageHeader title={user.username} />

      <Panel title={t('admin.userDetail.panel.userDetails')}>
        <dl className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Field label={t('admin.userDetail.field.username')}>{user.username}</Field>
          <Field label={t('admin.userDetail.field.role')}>
            <RoleBadge role={user.role} />
          </Field>
          <Field label={t('admin.userDetail.field.disabled')}>{user.is_disabled ? t('admin.value.yes') : t('admin.value.no')}</Field>
          <Field label={t('admin.table.created')}>{formatDateTime(user.created_at)}</Field>
          <Field label={t('admin.userDetail.field.agents')}>{user.agents_count}</Field>
          <Field label={t('admin.userDetail.field.activeApiKeys')}>{user.active_api_keys_count}</Field>
          <Field label={t('admin.userDetail.field.tasks24h')}>{user.tasks_24h}</Field>
          <Field label={t('admin.userDetail.field.failedTasks24h')}>{user.failed_tasks_24h}</Field>
          <Field label={t('admin.userDetail.field.activeSessions')}>{user.active_sessions_count}</Field>
          <Field label={t('admin.userDetail.field.recentAuditEvents')}>{user.recent_audit_count}</Field>
        </dl>
      </Panel>
    </div>
  );
}
