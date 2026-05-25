import { useState, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import api from '../../api/client';

type RequestMode = 'personal' | 'enterprise';

export default function RequestAccessPage() {
  const navigate = useNavigate();
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
        setErrorMsg('Submission succeeded but no request ID was returned. Please contact support.');
      }
    },
    onError: (error: any) => {
      const msg =
        error?.response?.data?.error?.message ||
        error?.response?.data?.detail ||
        'Submission failed. Please try again later.';
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
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="max-w-md w-full">
        <div className="text-center mb-6">
          <h1 className="text-xl font-bold">Request Access</h1>
          <p className="text-sm text-gray-500 mt-1">
            Submit a request to use AgentNet. Access is granted after review.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Your full name"
            />
          </div>

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Access Mode
            </label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setMode('personal')}
                className={`flex-1 px-3 py-2 rounded-md text-sm font-medium border ${
                  mode === 'personal'
                    ? 'bg-blue-50 border-blue-300 text-blue-700'
                    : 'bg-white border-gray-300 text-gray-600 hover:bg-gray-50'
                }`}
              >
                Personal
              </button>
              <button
                type="button"
                onClick={() => setMode('enterprise')}
                className={`flex-1 px-3 py-2 rounded-md text-sm font-medium border ${
                  mode === 'enterprise'
                    ? 'bg-blue-50 border-blue-300 text-blue-700'
                    : 'bg-white border-gray-300 text-gray-600 hover:bg-gray-50'
                }`}
              >
                Enterprise
              </button>
            </div>
          </div>

          {mode === 'enterprise' && (
            <div>
              <label htmlFor="organization" className="block text-sm font-medium text-gray-700 mb-1">Organization</label>
              <input
                id="organization"
                type="text"
                value={organization}
                onChange={(e) => setOrganization(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Company or team name"
              />
            </div>
          )}

          <div>
            <label htmlFor="use-case" className="block text-sm font-medium text-gray-700 mb-1">Use Case</label>
            <textarea
              id="use-case"
              value={useCase}
              onChange={(e) => setUseCase(e.target.value)}
              required
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="What do you plan to use AgentNet for?"
            />
          </div>

          <div className="flex items-start gap-2">
            <input
              id="terms"
              type="checkbox"
              checked={termsAcknowledged}
              onChange={(e) => setTermsAcknowledged(e.target.checked)}
              className="mt-1 h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <label htmlFor="terms" className="text-xs text-gray-600">
              I acknowledge that access is granted after review, not immediately,
              and that I will not share credentials or misuse the platform.
            </label>
          </div>

          {errorMsg && (
            <p data-testid="request-error" className="text-sm text-red-600">{errorMsg}</p>
          )}

          <button
            type="submit"
            disabled={!isValid || submitMutation.isPending}
            className="w-full py-2 px-4 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {submitMutation.isPending ? 'Submitting...' : 'Submit Request'}
          </button>
        </form>

        <div className="mt-4 text-center">
          <a href="/login" className="text-sm text-gray-500 hover:text-gray-700">
            Already have access? Sign in
          </a>
        </div>
      </div>
    </div>
  );
}