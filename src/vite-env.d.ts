/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Path of the API, same origin as the app. Defaults to '/api'. */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
