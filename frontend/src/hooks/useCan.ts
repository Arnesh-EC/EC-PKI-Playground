/**
 * Returns true if the current deploy's role has the given capability.
 *
 * The capability list is fetched from GET /auth/mode (cached by TanStack Query)
 * and is single-sourced from the backend — add/remove capabilities in
 * core/authz.py and both the server enforcement and this hook update together.
 *
 * This hook is COSMETIC: it hides UI that the current role cannot use.
 * The backend enforces the allowlist authoritatively; a guest with a valid token
 * calling an operator-only route still gets 403 regardless of what the UI shows.
 *
 * Usage:
 *   const canUpdate = useCan(CAPABILITIES.vmUpdate)
 *   if (canUpdate) return <UpdateForm />
 */

import { useQuery } from "@tanstack/react-query"
import { QUERY_KEYS, type Capability } from "@/constants"
import { getMode } from "@/lib/api"

export function useCan(cap: Capability): boolean {
  const { data } = useQuery({ queryKey: QUERY_KEYS.mode, queryFn: getMode })
  return !!data?.capabilities.includes(cap)
}
