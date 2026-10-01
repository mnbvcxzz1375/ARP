import { cn } from '../lib/utils';
import { PIXEL_CHIP } from '../lib/tokens';
import { useT } from '../i18n';

// Roles are identity, not status: the LED trio (ok/warn/bad) is reserved for
// real states only. super_admin uses the non-semantic raised-neutral chip
// (fixed #cbdbfc on #4b4968, 6.14:1, AA in both themes) so no role borrows a
// status color; admin keeps the accent emphasis chip (5.36:1 both themes).
const ROLE_MAP: Record<string, string> = {
  user: PIXEL_CHIP.info,
  admin: PIXEL_CHIP.accent,
  super_admin: PIXEL_CHIP.neutral,
};

/** Translation keys (namespace `common`) for known roles. */
const ROLE_LABEL_KEY: Record<string, string> = {
  user: 'common.role.user',
  admin: 'common.role.admin',
  super_admin: 'common.role.superAdmin',
};

export default function RoleBadge({ role }: { role: string }) {
  const t = useT();
  const key = role.toLowerCase();
  const cls = ROLE_MAP[key] ?? PIXEL_CHIP.neutral;
  const labelKey = ROLE_LABEL_KEY[key];
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 text-sm font-pixel leading-none',
        cls,
      )}
    >
      {labelKey ? t(labelKey) : role.replace(/_/g, ' ')}
    </span>
  );
}
