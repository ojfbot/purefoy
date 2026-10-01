// Endpoint defaults. Loopback only in dev — a production bundle must never
// reach for localhost (it triggers the browser's Local Network Access prompt
// for every visitor). Empty means "not configured": callers don't fetch.

// Production sets VITE_API_URL on the Vercel project (→ https://tde.jim.software).
export const API_BASE: string =
  import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://localhost:3021' : '')

export const FRAME_AGENT_URL: string =
  import.meta.env.VITE_FRAME_AGENT_URL ?? (import.meta.env.DEV ? 'http://localhost:4001' : '')
