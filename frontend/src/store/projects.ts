/**
 * Persisted project store.
 *
 * A "project" is a named, saved snapshot of a topology graph (nodes/edges/
 * counters). Backed by localStorage (via zustand `persist`), same pattern as
 * `auth.ts`/`theme.ts`. This is the seam called out in `topology.ts`: the
 * working graph there stays ephemeral/in-memory, and this store is what
 * actually persists it, one snapshot per project. Swapping localStorage for a
 * backend endpoint later only touches this file.
 *
 * Snapshot writes are checkpointed (see `lib/projectAutosave.ts`) rather than
 * happening on every topology mutation, so dragging/dropping nodes around
 * doesn't spam localStorage. `markActiveDirty` is intentionally idempotent
 * (no-ops once already dirty) for the same reason.
 */

import { create } from "zustand"
import { persist } from "zustand/middleware"
import type { Edge, Node } from "@xyflow/react"

import type { Viewport } from "@xyflow/react"

import { STORAGE_KEYS } from "@/constants"
import type { MachineData } from "@/store/topology"
import { DEFAULT_VIEWPORT, useTopologyStore } from "@/store/topology"
import { withSuppressedAutosave } from "@/lib/projectAutosave"

export interface Project {
  id: string
  name: string
  nodes: Node<MachineData>[]
  edges: Edge[]
  counters: Record<string, number>
  /** Camera pan/zoom, restored when this project's tab is reopened. */
  viewport: Viewport
  dirty: boolean
  updatedAt: number
}

function emptyProject(name: string): Project {
  return {
    id: crypto.randomUUID(),
    name,
    nodes: [],
    edges: [],
    counters: {},
    viewport: DEFAULT_VIEWPORT,
    dirty: false,
    updatedAt: Date.now(),
  }
}

interface ProjectsState {
  projects: Project[]
  activeProjectId: string | null
  nextProjectNumber: number

  ensureDefaultProject: () => void
  addProject: () => void
  renameProject: (id: string, name: string) => void
  switchProject: (id: string) => void
  markActiveDirty: () => void
  saveActiveSnapshot: () => void
  persistActiveDraft: () => void
}

export const useProjectsStore = create<ProjectsState>()(
  persist(
    (set, get) => ({
      projects: [],
      activeProjectId: null,
      nextProjectNumber: 1,

      ensureDefaultProject() {
        const { projects } = get()
        if (projects.length > 0) {
          const active =
            projects.find((p) => p.id === get().activeProjectId) ?? projects[0]
          withSuppressedAutosave(() =>
            useTopologyStore
              .getState()
              .loadSnapshot(
                active.nodes,
                active.edges,
                active.counters,
                active.viewport ?? DEFAULT_VIEWPORT,
              ),
          )
          if (!get().activeProjectId) set({ activeProjectId: projects[0].id })
          return
        }
        const project = emptyProject("Project 1")
        set({ projects: [project], activeProjectId: project.id, nextProjectNumber: 2 })
        withSuppressedAutosave(() =>
          useTopologyStore.getState().loadSnapshot([], [], {}, DEFAULT_VIEWPORT),
        )
      },

      addProject() {
        get().persistActiveDraft()
        const n = get().nextProjectNumber
        const project = emptyProject(`Project ${n}`)
        set((s) => ({
          projects: [...s.projects, project],
          activeProjectId: project.id,
          nextProjectNumber: n + 1,
        }))
        withSuppressedAutosave(() =>
          useTopologyStore.getState().loadSnapshot([], [], {}, DEFAULT_VIEWPORT),
        )
      },

      renameProject(id, name) {
        const trimmed = name.trim()
        if (!trimmed) return
        set((s) => ({
          projects: s.projects.map((p) =>
            p.id === id ? { ...p, name: trimmed } : p,
          ),
        }))
      },

      switchProject(id) {
        if (get().activeProjectId === id) return
        get().persistActiveDraft()
        const target = get().projects.find((p) => p.id === id)
        if (!target) return
        set({ activeProjectId: id })
        withSuppressedAutosave(() =>
          useTopologyStore
            .getState()
            .loadSnapshot(
              target.nodes,
              target.edges,
              target.counters,
              target.viewport ?? DEFAULT_VIEWPORT,
            ),
        )
      },

      markActiveDirty() {
        const { activeProjectId, projects } = get()
        const active = projects.find((p) => p.id === activeProjectId)
        if (!active || active.dirty) return
        set((s) => ({
          projects: s.projects.map((p) =>
            p.id === activeProjectId ? { ...p, dirty: true } : p,
          ),
        }))
      },

      saveActiveSnapshot() {
        const { activeProjectId } = get()
        if (!activeProjectId) return
        const { nodes, edges, counters, viewport } = useTopologyStore.getState()
        set((s) => ({
          projects: s.projects.map((p) =>
            p.id === activeProjectId
              ? { ...p, nodes, edges, counters, viewport, dirty: false, updatedAt: Date.now() }
              : p,
          ),
        }))
      },

      persistActiveDraft() {
        const { activeProjectId } = get()
        if (!activeProjectId) return
        const { nodes, edges, counters, viewport } = useTopologyStore.getState()
        set((s) => ({
          projects: s.projects.map((p) =>
            p.id === activeProjectId ? { ...p, nodes, edges, counters, viewport } : p,
          ),
        }))
      },
    }),
    { name: STORAGE_KEYS.projects },
  ),
)
