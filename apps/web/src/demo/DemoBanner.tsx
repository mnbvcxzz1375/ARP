import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { RotateCcw } from 'lucide-react';
import { useT } from '../i18n';
import { DEMO_PERSONAS, getDemoStore, resetDemoWorld, setDemoSession, type PersonaId } from './index';

/**
 * Demo mode banner: amber chip + persona switcher + reset control.
 *
 * Mounted only in VITE_DEMO_MODE builds (DashboardShell gates it), so the
 * component can rely on the demo store existing. The persona switch swaps
 * the session identity (the same ['auth/me'] response shape a real login
 * produces), resets the fixture world, and resets every react-query so
 * pages re-fetch and guards re-evaluate under the new permissions.
 */
export default function DemoBanner() {
  const t = useT();
  const qc = useQueryClient();
  const store = getDemoStore();
  const [personaId, setPersonaId] = useState<PersonaId>(store.personaId);

  const switchPersona = (id: PersonaId) => {
    resetDemoWorld();
    setDemoSession({ personaId: id });
    setPersonaId(id);
    // Re-run the auth probe and every page query under the new identity;
    // resetQueries also refetches active queries immediately.
    qc.resetQueries();
  };

  const handleReset = () => {
    resetDemoWorld();
    qc.resetQueries();
  };

  return (
    <div
      data-testid="demo-banner"
      className="flex flex-wrap items-center gap-3 border-b-2 border-pixel-line bg-pixel-raised px-4 py-2"
    >
      <span className="pixel-led pixel-led-amber" aria-hidden="true" />
      <span className="font-pixel text-pixel-sm uppercase tracking-wide text-pixel-fg">
        {t('shell.demo.badge')}
      </span>
      <span className="font-body text-base text-pixel-muted">{t('shell.demo.banner')}</span>

      <label className="ml-auto flex items-center gap-2 font-pixel text-pixel-sm text-pixel-muted">
        {t('shell.demo.persona.label')}
        <select
          data-testid="demo-persona-select"
          value={personaId}
          onChange={(e) => switchPersona(e.target.value as PersonaId)}
          className="border-2 border-pixel-line bg-pixel-bg px-2 py-1 font-pixel text-pixel-sm text-pixel-fg focus:border-pixel-accent-2 focus:outline-none"
        >
          {DEMO_PERSONAS.map((p) => (
            <option key={p.id} value={p.id}>
              {t(`shell.demo.persona.${p.id}`)}
            </option>
          ))}
        </select>
      </label>

      <button
        type="button"
        data-testid="demo-reset"
        onClick={handleReset}
        aria-label={t('shell.demo.reset.aria')}
        title={t('shell.demo.reset')}
        className="flex min-h-[36px] items-center gap-2 border-2 border-pixel-line bg-pixel-bg px-3 py-1 font-pixel text-pixel-sm text-pixel-fg hover:bg-pixel-accent hover:text-[#191a26]"
      >
        <RotateCcw size={14} strokeWidth={2} aria-hidden="true" />
        {t('shell.demo.reset')}
      </button>
    </div>
  );
}
