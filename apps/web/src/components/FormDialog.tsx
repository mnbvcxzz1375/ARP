import { ReactNode } from 'react';
import { useT } from '../i18n';

interface FormDialogProps {
  open: boolean;
  title: string;
  onClose: () => void;
  onSubmit: () => void;
  loading?: boolean;
  children: ReactNode;
}

export default function FormDialog({
  open,
  title,
  onClose,
  onSubmit,
  loading = false,
  children,
}: FormDialogProps) {
  const t = useT();
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#191a26]/70"
      role="dialog"
      aria-modal="true"
    >
      <div className="w-full max-w-lg max-h-[90vh] overflow-y-auto p-6 mx-4 bg-pixel-surface border-2 border-pixel-fg shadow-pixel">
        <h3 className="font-display text-pixel-lg text-pixel-fg">{title}</h3>
        <div className="mt-4 space-y-4">{children}</div>
        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={onClose}
            disabled={loading}
            className="min-h-[44px] px-4 py-2 font-pixel text-pixel-base border-2 border-pixel-line text-pixel-fg hover:bg-pixel-raised disabled:opacity-50"
          >
            {t('common.action.cancel')}
          </button>
          <button
            onClick={onSubmit}
            disabled={loading}
            className="min-h-[44px] px-4 py-2 font-pixel text-pixel-base border-2 border-[#191a26] bg-pixel-accent text-[#191a26] disabled:opacity-50"
          >
            {loading ? t('common.status.saving') : t('common.action.submit')}
          </button>
        </div>
      </div>
    </div>
  );
}
