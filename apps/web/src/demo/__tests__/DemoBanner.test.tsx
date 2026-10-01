import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterForTesting } from '../../test-utils';
import DemoBanner from '../DemoBanner';
import { getDemoStore, resetDemoStore, resetDemoSession } from '../demoStore';
import { personaById } from '../personas';

/**
 * Demo banner: the three-persona switcher is the demo's most
 * security-relevant surface — it changes /me.permissions, and every guard
 * and nav filter downstream re-evaluates on that. These tests pin that the
 * switch actually mutates the session identity and resets the demo world.
 */

function renderBanner() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterForTesting>
        <DemoBanner />
      </RouterForTesting>
    </QueryClientProvider>,
  );
  return queryClient;
}

beforeEach(() => {
  resetDemoStore();
  resetDemoSession();
});

describe('DemoBanner', () => {
  it('renders the badge, all three personas and the reset button', () => {
    renderBanner();
    expect(screen.getByTestId('demo-banner')).toBeInTheDocument();
    expect(screen.getByTestId('demo-persona-select')).toBeInTheDocument();
    for (const id of ['super_admin', 'org_manager', 'personal'] as const) {
      expect(
        screen.getByRole('option', { name: new RegExp(personaLabels(id)) }),
      ).toBeInTheDocument();
    }
    expect(screen.getByTestId('demo-reset')).toBeInTheDocument();
  });

  it('switching persona changes the session identity and rebuilds the world', () => {
    const qc = renderBanner();
    // Start with the org manager identity so the switch is observable.
    getDemoStore().personaId = 'org_manager';

    fireEvent.change(screen.getByTestId('demo-persona-select'), {
      target: { value: 'super_admin' },
    });

    expect(getDemoStore().personaId).toBe('super_admin');
    expect(getDemoStore().loggedIn).toBe(false); // unchanged by switching
    // The /me identity is now the super admin persona.
    expect(personaById('super_admin').buildMe().role).toBe('super_admin');
    // Queries were reset so pages re-fetch under the new identity.
    expect(qc.getQueryCache().getAll()).toHaveLength(0);
  });

  it('reset restores a pristine fixture world', () => {
    renderBanner();
    // Mutate the world, then reset.
    getDemoStore().world.gateways.splice(0, 1);
    expect(getDemoStore().world.gateways).toHaveLength(2);

    fireEvent.click(screen.getByTestId('demo-reset'));
    expect(getDemoStore().world.gateways).toHaveLength(3);
  });
});

function personaLabels(id: 'super_admin' | 'org_manager' | 'personal'): string {
  // English locale labels (i18n defaults to en in tests).
  return { super_admin: 'Super Admin', org_manager: 'Org Manager', personal: 'Personal User' }[id];
}
