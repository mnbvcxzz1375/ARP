import { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { useT } from '../i18n';

const SECRET_PATTERNS = [
  /sk-[A-Za-z0-9]{20,}/g,
  /agt_sk_[A-Za-z0-9_-]{20,}/g,
  /ak_[A-Za-z0-9_-]{20,}/g,
];

export default function SecretMaskedText({ text, className }: { text: string; className?: string }) {
  const [visible, setVisible] = useState(false);
  const t = useT();

  if (!text) return null;

  let masked = text;
  if (!visible) {
    for (const pattern of SECRET_PATTERNS) {
      masked = masked.replace(pattern, '***');
    }
  }

  return (
    <div className={`flex items-center gap-2 ${className || ''}`}>
      <code className="flex-1 px-2 py-1 font-mono text-lg break-all bg-pixel-bg border-2 border-pixel-line text-pixel-fg">
        {masked}
      </code>
      <button
        onClick={() => setVisible(!visible)}
        aria-label={visible ? t('common.secret.hide') : t('common.secret.show')}
        className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] text-pixel-muted hover:text-pixel-fg border-2 border-pixel-line bg-pixel-surface"
      >
        {visible ? <EyeOff className="w-4 h-4" strokeWidth={2} /> : <Eye className="w-4 h-4" strokeWidth={2} />}
      </button>
    </div>
  );
}
