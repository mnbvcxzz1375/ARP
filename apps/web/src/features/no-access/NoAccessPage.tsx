import { Link } from 'react-router-dom';
import { useT } from '../../i18n';
import { useLogout } from '../../hooks/useAuth';

/**
 * Fail-closed guard outcome: the session is authenticated but lacks the
 * permissions the guarded route requires. Sending such a visitor to
 * /login?next=... would loop (PublicLayout bounces an authenticated user
 * straight back to next), so guards send them here instead - a public route
 * that explains the situation and offers a way out.
 */
export default function NoAccessPage() {
  const t = useT();
  const logout = useLogout();

  return (
    <div className="min-h-screen bg-pixel-bg text-pixel-fg flex items-center justify-center p-6">
      <div className="max-w-md w-full bg-pixel-surface border-2 border-pixel-line p-8 shadow-pixel">
        <h1 className="font-display text-pixel-lg text-pixel-fg mb-4 leading-relaxed">
          {t('noAccess.title')}
        </h1>
        <p className="font-body text-pixel-base text-pixel-muted mb-8 leading-relaxed">
          {t('noAccess.description')}
        </p>
        <div className="flex flex-col sm:flex-row gap-3">
          <Link
            to="/app/overview"
            className="inline-flex items-center justify-center min-h-[44px] px-4 py-2 font-pixel text-pixel-base border-2 border-[#191a26] bg-pixel-accent text-[#191a26]"
          >
            {t('noAccess.back')}
          </Link>
          <button
            type="button"
            onClick={() => logout.mutate()}
            disabled={logout.isPending}
            className="inline-flex items-center justify-center min-h-[44px] px-4 py-2 font-pixel text-pixel-base border-2 border-pixel-line text-pixel-fg hover:bg-pixel-raised disabled:opacity-50"
          >
            {t('noAccess.logout')}
          </button>
        </div>
      </div>
    </div>
  );
}
