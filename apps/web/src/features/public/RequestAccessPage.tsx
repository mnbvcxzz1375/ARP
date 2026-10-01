import { useState, useMemo } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import api from '../../api/client';
import { useT } from '../../i18n';
import { rememberDocsOrigin } from '../docs/docsEntryMemory';

type RequestMode = 'personal' | 'enterprise';

/**
 * Pixel restyle: hard-edged panel, recessed terminal inputs, accent-solid
 * mode toggle for the active option (accent + #191a26 text = 5.36:1 in both
 * themes) and a solid LED-red error chip (5.89:1 both themes) for the
 * request-error feedback. Form logic, validation, API payload and the
 * request-error test id are unchanged.
 */
export default function RequestAccessPage() {
  const navigate = useNavigate();
  const t = useT();
  const [searchParams] = useSearchParams();
  const initialMode = (searchParams.get('mode') === 'enterprise' ? 'enterprise' : 'personal') as RequestMode;

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [organization, setOrganization] = useState('');
  const [mode, setMode] = useState<RequestMode>(initialMode);
  const [useCase, setUseCase] = useState('');
  const [termsAcknowledged, setTermsAcknowledged] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const isValid = useMemo(() => {
    return name.trim() !== '' && email.trim() !== '' && useCase.trim() !== '' && termsAcknowledged;
  }, [name, email, useCase, termsAcknowledged]);

  const submitMutation = useMutation({
    mutationFn: () =>
      api.post('/v1/public/access-requests', {
        applicant_name: name,
        applicant_email: email,
        organization: organization || null,
        requested_mode: mode,
        use_case: useCase,
        terms_acknowledged: termsAcknowledged,
      }),
    onSuccess: (response) => {
      const requestId = response.data?.request_id;
      if (typeof requestId === 'string' && requestId.trim() !== '') {
        navigate('/request-access/submitted', {
          state: { submitted: true, requestId },
        });
      } else {
        setErrorMsg(t('public.error.noRequestId'));
      }
    },
    onError: (error: any) => {
      const msg =
        error?.response?.data?.error?.message ||
        error?.response?.data?.detail ||
        t('public.error.submitFailed');
      setErrorMsg(msg);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValid) return;
    setErrorMsg(null);
    submitMutation.mutate();
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-pixel-bg px-4 py-8">
      <div className="w-full max-w-md bg-pixel-surface border-2 border-pixel-line shadow-pixel">
        {/* Accent header rule: 4px grid step, decorative (not a status LED). */}
        <div className="h-1 bg-pixel-accent" aria-hidden="true" />

        <div className="p-6 md:p-8">
          <div className="text-center mb-6">
            <h1 className="font-display text-pixel-lg text-pixel-fg chromatic">
              {t('public.request.title')}
            </h1>
            <p className="mt-2 font-body text-base text-pixel-muted">
              {t('public.request.subtitle')}
            </p>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div>
              <label
                htmlFor="name"
                className="block font-body text-base text-pixel-muted mb-1 tracking-pixel"
              >
                {t('public.field.name')}
              </label>
              <input
                id="name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                className="w-full px-3 py-2 bg-pixel-bg border-2 border-pixel-line font-mono text-base text-pixel-fg placeholder:text-pixel-muted"
                placeholder={t('public.field.namePlaceholder')}
              />
            </div>

            <div>
              <label
                htmlFor="email"
                className="block font-body text-base text-pixel-muted mb-1 tracking-pixel"
              >
                {t('public.field.email')}
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-3 py-2 bg-pixel-bg border-2 border-pixel-line font-mono text-base text-pixel-fg placeholder:text-pixel-muted"
                placeholder={t('public.field.emailPlaceholder')}
              />
            </div>

            <div>
              <label className="block font-body text-base text-pixel-muted mb-1 tracking-pixel">
                {t('public.field.accessMode')}
              </label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setMode('personal')}
                  aria-pressed={mode === 'personal'}
                  className={`flex-1 min-h-[44px] px-3 py-2 font-pixel text-base border-2 ${
                    mode === 'personal'
                      ? 'bg-pixel-accent text-[#191a26] border-[#191a26] shadow-pixel-sm'
                      : 'bg-pixel-surface text-pixel-muted border-pixel-line hover:text-pixel-fg'
                  }`}
                >
                  {t('shell.scope.personal')}
                </button>
                <button
                  type="button"
                  onClick={() => setMode('enterprise')}
                  aria-pressed={mode === 'enterprise'}
                  className={`flex-1 min-h-[44px] px-3 py-2 font-pixel text-base border-2 ${
                    mode === 'enterprise'
                      ? 'bg-pixel-accent text-[#191a26] border-[#191a26] shadow-pixel-sm'
                      : 'bg-pixel-surface text-pixel-muted border-pixel-line hover:text-pixel-fg'
                  }`}
                >
                  {t('shell.scope.enterprise')}
                </button>
              </div>
            </div>

            {mode === 'enterprise' && (
              <div>
                <label
                  htmlFor="organization"
                  className="block font-body text-base text-pixel-muted mb-1 tracking-pixel"
                >
                  {t('public.field.organization')}
                </label>
                <input
                  id="organization"
                  type="text"
                  value={organization}
                  onChange={(e) => setOrganization(e.target.value)}
                  className="w-full px-3 py-2 bg-pixel-bg border-2 border-pixel-line font-mono text-base text-pixel-fg placeholder:text-pixel-muted"
                  placeholder={t('public.field.organizationPlaceholder')}
                />
              </div>
            )}

            <div>
              <label
                htmlFor="use-case"
                className="block font-body text-base text-pixel-muted mb-1 tracking-pixel"
              >
                {t('public.field.useCase')}
              </label>
              <textarea
                id="use-case"
                value={useCase}
                onChange={(e) => setUseCase(e.target.value)}
                required
                rows={3}
                className="w-full px-3 py-2 bg-pixel-bg border-2 border-pixel-line font-mono text-base text-pixel-fg placeholder:text-pixel-muted resize-y"
                placeholder={t('public.field.useCasePlaceholder')}
              />
            </div>

            <div className="flex items-start gap-3">
              <input
                id="terms"
                type="checkbox"
                checked={termsAcknowledged}
                onChange={(e) => setTermsAcknowledged(e.target.checked)}
                className="mt-1 h-5 w-5 accent-pixel-accent"
              />
              <label htmlFor="terms" className="font-body text-sm text-pixel-muted leading-relaxed">
                {t('public.terms.label')}
              </label>
            </div>

            {errorMsg && (
              <p
                data-testid="request-error"
                className="px-3 py-2 text-base font-pixel bg-pixel-led-red text-[#f4f4fa] border-2 border-[#191a26]"
              >
                {errorMsg}
              </p>
            )}

            <button
              type="submit"
              disabled={!isValid || submitMutation.isPending}
              className="w-full min-h-[44px] py-2 px-4 bg-pixel-accent text-[#191a26] border-2 border-[#191a26] shadow-pixel-sm font-pixel text-base hover:bg-pixel-raised hover:text-pixel-fg disabled:bg-pixel-line disabled:text-pixel-muted disabled:border-pixel-line disabled:shadow-none disabled:cursor-not-allowed"
            >
              {submitMutation.isPending
                ? t('public.action.submitting')
                : t('public.action.submit')}
            </button>
          </form>

          <div className="mt-4 flex flex-col items-center gap-2 text-center">
            <a
              href="/login"
              className="font-body text-base text-pixel-muted hover:text-pixel-fg underline"
            >
              {t('public.action.alreadyHaveAccess')}
            </a>
            {/* In-card docs entry: the fixed bottom-bar link is easy to
                miss on a form screen. */}
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
