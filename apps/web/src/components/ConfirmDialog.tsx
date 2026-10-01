import { ReactNode } from 'react';
import { useT } from '../i18n';
import { cn } from '../lib/utils';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  variant?: 'default' | 'danger';
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  children?: ReactNode;
}

export default function ConfirmDialog({
  open,
  title,
  message,
  variant = 'default',
  confirmLabel,
  cancelLabel,
  onConfirm,
  onCancel,
  children,
}: ConfirmDialogProps) {
  const t = useT();
  const resolvedConfirmLabel = confirmLabel ?? t('common.action.confirm');
  const resolvedCancelLabel = cancelLabel ?? t('common.action.cancel');
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#191a26]/70"
      role="dialog"
      aria-modal="true"
    >
      <div className="w-full max-w-md p-6 mx-4 bg-pixel-surface border-2 border-pixel-fg shadow-pixel">
        <h3 className="font-display text-pixel-lg text-pixel-fg">{title}</h3>
        <p className="mt-3 text-lg text-pixel-muted">{message}</p>
        {children}
        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={onCancel}
            className="min-h-[44px] px-4 py-2 font-pixel text-pixel-base border-2 border-pixel-line text-pixel-fg hover:bg-pixel-raised"
          >
            {resolvedCancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className={cn(
              'min-h-[44px] px-4 py-2 font-pixel text-pixel-base border-2 border-[#191a26]',
              variant === 'danger'
                ? 'bg-pixel-led-red text-[#f4f4fa]'
                : 'bg-pixel-accent text-[#191a26]',
            )}
          >
            {resolvedConfirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
