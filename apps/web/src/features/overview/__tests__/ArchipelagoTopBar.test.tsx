import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RouterForTesting } from '../../../test-utils';
import ArchipelagoTopBar from '../ArchipelagoTopBar';

function renderBar(viewMode: 'map' | 'list' = 'map') {
  const onViewModeChange = vi.fn();
  render(
    <RouterForTesting>
      <ArchipelagoTopBar viewMode={viewMode} onViewModeChange={onViewModeChange} />
    </RouterForTesting>,
  );
  return { onViewModeChange };
}

describe('ArchipelagoTopBar', () => {
  it('renders the brand block', () => {
    renderBar();
    expect(screen.getByText('AgentNet')).toBeInTheDocument();
    expect(screen.getByText('Relay Archipelago')).toBeInTheDocument();
  });

  it('marks the active view mode with aria-pressed', () => {
    renderBar('map');
    expect(screen.getByRole('button', { name: 'Map' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'List' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('switches to list mode on click', async () => {
    const user = userEvent.setup();
    const { onViewModeChange } = renderBar();
    await user.click(screen.getByRole('button', { name: 'List' }));
    expect(onViewModeChange).toHaveBeenCalledWith('list');
  });

  // The create-task entry is a capability GAP: no console entry exists,
  // so it links to the docs quickstart (same pattern as EmptyState).
  it('points the create-task entry at the docs quickstart', () => {
    renderBar();
    const link = screen.getByRole('link', { name: /Task guide/ });
    expect(link).toHaveAttribute('href', '/docs/quickstart');
  });

  it('links the account entry at the settings page', () => {
    renderBar();
    expect(screen.getByRole('link', { name: 'Account' })).toHaveAttribute('href', '/app/settings');
  });
});
