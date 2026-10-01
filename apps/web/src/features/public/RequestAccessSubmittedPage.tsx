import { useLocation, Link } from 'react-router-dom';
import { useT } from '../../i18n';

/**
 * Pixel restyle: both the confirmed and unable-to-confirm states render in
 * a hard-edged surface panel with a 4px accent header rule. The request ID
 * is shown on a raised step in the mono font; the primary action uses the
 * accent-solid + #191a26 text pattern (5.36:1 in both themes). Routing
 * state validation and link targets are unchanged.
 */
export default function RequestAccessSubmittedPage() {
  const location = useLocation();
  const t = useT();
  const state = location.state as { submitted?: boolean; requestId?: string } | null;
  const isValid = state?.submitted === true && typeof state.requestId === 'string' && state.requestId.trim() !== '';

  if (!isValid) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-pixel-bg px-4 py-8">
        <div className="w-full max-w-md bg-pixel-surface border-2 border-pixel-line shadow-pixel">
          <div className="h-1 bg-pixel-accent" aria-hidden="true" />
          <div className="p-6 md:p-8 text-center">
            <h1 className="font-display text-pixel-lg text-pixel-fg chromatic">
              {t('public.unable.title')}
            </h1>
            <p className="mt-4 font-body text-base text-pixel-muted leading-relaxed">
              {t('public.unable.body')}
            </p>
            <div className="mt-8">
              <Link
                to="/request-access"
                className="inline-flex items-center justify-center gap-2 min-h-[44px] px-4 py-2 bg-pixel-accent text-[#191a26] border-2 border-[#191a26] shadow-pixel-sm font-pixel text-base hover:bg-pixel-raised hover:text-pixel-fg"
              >
                {t('public.unable.action.return')}
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-pixel-bg px-4 py-8">
      <div className="w-full max-w-md bg-pixel-surface border-2 border-pixel-line shadow-pixel">
        {/* Accent header rule: 4px grid step, decorative (not a status LED). */}
        <div className="h-1 bg-pixel-accent" aria-hidden="true" />

        <div className="p-6 md:p-8 text-center">
          <h1 className="font-display text-pixel-lg text-pixel-fg chromatic">
            {t('public.submitted.title')}
          </h1>
          <p className="mt-4 font-body text-base text-pixel-muted leading-relaxed">
            {t('public.submitted.body')}
          </p>

          <div className="mt-6 p-3 bg-pixel-raised border-2 border-pixel-line text-left">
            <p className="font-body text-sm text-pixel-muted tracking-pixel">
              {t('public.submitted.requestIdLabel')}
            </p>
            <p className="mt-1 font-mono text-base text-pixel-fg break-all">
              {state.requestId}
            </p>
          </div>

          <div className="mt-8">
            <Link
              to="/login"
              className="inline-flex items-center justify-center gap-2 min-h-[44px] px-4 py-2 bg-pixel-raised text-pixel-fg border-2 border-pixel-line font-pixel text-base hover:bg-pixel-accent hover:text-[#191a26] hover:border-[#191a26]"
            >
              {t('common.login.submit')}
            </Link>
          </div>

          <p className="mt-6 font-body text-sm text-pixel-muted">
            {t('public.submitted.note')}
          </p>
        </div>
      </div>
    </div>
  );
}
