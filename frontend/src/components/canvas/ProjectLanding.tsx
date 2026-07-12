import { FilePlus2, Network } from "lucide-react"

import { cn } from "@/lib/utils"
import { useProjectsStore } from "@/store/projects"

/**
 * Shown by the Workspace when there are no projects (i.e. the last one was
 * deleted). Offers the two ways to start a new project — a clean workspace or
 * the pre-configured PKI lab template.
 */
export function ProjectLanding() {
  const addProject = useProjectsStore((s) => s.addProject)
  const addProjectFromTemplate = useProjectsStore((s) => s.addProjectFromTemplate)

  return (
    <div className="flex flex-1 items-center justify-center overflow-y-auto bg-muted/20 p-6">
      <div className="flex w-full max-w-2xl flex-col items-center gap-8">
        <div className="flex flex-col items-center gap-1.5 text-center">
          <h2 className="text-xl font-semibold tracking-tight">
            How do you wish to start?
          </h2>
          <p className="text-sm text-muted-foreground">
            Create a project to begin composing your topology.
          </p>
        </div>

        <div className="grid w-full grid-cols-1 gap-4 sm:grid-cols-2">
          <StartCard
            icon={FilePlus2}
            accent="text-sky-500"
            title="Empty Project"
            subtitle="Clean new workspace"
            onClick={() => addProject()}
          />
          <StartCard
            icon={Network}
            accent="text-amber-500"
            title="Project Template"
            subtitle="Pre-configured PKI"
            onClick={() => addProjectFromTemplate()}
          />
        </div>
      </div>
    </div>
  )
}

function StartCard({
  icon: Icon,
  accent,
  title,
  subtitle,
  onClick,
}: {
  icon: React.ElementType
  accent: string
  title: string
  subtitle: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "group flex flex-col items-start gap-3 rounded-xl border bg-card p-5 text-left",
        "shadow-sm ring-1 ring-foreground/5 transition-all outline-none",
        "hover:border-primary/40 hover:shadow-md hover:-translate-y-0.5",
        "focus-visible:ring-3 focus-visible:ring-ring/50",
      )}
    >
      <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted/60">
        <Icon className={cn("h-5 w-5", accent)} />
      </span>
      <span className="flex flex-col gap-0.5">
        <span className="text-sm font-semibold">{title}</span>
        <span className="text-xs text-muted-foreground">{subtitle}</span>
      </span>
    </button>
  )
}
