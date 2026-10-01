import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { DEFAULT_LOGIN_REDIRECT, resolveNextTarget, useLogin } from '../../hooks/useAuth';
import { useT } from '../../i18n';
import LoadingState from '../../components/LoadingState';
import { rememberDocsOrigin } from '../docs/docsEntryMemory';
import { isDemoMode, personaById } from '../../demo';

/**
 * Pixel restyle of the sign-in page. Single hard-edged surface panel with a
 * 6px hard-offset pixel shadow, a 4px accent header rule, one Press Start 2P
 * chromatic title and recessed VT323 terminal inputs.
 *
 * Visual contract notes:
 * - Inputs sit one step below the panel (bg on surface) so the recessed
 *   terminal look stays readable in both themes; focus comes from the
 *   global *:focus-visible accent-2 outline.
 * - The invalid-credentials message is a solid LED-red chip with #f4f4fa
 *   text (5.89:1 in both themes), matching ErrorState.
 * - The primary action is accent-solid + #191a26 text (5.36:1 both themes).
 * - Login logic (useLogin mutate, field ids, data-testid) is untouched.
 */
export default function LoginPage() {
  const t = useT();
  const [username, setUsername] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [searchParams] = useSearchParams();
  const login = useLogin();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Deep-link target: guards redirect to /login?next=<encoded path>.
    // resolveNextTarget rejects anything that is not a same-origin path,
    // falling back to the personal console default.
    const redirectTarget = resolveNextTarget(searchParams.get('next')) ?? DEFAULT_LOGIN_REDIRECT;
    login.mutate({ username, api_key: apiKey, redirectTarget });
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-pixel-bg px-4 py-8">
      <div className="w-full max-w-sm bg-pixel-surface border-2 border-pixel-line shadow-pixel">
        {/* Accent header rule: 4px grid step, decorative (not a status LED). */}
        <div className="h-1 bg-pixel-accent" aria-hidden="true" />

        <div className="p-6 md:p-8">
          <div className="text-center mb-8">
            <h1 className="font-display text-pixel-xl text-pixel-fg chromatic">
              AgentNet
            </h1>
            <p className="mt-2 font-body text-base text-pixel-muted">
              {t('common.login.subtitle')}
            </p>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div>
              <label
                htmlFor="login-username"
                className="block font-body text-base text-pixel-muted mb-1 tracking-pixel"
              >
                {t('common.login.username')}
              </label>
              <input
                id="login-username"
                name="username"
                data-testid="login-username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className="w-full px-3 py-2 bg-pixel-bg border-2 border-pixel-line font-mono text-base text-pixel-fg placeholder:text-pixel-muted"
                placeholder={t('auth.login.usernamePlaceholder')}
              />
            </div>
            <div>
              <label
                htmlFor="login-api-key"
                className="block font-body text-base text-pixel-muted mb-1 tracking-pixel"
              >
                {t('common.login.apiKey')}
              </label>
              <input
                id="login-api-key"
                name="api_key"
                data-testid="login-api-key"
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                required
                className="w-full px-3 py-2 bg-pixel-bg border-2 border-pixel-line font-mono text-base text-pixel-fg placeholder:text-pixel-muted"
                placeholder={t('auth.login.apiKeyPlaceholder')}
              />
            </div>

            {login.isError && (
              <p
                data-testid="login-error"
                className="px-3 py-2 text-base font-pixel bg-pixel-led-red text-[#f4f4fa] border-2 border-[#191a26]"
              >
                {t('common.login.error')}
              </p>
            )}

            <button
              type="submit"
              disabled={login.isPending}
              className="w-full min-h-[44px] py-2 px-4 bg-pixel-accent text-[#191a26] border-2 border-[#191a26] shadow-pixel-sm font-pixel text-base hover:bg-pixel-raised hover:text-pixel-fg disabled:bg-pixel-line disabled:text-pixel-muted disabled:border-pixel-line disabled:shadow-none disabled:cursor-not-allowed"
            >
              {login.isPending ? <LoadingState className="py-0" /> : t('common.login.submit')}
            </button>

            {/* Demo builds only: one-click entry as the seeded super admin.
                The banner persona switcher can then change identity. */}
            {isDemoMode() && (
              <button
                type="button"
                data-testid="demo-login"
                onClick={() => {
                  const p = personaById('super_admin');
                  setUsername(p.username);
                  setApiKey(p.apiKey);
                  login.mutate({
                    username: p.username,
                    api_key: p.apiKey,
                    redirectTarget:
                      resolveNextTarget(searchParams.get('next')) ?? DEFAULT_LOGIN_REDIRECT,
                  });
                }}
                disabled={login.isPending}
                className="w-full min-h-[44px] py-2 px-4 bg-pixel-raised text-pixel-fg border-2 border-pixel-line font-pixel text-base hover:border-pixel-accent disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {t('common.login.demoEntry')}
              </button>
            )}
          </form>

          <div className="mt-4 flex flex-col items-center gap-2 text-center">
            <Link
              to="/request-access"
              className="font-body text-base text-pixel-muted hover:text-pixel-fg underline"
            >
              {t('common.login.requestAccess')}
            </Link>
            {/* In-card docs entry: the fixed bottom-bar link is easy to
                miss on a login screen. */}
            <Link
              to="/docs/quickstart"
              onClick={() => rememberDocsOrigin()}
              className="font-body text-base text-pixel-muted hover:text-pixel-fg underline"
            >
              {t('common.login.docs')}
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
