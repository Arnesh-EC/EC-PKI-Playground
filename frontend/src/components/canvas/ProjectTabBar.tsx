import { useEffect, useState } from "react"
import { Plus, Save } from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useProjectsStore } from "@/store/projects"

export function ProjectTabBar() {
  const projects = useProjectsStore((s) => s.projects)
  const activeProjectId = useProjectsStore((s) => s.activeProjectId)
  const switchProject = useProjectsStore((s) => s.switchProject)
  const renameProject = useProjectsStore((s) => s.renameProject)
  const addProject = useProjectsStore((s) => s.addProject)
  const saveActiveSnapshot = useProjectsStore((s) => s.saveActiveSnapshot)
  const isActiveDirty =
    projects.find((p) => p.id === activeProjectId)?.dirty ?? false

  const [editingId, setEditingId] = useState<string | null>(null)
  const [draftName, setDraftName] = useState("")

  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault()
        saveActiveSnapshot()
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [saveActiveSnapshot])

  function startEditing(id: string, name: string) {
    setEditingId(id)
    setDraftName(name)
  }

  function commitEditing() {
    if (editingId) renameProject(editingId, draftName)
    setEditingId(null)
  }

  return (
    <div className="flex shrink-0 items-center gap-1 border-b bg-muted/30 px-2 py-1">
      {projects.map((project) => {
        const isActive = project.id === activeProjectId
        const isEditing = editingId === project.id

        if (isEditing) {
          return (
            <Input
              key={project.id}
              autoFocus
              value={draftName}
              onChange={(e) => setDraftName(e.target.value)}
              onBlur={commitEditing}
              onKeyDown={(e) => {
                if (e.key === "Enter") commitEditing()
                if (e.key === "Escape") setEditingId(null)
              }}
              className="h-7 w-32 text-xs"
            />
          )
        }

        return (
          <button
            key={project.id}
            type="button"
            onClick={() => switchProject(project.id)}
            onDoubleClick={() => startEditing(project.id, project.name)}
            className={cn(
              "h-7 rounded-[min(var(--radius-md),12px)] px-2.5 text-xs font-medium whitespace-nowrap transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
              isActive
                ? "bg-secondary text-secondary-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            {project.name}
            {project.dirty && (
              <span className="ml-1 text-muted-foreground" aria-label="Unsaved changes">
                *
              </span>
            )}
          </button>
        )
      })}

      <Button
        variant="ghost"
        size="icon-sm"
        onClick={() => addProject()}
        aria-label="New project"
      >
        <Plus />
      </Button>

      <Button
        variant="ghost"
        size="icon-sm"
        className="ml-auto"
        disabled={!isActiveDirty}
        onClick={() => saveActiveSnapshot()}
        aria-label="Save project (Ctrl+S)"
        title="Save project (Ctrl+S)"
      >
        <Save />
      </Button>
    </div>
  )
}
