import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import StatusBadge from '../StatusBadge';

describe('StatusBadge', () => {
  it('renders Completed status correctly', () => {
    render(<StatusBadge status="completed" />);
    const badge = screen.getByText('Completed');
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain('bg-pixel-led-green');
  });

  it('renders Failed status correctly', () => {
    render(<StatusBadge status="failed" />);
    const badge = screen.getByText('Failed');
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain('bg-pixel-led-red');
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

  // M3 relay dataplane hop events (delivery-event timeline).
  it('renders the relay_forwarded hop event', () => {
    render(<StatusBadge status="relay_forwarded" />);
    const badge = screen.getByText('Relay Forwarded');
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain('bg-pixel-accent-2');
  });

  it('renders the channel_forwarded hop event', () => {
    render(<StatusBadge status="channel_forwarded" />);
    const badge = screen.getByText('Channel Forwarded');
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain('bg-pixel-accent-2');
  });

  // TaskStatus approval step (constants.py): the journey map feeds the
  // delivery/execution/appoval statuses through this badge, and
  // awaiting_approval was missing from both maps (raw fallback + warn).
  it('renders the awaiting_approval status with the warn chip', () => {
    render(<StatusBadge status="awaiting_approval" />);
    const badge = screen.getByText('Awaiting Approval');
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain('bg-pixel-led-amber');
    expect(badge.className).toContain('border-[#191a26]');
  });
});
