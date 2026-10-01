/**
 * Demo mode entry: build-time switch + the axios adapter export.
 *
 * `VITE_DEMO_MODE` must be a build-time env var ("1" or "true"); when off,
 * the app builds exactly as before — the demo module is dead code that
 * tree-shakes out of the production bundle.
 */
export function isDemoMode(): boolean {
  const v = import.meta.env.VITE_DEMO_MODE;
  return v === '1' || v === 'true';
}

export { demoApi, demoAxiosAdapter, resetDemoWorld } from './demoAdapter';
export { getDemoStore, resetDemoStore, resetDemoSession, setDemoSession } from './demoStore';
export { DEMO_PERSONAS, personaById, type PersonaId, type DemoPersona } from './personas';
export { default as DemoBanner } from './DemoBanner';
