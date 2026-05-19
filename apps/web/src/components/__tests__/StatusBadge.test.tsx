import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import StatusBadge from '../StatusBadge';

describe('StatusBadge', () => {
  it('renders Completed status correctly', () => {
    render(<StatusBadge status="completed" />);
    const badge = screen.getByText('Completed');
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain('bg-green-100');
  });

  it('renders Failed status correctly', () => {
    render(<StatusBadge status="failed" />);
    const badge = screen.getByText('Failed');
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain('bg-red-100');
  });

  it('renders Running status correctly', () => {
    render(<StatusBadge status="running" />);
    expect(screen.getByText('Running')).toBeInTheDocument();
  });

  it('renders online status', () => {
    render(<StatusBadge status="online" />);
    expect(screen.getByText('Online')).toBeInTheDocument();
  });

  it('renders offline status', () => {
    render(<StatusBadge status="offline" />);
    expect(screen.getByText('Offline')).toBeInTheDocument();
  });

  it('handles unknown status', () => {
    render(<StatusBadge status="unknown_status" />);
    expect(screen.getByText('unknown_status')).toBeInTheDocument();
  });
});
