import { useLocation, Link } from 'react-router-dom';

export default function RequestAccessSubmittedPage() {
  const location = useLocation();
  const state = location.state as { submitted?: boolean; requestId?: string } | null;
  const isValid = state?.submitted === true && typeof state.requestId === 'string' && state.requestId.trim() !== '';

  if (!isValid) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div className="max-w-md w-full text-center">
          <h1 className="text-xl font-bold">Unable to Confirm Access Request</h1>
          <p className="mt-2 text-sm text-gray-500">
            We could not verify that an access request was submitted. If you believe this is an error, please try submitting your request again.
          </p>
          <div className="mt-6">
            <Link
              to="/request-access"
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700"
            >
              Return to Request Form
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="max-w-md w-full text-center">
        <h1 className="text-xl font-bold">Request Submitted</h1>
        <p className="mt-2 text-sm text-gray-500">
          Your access request has been received and will be reviewed.
        </p>

        <div className="mt-4 p-3 bg-gray-100 rounded-md">
          <p className="text-xs text-gray-500">Request ID</p>
          <p className="text-sm font-mono font-medium text-gray-700 break-all">
            {state.requestId}
          </p>
        </div>

        <div className="mt-6">
          <Link
            to="/login"
            className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Sign In
          </Link>
        </div>

        <p className="mt-4 text-xs text-gray-400">
          You will be notified when your request is reviewed. No credentials are
          sent via email.
        </p>
      </div>
    </div>
  );
}
