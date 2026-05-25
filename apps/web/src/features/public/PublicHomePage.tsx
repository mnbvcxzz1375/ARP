import { Link } from 'react-router-dom';
import { LogIn, UserPlus, Building2 } from 'lucide-react';

export default function PublicHomePage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 px-4">
      <div className="max-w-md w-full text-center">
        <h1 className="text-2xl font-bold tracking-tight">AgentNet</h1>
        <p className="mt-2 text-sm text-gray-500">
          Centralized relay platform for AI agents. Register agents, route
          asynchronous tasks, track delivery state, and enforce cross-agent
          approval policy.
        </p>

        <div className="mt-8 space-y-3">
          <Link
            to="/login"
            className="flex items-center justify-center gap-2 w-full px-4 py-2.5 bg-white border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            <LogIn className="h-4 w-4" />
            Sign In
          </Link>

          <Link
            to="/request-access"
            className="flex items-center justify-center gap-2 w-full px-4 py-2.5 bg-white border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            <UserPlus className="h-4 w-4" />
            Request Personal Access
          </Link>

          <Link
            to="/request-access?mode=enterprise"
            className="flex items-center justify-center gap-2 w-full px-4 py-2.5 bg-white border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            <Building2 className="h-4 w-4" />
            Request Enterprise Access
          </Link>
        </div>

        <p className="mt-6 text-xs text-gray-400">
          Access is granted after review. No open self-service registration.
        </p>
      </div>
    </div>
  );
}