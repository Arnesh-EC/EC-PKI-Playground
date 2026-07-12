import { useEffect, useRef } from "react"
import { CAPABILITIES, ROLES } from "@/constants"
import { useAuthStore } from "@/store/auth"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { HealthBadge } from "@/components/HealthBadge"
import { LoginForm } from "@/components/LoginForm"
import { LogoutButton } from "@/components/LogoutButton"
import { Splash } from "@/components/Splash"
import { SettingsDialog } from "@/components/SettingsDialog"
import { ThemeToggle } from "@/components/ThemeToggle"
import { Workspace } from "@/components/canvas/Workspace"
import { useApplyTheme } from "@/hooks/useTheme"
import { useBeforeUnloadWarning } from "@/hooks/useBeforeUnloadWarning"
import { useMe } from "@/hooks/useMe"
import { initProjectAutosave } from "@/lib/projectAutosave"
import {
  initServerProjects,
  retryInitServerProjects,
  useProjectSyncStore,
} from "@/lib/projectSync"
import { useProjectsStore } from "@/store/projects"

function App() {
  // Apply the resolved theme to <html> on every render. Must be called before
  // any early returns so theme applies to the splash / login screens too.
  useApplyTheme()

  useBeforeUnloadWarning()

  // Login is always required — no anonymous mode. Without a session token the
  // first (and only) screen is the login form; both operators and guests sign
  // in with an account (guests via username/password only).
  const token = useAuthStore((s) => s.token)
  const sessionReady = !!token

  // Once a session exists, load the active project's topology (or bootstrap a
  // default one) and start the autosave bridge. Runs once per session.
  //
  // Operator roles carry the project:* capabilities → projects live on the
  // server (lib/projectSync.ts). Guests keep localStorage persistence.
  // Capabilities are per-user (GET /auth/me), so wait for that query before
  // choosing a persistence mode — `me` is undefined until it lands.
  const me = useMe()
  const canProjects = !!me?.capabilities.includes(CAPABILITIES.projectRead)
  const syncStatus = useProjectSyncStore((s) => s.status)
  const syncError = useProjectSyncStore((s) => s.loadError)
  const didInitProjects = useRef(false)
  useEffect(() => {
    if (!sessionReady || !me || didInitProjects.current) return
    didInitProjects.current = true
    initProjectAutosave()
    if (canProjects) void initServerProjects()
    else useProjectsStore.getState().ensureDefaultProject()
  }, [sessionReady, me, canProjects])

  if (!token) return <LoginForm />

  // Capabilities (GET /auth/me) decide the persistence mode below; rendering
  // the workspace before they land would flash the wrong mode for operators.
  if (!me) return <Splash label="Loading session…" />

  // Server-persistence gate (operator only): the canvas can't render until the
  // project list is hydrated from the backend. No silent localStorage fallback
  // on error — serving stale local data while the server is the record invites
  // divergence.
  if (canProjects && syncStatus !== "ready") {
    if (syncStatus === "error") {
      return (
        <div className="flex h-svh flex-col items-center justify-center gap-3">
          <p className="text-sm text-muted-foreground">
            Couldn&apos;t load projects from the server{syncError ? `: ${syncError}` : "."}
          </p>
          <Button variant="outline" onClick={() => retryInitServerProjects()}>
            Retry
          </Button>
        </div>
      )
    }
    return <Splash label="Loading projects…" />
  }

  const isGuest = me.role === ROLES.guest

  return (
    <div className="flex h-svh flex-col overflow-hidden">
      {/* Top bar */}
      <header className="flex shrink-0 items-center justify-between gap-4 border-b px-4 py-2">
        <div>
          <h1 className="text-base font-semibold tracking-tight">EC PKI Playground</h1>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <HealthBadge />
          {isGuest && <Badge variant="secondary">Guest</Badge>}
          <LogoutButton />
          <SettingsDialog />
          <ThemeToggle />
        </div>
      </header>

      {/* Canvas workspace — takes the remaining viewport height */}
      <Workspace />
    </div>
  )
}

export default App
