import { useQuery } from "@tanstack/react-query"
import { getHealth } from "@/lib/api"
import { QUERY_KEYS } from "@/constants"
import { Badge } from "@/components/ui/badge"

/** Live backend reachability indicator, polled via TanStack Query. */
export function HealthBadge() {
  const { data, isLoading, isError } = useQuery({
    queryKey: QUERY_KEYS.health,
    queryFn: getHealth,
    refetchInterval: 15_000,
  })

  if (isLoading) return <Badge variant="secondary">API: checking…</Badge>
  if (isError || data?.status !== "ok")
    return <Badge variant="destructive">API: unreachable</Badge>

  const libs = Object.keys(data.libraries).join(", ")
  return (
    <Badge className="bg-emerald-600 text-white" title={`libraries: ${libs}`}>
      API: ok
    </Badge>
  )
}
