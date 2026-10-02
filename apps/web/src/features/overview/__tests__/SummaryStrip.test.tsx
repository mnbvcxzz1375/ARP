import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import SummaryStrip from '../SummaryStrip';

describe('SummaryStrip', () => {
  it('renders all five counts with their labels', () => {
    render(
      <SummaryStrip
        data={{
          online_agents: 3,
          tasks_today: 12,
          failed_tasks: 1,
          pending_approvals: 2,
          pending_messages: 5,
        }}
      />,
    );
    expect(screen.getByText('Online Agents')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('Tasks Today')).toBeInTheDocument();
    expect(screen.getByText('Pending Approvals')).toBeInTheDocument();
    expect(screen.getByText('Pending Messages')).toBeInTheDocument();
  });

  // The failed count is a text chip on the LED-red palette (tokens.ts),
  // so the danger state never relies on color alone.
  it('renders the failed count on the LED-red chip', () => {
    render(<SummaryStrip data={{ failed_tasks: 4 }} />);
    const chip = screen.getByText('4');
    expect(chip.className).toContain('bg-pixel-led-red');
    expect(screen.getByText('Failed Tasks')).toBeInTheDocument();
  });

  it('shows zeros while the query has not arrived', () => {
    render(<SummaryStrip data={null} />);
    // Five counters, all zero (the failed count is the chip).
    expect(screen.getAllByText('0').length).toBe(5);
  });

  // Per-feed degradation: a failed overview feed (403 / network) swaps
  // the counts for a gap sentence — no partial or invented numbers.
  it('replaces the counts with a gap sentence when the feed failed', () => {
    render(<SummaryStrip data={null} isError />);
    expect(screen.getByText('Overview summary unavailable (permission or network).')).toBeInTheDocument();
    expect(screen.queryByText('Online Agents')).toBeNull();
  });

  // Persistent lag note: overview is a 15s-TTL Redis snapshot polled every
  // 15s, so the strip must stay honest about ~30s staleness in every state.
  it('always renders the lag note', () => {
    const { rerender } = render(<SummaryStrip data={null} />);
    expect(screen.getByText(/Refreshes about every/)).toBeInTheDocument();
    rerender(<SummaryStrip data={{ online_agents: 9, failed_tasks: 2 }} isError />);
    expect(screen.getByText(/Refreshes about every/)).toBeInTheDocument();
  });
});
