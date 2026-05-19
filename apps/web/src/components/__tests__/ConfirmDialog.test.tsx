import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ConfirmDialog from '../ConfirmDialog';

describe('ConfirmDialog', () => {
  it('renders nothing when closed', () => {
    const { container } = render(
      <ConfirmDialog open={false} title="Test" message="Msg" onConfirm={vi.fn()} onCancel={vi.fn()} />
    );
    expect(container.innerHTML).toBe('');
  });

  it('renders title and message when open', () => {
    render(
      <ConfirmDialog open={true} title="Delete Agent" message="Are you sure?" onConfirm={vi.fn()} onCancel={vi.fn()} />
    );
    expect(screen.getByText('Delete Agent')).toBeInTheDocument();
    expect(screen.getByText('Are you sure?')).toBeInTheDocument();
  });

  it('calls onConfirm when confirm clicked', async () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(
      <ConfirmDialog open={true} title="Test" message="Confirm?" onConfirm={onConfirm} onCancel={onCancel} />
    );
    fireEvent.click(screen.getByText('Confirm'));
    expect(onConfirm).toHaveBeenCalledOnce();
    expect(onCancel).not.toHaveBeenCalled();
  });

  it('calls onCancel when cancel clicked', async () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(
      <ConfirmDialog open={true} title="Test" message="Cancel?" onConfirm={onConfirm} onCancel={onCancel} />
    );
    fireEvent.click(screen.getByText('Cancel'));
    expect(onCancel).toHaveBeenCalledOnce();
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it('renders danger variant with red button', () => {
    render(
      <ConfirmDialog open={true} title="Danger" message="Dangerous!" variant="danger" onConfirm={vi.fn()} onCancel={vi.fn()} />
    );
    const btn = screen.getByText('Confirm');
    expect(btn.className).toContain('bg-red-600');
  });

  it('renders custom confirm label', () => {
    render(
      <ConfirmDialog open={true} title="Test" message="Msg" confirmLabel="Delete Forever" onConfirm={vi.fn()} onCancel={vi.fn()} />
    );
    expect(screen.getByText('Delete Forever')).toBeInTheDocument();
  });
});
