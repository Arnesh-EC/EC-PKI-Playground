import { useEffect } from "react"

import { useProjectsStore } from "@/store/projects"

/** Warns on browser navigate-away/close while any project has unsaved changes. */
export function useBeforeUnloadWarning() {
  const hasDirty = useProjectsStore((s) => s.projects.some((p) => p.dirty))

  useEffect(() => {
    if (!hasDirty) return
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ""
    }
    window.addEventListener("beforeunload", handler)
    return () => window.removeEventListener("beforeunload", handler)
  }, [hasDirty])
}
