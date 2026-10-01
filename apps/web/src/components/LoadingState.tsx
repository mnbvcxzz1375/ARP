import { Loader2 } from 'lucide-react';
import { useT } from '../i18n';
import { cn } from '../lib/utils';

export default function LoadingState({ className }: { className?: string }) {
  const t = useT();
  // Loading is an allowed status-feedback animation; disabled under
  // prefers-reduced-motion. The `.animate-spin` class is part of the
  // component contract expected by page tests.
  return (
    <div className={cn('flex items-center justify-center p-12', className)}>
      <Loader2
        className="w-8 h-8 animate-spin text-pixel-muted motion-reduce:animate-none"
        strokeWidth={2}
        aria-hidden="true"
      />
      <span className="sr-only">{t('common.status.loadingSr')}</span>
    </div>
  );
}
