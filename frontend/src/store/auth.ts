/**
 * Persisted ESXi session store.
 *
 * Backed by localStorage (via zustand `persist` middleware). The token,
 * connected host, and vCenter API version survive a page reload; credentials
 * are never stored. The backend's session store is in-process, so a backend
 * restart will invalidate the token — `api.ts` auto-clears this store on 401.
 *
 * No React provider is needed; import `useAuthStore` directly in any component.
 * Keep this module free of `api.ts` imports to avoid circular dependencies.
 */

import { create } from "zustand"
import { persist } from "zustand/middleware"

import { STORAGE_KEYS } from "@/constants"

interface Session {
  token: string
  host: string
  apiVersion: string
}

interface AuthState {
  token?: string
  host?: string
  apiVersion?: string
  setSession: (s: Session) => void
  clear: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      setSession: ({ token, host, apiVersion }) =>
        set({ token, host, apiVersion }),
      clear: () =>
        set({ token: undefined, host: undefined, apiVersion: undefined }),
    }),
    { name: STORAGE_KEYS.auth },
  ),
)
