import { useEffect, useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';
import { useAuth } from '../../hooks/useAuth';
import { useFormat, useT } from '../../i18n';
import DataTable from '../../components/DataTable';
import FormDialog from '../../components/FormDialog';
import ConfirmDialog from '../../components/ConfirmDialog';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import EmptyState from '../../components/EmptyState';
import {
  ErrorBanner,
  NeutralChip,
  PageTitleRow,
  PixelField,
  PixButton,
  PIXEL_INPUT,
} from '../connections/pixel-ui';
import { shortUserId } from '../../lib/utils';

/**
 * Organization Members (org domain, /enterprise/members).
 *
 * Backend contract (apps/api/app/routers/organizations.py):
 *   GET    /v1/organizations/mine
 *   GET    /v1/organizations/{org_id}/members
 *   POST   /v1/organizations/{org_id}/members        {user_id, role}
 *   PATCH  /v1/organizations/{org_id}/members/{user_id} {role}
 *   DELETE /v1/organizations/{org_id}/members/{user_id}
 *
 * Every mutation requires the manager role on THAT organization (or the
 * super_admin bypass). The page derives `canManage` from the /me
 * organizations echo (selected membership role) and renders read-only
 * notice + no action buttons otherwise; the backend stays the authority.
 *
 * Member add takes a resolved user_id (UUID), not a username, because the
 * backend cannot look users up by username inside that handler (see the
 * note in apps/api/app/schemas/organizations.py). Sessions that hold the
 * platform user:read:global permission additionally get a username search
 * (GET /v1/dashboard/admin/users?search=...); everyone else pastes the
 * UUID directly.
 */

interface OrgRow {
  org_id: string;
  name: string;
  slug: string;
  role: string | null;
  is_disabled: boolean;
  created_at: string;
}

interface MemberRow {
  user_id: string;
  username: string;
  role: string;
  created_at: string;
}

interface SearchUser {
  user_id: string;
  username: string;
  role: string;
}

const MEMBER_ROLES = ['manager', 'member'] as const;
type MemberRole = (typeof MEMBER_ROLES)[number];

/**
 * Server error detail extractor: returns backend messages verbatim (they
 * are dynamic data, never translated) and falls back to the caller-
 * supplied translated message when nothing usable is present.
 */
function extractDomainError(err: any, fallback: string): string {
  const data = err?.response?.data;
  if (data?.error?.message) return data.error.message;
  if (data?.error?.detail) return data.error.detail;
  if (data?.detail) return data.detail;
  if (data?.message) return data.message;
  return err?.message || fallback;
}

function roleLabel(t: (key: string) => string, role: string): string {
  return role === 'manager' || role === 'member'
    ? t(`enterprise.orgMembers.role.${role}`)
    : role;
}

export default function OrgMembersPage() {
  const qc = useQueryClient();
  const t = useT();
  const { formatDate } = useFormat();
  const { data: user } = useAuth();
  const permissions = user?.permissions ?? [];
  const isSuperAdmin = user?.role === 'super_admin';

  const [selectedOrgId, setSelectedOrgId] = useState<string>('');
  const [formOpen, setFormOpen] = useState(false);
  const [editingMember, setEditingMember] = useState<MemberRow | null>(null);
  const [formRole, setFormRole] = useState<MemberRole>('member');
  const [formUserId, setFormUserId] = useState('');
  const [userQuery, setUserQuery] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [removeMember, setRemoveMember] = useState<MemberRow | null>(null);
  const [removeError, setRemoveError] = useState<string | null>(null);

  // Organizations the session belongs to (the org domain echo).
  const orgsQuery = useQuery({
    queryKey: ['organizations/mine'],
    queryFn: () => api.get('/v1/organizations/mine').then((r) => r.data),
  });
  const orgs: OrgRow[] = useMemo(
    () => orgsQuery.data?.organizations ?? [],
    [orgsQuery.data],
  );
  const selectedOrg = orgs.find((o) => o.org_id === selectedOrgId) ?? null;

  // The membership echo is authoritative for who may manage the selected
  // org; super_admin is admitted through the backend bypass.
  const canManage = isSuperAdmin || selectedOrg?.role === 'manager';

  // Default to the first membership once /mine lands (a single membership
  // renders no selector, so the selection must be wired programmatically).
  useEffect(() => {
    if (!selectedOrgId && orgs.length > 0) {
      setSelectedOrgId(orgs[0].org_id);
    }
  }, [selectedOrgId, orgs]);

  // Username search is only available to sessions the platform user-list
  // endpoint admits (user:read:global); org managers do not hold it.
  const canSearchUsers =
    isSuperAdmin || permissions.includes('user:read:global');

  const membersQuery = useQuery({
    queryKey: ['organizations', selectedOrgId, 'members'],
    queryFn: () =>
      api.get(`/v1/organizations/${selectedOrgId}/members`).then((r) => r.data),
    enabled: !!selectedOrgId,
  });
  const members: MemberRow[] = membersQuery.data?.members ?? [];

  const usersQuery = useQuery({
    queryKey: ['organizations/member-add/user-search', userQuery],
    queryFn: () =>
      api
        .get('/v1/dashboard/admin/users', {
          params: { search: userQuery.trim(), limit: 20, offset: 0 },
        })
        .then((r) => r.data),
    enabled:
      formOpen &&
      !editingMember &&
      canSearchUsers &&
      userQuery.trim().length >= 2,
  });
  const searchResults: SearchUser[] = usersQuery.data?.users ?? [];

  const membersKey = ['organizations', selectedOrgId, 'members'] as const;

  const addMutation = useMutation({
    mutationFn: (body: { user_id: string; role: MemberRole }) =>
      api.post(`/v1/organizations/${selectedOrgId}/members`, body),
    onSuccess: () => {
      setFormOpen(false);
      setFormError(null);
      setUserQuery('');
      setFormUserId('');
      qc.invalidateQueries({ queryKey: membersKey });
    },
    onError: (err: any) => {
      setFormError(extractDomainError(err, t('enterprise.orgMembers.error.add')));
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: MemberRole }) =>
      api.patch(`/v1/organizations/${selectedOrgId}/members/${userId}`, { role }),
    onSuccess: () => {
      setFormOpen(false);
      setEditingMember(null);
      setFormError(null);
      qc.invalidateQueries({ queryKey: membersKey });
    },
    onError: (err: any) => {
      setFormError(extractDomainError(err, t('enterprise.orgMembers.error.update')));
    },
  });

  const removeMutation = useMutation({
    mutationFn: (userId: string) =>
      api.delete(`/v1/organizations/${selectedOrgId}/members/${userId}`),
    onSuccess: () => {
      setRemoveMember(null);
      setRemoveError(null);
      qc.invalidateQueries({ queryKey: membersKey });
    },
    onError: (err: any) => {
      setRemoveError(extractDomainError(err, t('enterprise.orgMembers.error.remove')));
    },
  });

  function handleOpenAdd() {
    setEditingMember(null);
    setFormRole('member');
    setFormUserId('');
    setUserQuery('');
    setFormError(null);
    setFormOpen(true);
  }

  function handleOpenEditRole(member: MemberRow) {
    setEditingMember(member);
    setFormRole(member.role === 'manager' ? 'manager' : 'member');
    setFormError(null);
    setFormOpen(true);
  }

  function handleSubmit() {
    if (editingMember) {
      updateMutation.mutate({ userId: editingMember.user_id, role: formRole });
      return;
    }
    if (!formUserId.trim()) {
      setFormError(t('enterprise.orgMembers.error.userIdRequired'));
      return;
    }
    addMutation.mutate({ user_id: formUserId.trim(), role: formRole });
  }

  if (orgsQuery.isLoading) return <LoadingState />;
  if (orgsQuery.isError) {
    return <ErrorState message={t('enterprise.orgMembers.error.loadOrgs')} />;
  }
  if (orgs.length === 0) {
    return (
      <div>
        <PageTitleRow title={t('enterprise.orgMembers.title')} />
        <EmptyState message={t('enterprise.orgMembers.empty.orgs')} />
      </div>
    );
  }

  return (
    <div>
      <PageTitleRow
        title={t('enterprise.orgMembers.title')}
        actions={
          canManage ? (
            <PixButton onClick={handleOpenAdd}>
              {t('enterprise.orgMembers.action.addMember')}
            </PixButton>
          ) : null
        }
      />

      {/* Org selector: a session may hold multiple memberships. */}
      {orgs.length > 1 && (
        <div className="mb-4 max-w-sm">
          <PixelField
            label={t('enterprise.orgMembers.selector.label')}
            htmlFor="org-members-selector"
          >
            <select
              id="org-members-selector"
              className={PIXEL_INPUT}
              value={selectedOrgId}
              onChange={(e) => {
                setSelectedOrgId(e.target.value);
                setRemoveError(null);
              }}
            >
              {orgs.map((org) => (
                <option key={org.org_id} value={org.org_id}>
                  {org.name}
                  {org.is_disabled ? ` (${t('enterprise.value.no')})` : ''}
                </option>
              ))}
            </select>
          </PixelField>
        </div>
      )}

      {!canManage && selectedOrg && (
        <ErrorBanner
          message={t('enterprise.orgMembers.notice.readOnly')}
          className="mb-4"
        />
      )}

      {selectedOrgId && membersQuery.isLoading && <LoadingState />}
      {selectedOrgId && membersQuery.isError && (
        <ErrorState message={t('enterprise.orgMembers.error.loadMembers')} />
      )}

      {selectedOrgId && !membersQuery.isLoading && !membersQuery.isError && (
        <>
          {members.length === 0 ? (
            <EmptyState message={t('enterprise.orgMembers.empty')} />
          ) : (
            <div className="shadow-pixel-sm">
              <DataTable
                columns={[
                  {
                    key: 'username',
                    label: t('enterprise.orgMembers.table.username'),
                    // Usernames are non-unique display labels; the short
                    // user_id suffix keeps same-named members distinct.
                    render: (r: MemberRow) => (
                      <span>
                        {r.username}{' '}
                        <span className="font-mono text-pixel-muted">· {shortUserId(r.user_id)}</span>
                      </span>
                    ),
                  },
                  {
                    key: 'role',
                    label: t('enterprise.orgMembers.table.role'),
                    render: (r: MemberRow) => (
                      <NeutralChip>{roleLabel(t, r.role)}</NeutralChip>
                    ),
                  },
                  {
                    key: 'created_at',
                    label: t('enterprise.orgMembers.table.joined'),
                    render: (r: MemberRow) =>
                      r.created_at ? formatDate(r.created_at) : '--',
                  },
                  {
                    key: 'actions',
                    label: '',
                    render: (r: MemberRow) =>
                      canManage ? (
                        <div className="flex gap-2">
                          <PixButton
                            variant="ghost"
                            compact
                            onClick={() => handleOpenEditRole(r)}
                          >
                            {t('enterprise.orgMembers.action.editRole')}
                          </PixButton>
                          <PixButton
                            variant="danger"
                            compact
                            onClick={() => {
                              setRemoveMember(r);
                              setRemoveError(null);
                            }}
                          >
                            {t('enterprise.action.delete')}
                          </PixButton>
                        </div>
                      ) : (
                        '--'
                      ),
                  },
                ]}
                data={members}
              />
            </div>
          )}
        </>
      )}

      <FormDialog
        open={formOpen}
        title={
          editingMember
            ? t('enterprise.orgMembers.form.editTitle')
            : t('enterprise.orgMembers.form.addTitle')
        }
        onClose={() => {
          setFormOpen(false);
          setEditingMember(null);
        }}
        onSubmit={handleSubmit}
        loading={addMutation.isPending || updateMutation.isPending}
      >
        <div className="space-y-4">
          {editingMember ? (
            <PixelField
              label={t('enterprise.orgMembers.table.username')}
              htmlFor="org-member-username"
            >
              <input
                id="org-member-username"
                className={PIXEL_INPUT}
                value={editingMember.username}
                readOnly
              />
            </PixelField>
          ) : canSearchUsers ? (
            <>
              <PixelField
                label={t('enterprise.orgMembers.form.username')}
                htmlFor="org-member-search"
              >
                <input
                  id="org-member-search"
                  className={PIXEL_INPUT}
                  value={userQuery}
                  onChange={(e) => {
                    setUserQuery(e.target.value);
                    setFormUserId('');
                  }}
                  placeholder={t('enterprise.orgMembers.form.usernamePlaceholder')}
                />
              </PixelField>
              <PixelField
                label={t('enterprise.orgMembers.form.userId')}
                htmlFor="org-member-user-id"
              >
                <select
                  id="org-member-user-id"
                  className={PIXEL_INPUT}
                  value={formUserId}
                  onChange={(e) => setFormUserId(e.target.value)}
                >
                  <option value="">
                    {userQuery.trim().length >= 2 && usersQuery.isFetching
                      ? t('enterprise.orgMembers.form.searching')
                      : t('enterprise.orgMembers.form.selectUser')}
                  </option>
                  {searchResults.map((candidate) => (
                    <option key={candidate.user_id} value={candidate.user_id}>
                      {/* Disambiguate same-named candidates: the option's
                          value is the user_id, the label shows both. */}
                      {candidate.username} · {shortUserId(candidate.user_id)}
                    </option>
                  ))}
                </select>
              </PixelField>
            </>
          ) : (
            <>
              <PixelField
                label={t('enterprise.orgMembers.form.userId')}
                htmlFor="org-member-user-id"
              >
                <input
                  id="org-member-user-id"
                  className={PIXEL_INPUT}
                  value={formUserId}
                  onChange={(e) => setFormUserId(e.target.value)}
                  placeholder={t('enterprise.orgMembers.form.userIdPlaceholder')}
                />
              </PixelField>
              <p className="font-pixel text-pixel-sm text-pixel-muted">
                {t('enterprise.orgMembers.form.userIdHint')}
              </p>
            </>
          )}
          <PixelField label={t('enterprise.orgMembers.form.role')} htmlFor="org-member-role">
            <select
              id="org-member-role"
              className={PIXEL_INPUT}
              value={formRole}
              onChange={(e) => setFormRole(e.target.value as MemberRole)}
            >
              {MEMBER_ROLES.map((role) => (
                <option key={role} value={role}>
                  {t(`enterprise.orgMembers.role.${role}`)}
                </option>
              ))}
            </select>
          </PixelField>
          {formError && <ErrorBanner message={formError} className="mb-0" />}
        </div>
      </FormDialog>

      <ConfirmDialog
        open={!!removeMember}
        title={t('enterprise.orgMembers.confirm.removeTitle')}
        message={t('enterprise.orgMembers.confirm.removeMessage', {
          username: removeMember?.username ?? '',
          org: selectedOrg?.name ?? '',
        })}
        variant="danger"
        confirmLabel={t('enterprise.action.delete')}
        onConfirm={() =>
          removeMember && removeMutation.mutate(removeMember.user_id)
        }
        onCancel={() => {
          setRemoveMember(null);
          setRemoveError(null);
        }}
      />
      {removeError && <ErrorBanner message={removeError} className="mt-4" />}
    </div>
  );
}
