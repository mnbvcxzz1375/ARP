import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterForTesting } from '../../../test-utils';
import RequestAccessPage from '../RequestAccessPage';

vi.mock('../../../api/client', () => ({
  default: { post: vi.fn() },
}));

import api from '../../../api/client';

function renderPage(initialEntries?: string[]) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterForTesting initialEntries={initialEntries || ['/request-access']}>
        <RequestAccessPage />
      </RouterForTesting>
    </QueryClientProvider>,
  );
}

describe('RequestAccessPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the form with required fields', () => {
    renderPage();
    expect(screen.getByLabelText('Name')).toBeInTheDocument();
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
    expect(screen.getByLabelText('Use Case')).toBeInTheDocument();
    expect(screen.getByText('Submit Request')).toBeInTheDocument();
  });

  it('disables submit button when fields are empty', () => {
    renderPage();
    expect(screen.getByText('Submit Request')).toBeDisabled();
  });

  it('enables submit button when all fields are valid', () => {
    renderPage();
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Test User' } });
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'test@example.com' } });
    fireEvent.change(screen.getByLabelText('Use Case'), { target: { value: 'Testing' } });
    fireEvent.click(screen.getByRole('checkbox'));

    expect(screen.getByText('Submit Request')).not.toBeDisabled();
  });

  it('pre-selects enterprise mode from URL params', () => {
    renderPage(['/request-access?mode=enterprise']);
    const enterpriseBtn = screen.getByText('Enterprise');
    // Visual-only assertion updated for the pixel restyle: the active mode
    // toggle is now an accent-solid pixel block (was legacy bg-blue-50).
    expect(enterpriseBtn.className).toContain('bg-pixel-accent');
  });

  it('navigates to submitted page with state on API success with request_id', async () => {
    (api.post as any).mockResolvedValue({
      data: { request_id: 'abc-123', status: 'pending' },
    });

    renderPage();
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Jane Doe' } });
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'jane@example.com' } });
    fireEvent.change(screen.getByLabelText('Use Case'), { target: { value: 'Testing' } });
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByText('Submit Request'));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/v1/public/access-requests', {
        applicant_name: 'Jane Doe',
        applicant_email: 'jane@example.com',
        organization: null,
        requested_mode: 'personal',
        use_case: 'Testing',
        terms_acknowledged: true,
      });
    });
  });

  it('stays on form and shows error when API succeeds but request_id is missing', async () => {
    (api.post as any).mockResolvedValue({
      data: { status: 'pending' },
    });

    renderPage();
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'No ID User' } });
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'noid@example.com' } });
    fireEvent.change(screen.getByLabelText('Use Case'), { target: { value: 'Testing' } });
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByText('Submit Request'));

    await waitFor(() => {
      expect(screen.getByTestId('request-error')).toHaveTextContent('no request ID was returned');
    });
    expect(screen.getByText('Submit Request')).toBeInTheDocument();
  });

  it('stays on form and shows error when API succeeds but request_id is empty string', async () => {
    (api.post as any).mockResolvedValue({
      data: { request_id: '', status: 'pending' },
    });

    renderPage();
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Empty ID User' } });
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'empty@example.com' } });
    fireEvent.change(screen.getByLabelText('Use Case'), { target: { value: 'Testing' } });
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByText('Submit Request'));

    await waitFor(() => {
      expect(screen.getByTestId('request-error')).toHaveTextContent('no request ID was returned');
    });
    expect(screen.getByText('Submit Request')).toBeInTheDocument();
  });

  it('shows error and stays on form on API failure', async () => {
    (api.post as any).mockRejectedValue({
      response: { data: { error: { message: 'A pending request already exists' } } },
    });

    renderPage();
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Dup User' } });
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'dup@example.com' } });
    fireEvent.change(screen.getByLabelText('Use Case'), { target: { value: 'Duplicate' } });
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByText('Submit Request'));

    await waitFor(() => {
      expect(screen.getByTestId('request-error')).toHaveTextContent('A pending request already exists');
    });
    // Still on form - submit button still present
    expect(screen.getByText('Submit Request')).toBeInTheDocument();
  });

  it('does not navigate on 500 error', async () => {
    (api.post as any).mockRejectedValue({
      response: { status: 500, data: { detail: 'Internal server error' } },
    });

    renderPage();
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'User' } });
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@example.com' } });
    fireEvent.change(screen.getByLabelText('Use Case'), { target: { value: 'Testing' } });
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByText('Submit Request'));

    await waitFor(() => {
      expect(screen.getByTestId('request-error')).toBeInTheDocument();
    });
    // Form still present, not on submitted page
    expect(screen.queryByText('Request Submitted')).not.toBeInTheDocument();
  });

  it('shows organization field when enterprise mode is selected', () => {
    renderPage();
    fireEvent.click(screen.getByText('Enterprise'));
    expect(screen.getByLabelText('Organization')).toBeInTheDocument();
  });
});
