import { ReactFlowProvider } from "@xyflow/react"
import { Canvas } from "./Canvas"
import { Inspector } from "./Inspector"
import { ProjectTabBar } from "./ProjectTabBar"
import { Toolbox } from "./Toolbox"

/**
 * Full-height authenticated workspace: Toolbox | (tab bar above Canvas | Inspector)
 * The toolbox is shared across all projects, so the project tab bar starts
 * after it rather than spanning the full width.
 * Rendered by App.tsx in the authenticated shell; auth gating is upstream.
 */
export function Workspace() {
  return (
    <ReactFlowProvider>
      <div className="flex flex-1 overflow-hidden">
        <Toolbox />
        <div className="flex flex-1 flex-col overflow-hidden">
          <ProjectTabBar />
          <div className="flex flex-1 overflow-hidden">
            <Canvas />
            <Inspector />
          </div>
        </div>
      </div>
    </ReactFlowProvider>
  )
}
