import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RouterForTesting } from '../../../test-utils';
import ActivityBar, { type ActivityEntry } from '../ActivityBar';

const now = Date.parse('2026-10-01T12:00:00Z');

function entry(minutesAgo: number, action: string): ActivityEntry {
  return {
    action,
    resource_id: `a1000001-0000-4000-8000-00000000000${minutesAgo}`,
    created_at: new Date(now - minutesAgo * 60_000).toISOString(),
  };
}

function renderBar(activity?: ActivityEntry[]) {
  return render(
    <RouterForTesting>
      <ActivityBar activity={activity} />
    </RouterForTesting>,
  );
}

describe('ActivityBar', () => {
  it('renders the newest three entries', () => {
    renderBar([
      entry(5, 'dashboard.agent.update'),
      entry(10, 'dashboard.agent.rotate_token'),
      entry(20, 'dashboard.agent.create'),
      entry(40, 'dashboard.agent.update'),
      entry(80, 'dashboard.agent.update'),
    ]);
    // Newest first: exactly three rows.
    expect(screen.getAllByRole('listitem').length).toBe(3);
    expect(screen.getByText('dashboard.agent.update')).toBeInTheDocument();
    expect(screen.getByText('dashboard.agent.rotate_token')).toBeInTheDocument();
    expect(screen.getByText('dashboard.agent.create')).toBeInTheDocument();
    // The oldest fixture is cut off by the slice.
    expect(screen.queryByText('dashboard.agent.firewall')).toBeNull();
  });

  it('renders the view-all entry pointing at the agents page', () => {
    renderBar([entry(5, 'dashboard.agent.create')]);
    expect(screen.getByRole('link', { name: 'View all agents' })).toHaveAttribute(
      'href',
      '/app/agents',
    );
  });

  // The empty state copy explains the narrow audit scope (only actions
  // performed BY the user's own agents) instead of reading like an error.
  it('renders the scope-explaining empty state when the audit slice is empty', () => {
    renderBar([]);
    expect(
      screen.getByText(/This list only carries audit events performed by your own agents/),
    ).toBeInTheDocument();
  });

  it('renders the empty state while the query has not arrived', () => {
    renderBar(undefined);
    expect(
      screen.getByText(/This list only carries audit events performed by your own agents/),
    ).toBeInTheDocument();
  });

  // Timestamps are short and locale formatted (no stacked raw ISO strings).
  it('renders short localized timestamps, never raw ISO strings', () => {
    const { container } = renderBar([entry(5, 'dashboard.agent.create')]);
    const time = container.querySelector('time');
    expect(time).not.toBeNull();
    expect(time!.textContent).toMatch(/\d{1,2}\/\d{1,2}/);
    expect(time!.textContent).not.toContain('T');
  });
});
