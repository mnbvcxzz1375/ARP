import { useState } from 'react';
import { useLogin } from '../../hooks/useAuth';
import LoadingState from '../../components/LoadingState';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [apiKey, setApiKey] = useState('');
  const login = useLogin();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    login.mutate({ username, api_key: apiKey });
  };

  return (
    <div className="w-full max-w-sm">
      <div className="text-center mb-8">
        <h1 className="text-2xl font-bold">AgentNet</h1>
        <p className="text-sm text-gray-500 mt-1">Sign in to your dashboard</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="your-username"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">API Key</label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            required
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="ak_..."
          />
        </div>

        {login.isError && (
          <p className="text-sm text-red-600">
            Invalid credentials. Please check your username and API key.
          </p>
        )}

        <button
          type="submit"
          disabled={login.isPending}
          className="w-full py-2 px-4 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {login.isPending ? <LoadingState className="py-0" /> : 'Sign In'}
        </button>
      </form>
    </div>
  );
}
