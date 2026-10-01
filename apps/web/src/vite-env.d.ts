/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Offline demo mode: the api client routes to the in-memory fixture world. */
  readonly VITE_DEMO_MODE?: string;
  /** Backend base URL (same-origin by default). */
  readonly VITE_AGENTNET_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
