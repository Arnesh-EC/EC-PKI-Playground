import { useAuthStore } from "@/store/auth"
import { HealthBadge } from "@/components/HealthBadge"
import { HostnameForm } from "@/components/HostnameForm"
import { LoginForm } from "@/components/LoginForm"
import { LogoutButton } from "@/components/LogoutButton"

function App() {
  const token = useAuthStore((s) => s.token)
  const host = useAuthStore((s) => s.host)

  if (!token) return <LoginForm />

  return (
    <div className="mx-auto min-h-svh max-w-3xl px-6 py-10">
      <header className="mb-8 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">EC-PKI-Lab</h1>
          <p className="text-sm text-muted-foreground">
            Web console over the vmkit / configgen / isokit deployment API.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          {host && (
            <span className="hidden text-sm text-muted-foreground sm:block">
              {host}
            </span>
          )}
          <HealthBadge />
          <LogoutButton />
        </div>
      </header>

      <main className="space-y-6">
        <HostnameForm />
      </main>
    </div>
  )
}

export default App
