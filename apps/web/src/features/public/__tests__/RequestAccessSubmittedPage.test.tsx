import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Routes, Route } from 'react-router-dom';
import { RouterForTesting } from '../../../test-utils';
import RequestAccessSubmittedPage from '../RequestAccessSubmittedPage';

function renderSubmitted(initialEntries: string[], state?: Record<string, unknown>) {
  return render(
    <RouterForTesting initialEntries={state ? [{ pathname: initialEntries[0], state }] : initialEntries}>
      <Routes>
        <Route path="/request-access/submitted" element={<RequestAccessSubmittedPage />} />
        <Route path="/request-access" element={<div>Request Form</div>} />
      </Routes>
    </RouterForTesting>,
  );
}

describe('RequestAccessSubmittedPage', () => {
  it('shows success when navigated with valid state', () => {
    renderSubmitted(['/request-access/submitted'], { submitted: true, requestId: 'abc-123' });

    expect(screen.getByText('Request Submitted')).toBeInTheDocument();
    expect(screen.getByText('abc-123')).toBeInTheDocument();
  });

  it('shows unable to confirm when accessed directly without state', () => {
    renderSubmitted(['/request-access/submitted']);

    expect(screen.getByText('Unable to Confirm Access Request')).toBeInTheDocument();
    expect(screen.queryByText('Request Submitted')).not.toBeInTheDocument();
  });

  it('shows unable to confirm when accessed with query string but no state', () => {
    renderSubmitted(['/request-access/submitted?request_id=test-123']);

    expect(screen.getByText('Unable to Confirm Access Request')).toBeInTheDocument();
    expect(screen.queryByText('Request Submitted')).not.toBeInTheDocument();
    expect(screen.queryByText('test-123')).not.toBeInTheDocument();
  });

  it('shows unable to confirm when state has submitted but no requestId', () => {
    renderSubmitted(['/request-access/submitted'], { submitted: true });

    expect(screen.getByText('Unable to Confirm Access Request')).toBeInTheDocument();
    expect(screen.queryByText('Request Submitted')).not.toBeInTheDocument();
  });

  it('shows unable to confirm when state has submitted true but empty requestId', () => {
    renderSubmitted(['/request-access/submitted'], { submitted: true, requestId: '' });

    expect(screen.getByText('Unable to Confirm Access Request')).toBeInTheDocument();
    expect(screen.queryByText('Request Submitted')).not.toBeInTheDocument();
  });

  it('shows unable to confirm when state has submitted false', () => {
    renderSubmitted(['/request-access/submitted'], { submitted: false, requestId: 'abc-123' });

    expect(screen.getByText('Unable to Confirm Access Request')).toBeInTheDocument();
    expect(screen.queryByText('Request Submitted')).not.toBeInTheDocument();
  });

  it('provides return to request form link in unable-to-confirm state', () => {
    renderSubmitted(['/request-access/submitted']);

    expect(screen.getByText('Return to Request Form')).toBeInTheDocument();
    expect(screen.getByText('Return to Request Form').closest('a')).toHaveAttribute('href', '/request-access');
  });
});
