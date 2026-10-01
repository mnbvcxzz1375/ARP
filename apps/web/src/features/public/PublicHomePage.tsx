import { Link } from 'react-router-dom';
import { LogIn, UserPlus, Building2 } from 'lucide-react';
import { useT } from '../../i18n';

/**
 * Pixel restyle: hard-edged surface panel with a hard-offset pixel shadow,
 * one display title (the only chromatic element on the screen), VT323 body
 * copy and full-width pixel buttons. Content, links and behavior are
 * unchanged.
 *
 * Contrast: primary action uses the accent-solid + #191a26 text pattern
 * (5.36:1 in both themes); secondary actions use fg text on the raised
 * step. All colors are the single-source pixel tokens.
 */
export default function PublicHomePage() {
  const t = useT();
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-pixel-bg px-4 py-8">
      <div className="w-full max-w-md bg-pixel-surface border-2 border-pixel-line shadow-pixel">
        {/* Accent header rule: 4px grid step, decorative (not a status LED). */}
        <div className="h-1 bg-pixel-accent" aria-hidden="true" />

        <div className="p-6 md:p-8 text-center">
          <h1 className="font-display text-pixel-2xl text-pixel-fg chromatic">
            AgentNet
          </h1>
          <p className="mt-4 font-body text-base text-pixel-muted leading-relaxed">
            {t('public.home.description')}
          </p>

          <div className="mt-8 flex flex-col gap-4">
            <Link
              to="/login"
              className="flex items-center justify-center gap-2 w-full min-h-[44px] px-4 py-2 bg-pixel-accent text-[#191a26] border-2 border-[#191a26] shadow-pixel-sm font-pixel text-base hover:bg-pixel-raised hover:text-pixel-fg"
            >
              <LogIn className="h-5 w-5" strokeWidth={2} aria-hidden="true" />
              {t('common.login.submit')}
            </Link>

            <Link
              to="/request-access"
              className="flex items-center justify-center gap-2 w-full min-h-[44px] px-4 py-2 bg-pixel-raised text-pixel-fg border-2 border-pixel-line font-pixel text-base hover:bg-pixel-accent hover:text-[#191a26] hover:border-[#191a26]"
            >
              <UserPlus className="h-5 w-5" strokeWidth={2} aria-hidden="true" />
              {t('public.home.action.requestPersonal')}
            </Link>

            <Link
              to="/request-access?mode=enterprise"
              className="flex items-center justify-center gap-2 w-full min-h-[44px] px-4 py-2 bg-pixel-raised text-pixel-fg border-2 border-pixel-line font-pixel text-base hover:bg-pixel-accent hover:text-[#191a26] hover:border-[#191a26]"
            >
              <Building2 className="h-5 w-5" strokeWidth={2} aria-hidden="true" />
              {t('public.home.action.requestEnterprise')}
            </Link>
          </div>

          <p className="mt-6 font-body text-sm text-pixel-muted">
            {t('public.home.note.review')}
          </p>
        </div>
      </div>
    </div>
  );
}
