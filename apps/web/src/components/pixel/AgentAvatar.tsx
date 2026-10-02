import { useT } from '../../i18n';
import { getAvatarSprite, normalizeSeed } from '../../lib/avatar';

export interface AgentAvatarProps {
  seed: string | null | undefined;
  size?: 28 | 64;
  name?: string | null | undefined;
  className?: string;
}

/** Stable identities select original pixel artwork shared across all agent views. */
export default function AgentAvatar({ seed, size = 28, name, className }: AgentAvatarProps) {
  const t = useT();
  const identity = normalizeSeed(seed);
  const sprite = getAvatarSprite(identity);
  return (
    <svg
      className={className ? `agent-avatar ${className}` : 'agent-avatar'}
      width={size}
      height={size}
      viewBox={size === 28 ? sprite.portraitViewBox : sprite.viewBox}
      role="img"
      aria-label={t('common.agentAvatar.alt', { name: name?.trim() || identity })}
      data-agent-seed={identity}
      style={{ imageRendering: 'pixelated', flexShrink: 0 }}
    >
      <image href={sprite.src} width={sprite.width} height={sprite.height} aria-hidden="true" />
    </svg>
  );
}
