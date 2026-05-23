import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import StepUpDialog from '../StepUpDialog';

vi.mock('../../api/client', () => ({
  default: { post: vi.fn() },
}));

import api from '../../api/client';

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe('StepUpDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders nothing when closed', () => {
    renderWithClient(
      <StepUpDialog open={false} onSuccess={vi.fn()} onCancel={vi.fn()} />
    );
    expect(screen.queryByText('Step-Up Verification')).not.toBeInTheDocument();
  });

  it('renders the dialog when open', () => {
    renderWithClient(
      <StepUpDialog open={true} onSuccess={vi.fn()} onCancel={vi.fn()} />
    );
    expect(screen.getByText('Step-Up Verification')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Enter your API key')).toBeInTheDocument();
    expect(screen.getByText('Verify')).toBeInTheDocument();
  });

  it('disables verify button when input is empty', () => {
    renderWithClient(
      <StepUpDialog open={true} onSuccess={vi.fn()} onCancel={vi.fn()} />
    );
    const verifyButton = screen.getByText('Verify');
    expect(verifyButton).toBeDisabled();
  });

  it('enables verify button when input is filled', () => {
    renderWithClient(
      <StepUpDialog open={true} onSuccess={vi.fn()} onCancel={vi.fn()} />
    );
    const input = screen.getByPlaceholderText('Enter your API key');
    fireEvent.change(input, { target: { value: 'test-api-key' } });
    expect(screen.getByText('Verify')).not.toBeDisabled();
  });

  it('calls step-up API on submit', async () => {
    (api.post as any).mockResolvedValue({ data: { ok: true } });
    const onSuccess = vi.fn();

    renderWithClient(
      <StepUpDialog open={true} onSuccess={onSuccess} onCancel={vi.fn()} />
    );

    const input = screen.getByPlaceholderText('Enter your API key');
    fireEvent.change(input, { target: { value: 'test-api-key' } });
    fireEvent.click(screen.getByText('Verify'));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/v1/dashboard/auth/step-up', {
        api_key: 'test-api-key',
      });
    });
  });

  it('calls onSuccess after successful step-up', async () => {
    (api.post as any).mockResolvedValue({ data: { ok: true } });
    const onSuccess = vi.fn();

    renderWithClient(
      <StepUpDialog open={true} onSuccess={onSuccess} onCancel={vi.fn()} />
    );

    fireEvent.change(screen.getByPlaceholderText('Enter your API key'), {
      target: { value: 'test-api-key' },
    });
    fireEvent.click(screen.getByText('Verify'));

    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalled();
    });
  });

  it('shows error message on API failure', async () => {
    (api.post as any).mockRejectedValue({
      response: { data: { detail: 'Invalid API key' } },
    });

    renderWithClient(
      <StepUpDialog open={true} onSuccess={vi.fn()} onCancel={vi.fn()} />
    );

    fireEvent.change(screen.getByPlaceholderText('Enter your API key'), {
      target: { value: 'wrong-key' },
    });
    fireEvent.click(screen.getByText('Verify'));

    await waitFor(() => {
      expect(screen.getByTestId('step-up-error')).toHaveTextContent('Invalid API key');
    });
  });

  it('does not call onSuccess on API failure', async () => {
    (api.post as any).mockRejectedValue({
      response: { data: { detail: 'Invalid API key' } },
    });
    const onSuccess = vi.fn();

    renderWithClient(
      <StepUpDialog open={true} onSuccess={onSuccess} onCancel={vi.fn()} />
    );

    fireEvent.change(screen.getByPlaceholderText('Enter your API key'), {
      target: { value: 'wrong-key' },
    });
    fireEvent.click(screen.getByText('Verify'));

    await waitFor(() => {
      expect(screen.getByTestId('step-up-error')).toBeInTheDocument();
    });
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it('clears input and calls onCancel when cancel is clicked', () => {
    const onCancel = vi.fn();

    renderWithClient(
      <StepUpDialog open={true} onSuccess={vi.fn()} onCancel={onCancel} />
    );

    const input = screen.getByPlaceholderText('Enter your API key');
    fireEvent.change(input, { target: { value: 'test-key' } });
    fireEvent.click(screen.getByText('Cancel'));

    expect(onCancel).toHaveBeenCalled();
  });

  it('shows verifying state while pending', async () => {
    (api.post as any).mockReturnValue(new Promise(() => {})); // never resolves, stays pending

    renderWithClient(
      <StepUpDialog open={true} onSuccess={vi.fn()} onCancel={vi.fn()} />
    );

    fireEvent.change(screen.getByPlaceholderText('Enter your API key'), {
      target: { value: 'test-key' },
    });
    fireEvent.click(screen.getByText('Verify'));

    await waitFor(() => {
      expect(screen.getByText('Verifying...')).toBeInTheDocument();
    });
    expect(screen.getByText('Verifying...')).toBeDisabled();
  });
});
