import { cn } from '../lib/utils';
import { PIXEL_CHIP } from '../lib/tokens';
import { useT } from '../i18n';

const RISK_MAP: Record<string, string> = {
  low: PIXEL_CHIP.ok,
  medium: PIXEL_CHIP.warn,
  high: PIXEL_CHIP.bad,
  critical: PIXEL_CHIP.bad,
};

/** Translation keys (namespace `common`) for known risk levels. */
const RISK_LABEL_KEY: Record<string, string> = {
  low: 'common.riskLevel.low',
  medium: 'common.riskLevel.medium',
  high: 'common.riskLevel.high',
  critical: 'common.riskLevel.critical',
};

export default function RiskBadge({ level }: { level: string }) {
  const t = useT();
  const key = level.toLowerCase();
  const cls = RISK_MAP[key] ?? PIXEL_CHIP.neutral;
  const labelKey = RISK_LABEL_KEY[key];
  // `capitalize` is a no-op for CJK text; English keeps its legacy shape.
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 text-sm font-pixel leading-none capitalize',
        cls,
      )}
    >
      {labelKey ? t(labelKey) : level}
    </span>
  );
}
