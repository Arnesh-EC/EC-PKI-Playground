/**
 * Bridges the ephemeral topology store to the persisted projects store.
 *
 * The only module that imports both `store/topology.ts` and `store/projects.ts`
 * — keeps the two stores decoupled from each other. Subscribes to topology
 * changes and decides, per change, whether it's just an in-progress edit
 * (mark the active project dirty, cheap, in-memory) or a checkpoint worth
 * writing to localStorage (a node finished configuring, or domain membership
 * changed). Plain drags/drops of `unconfigured` nodes only mark dirty.
 */

import { EDGE_TYPE, NODE_STATUS } from "@/constants/topology"
import { useTopologyStore } from "@/store/topology"
import { useProjectsStore } from "@/store/projects"

let suppressed = false

/** Runs `fn` (a topology mutation, e.g. loadSnapshot) without it being read as a dirty edit or checkpoint. */
export function withSuppressedAutosave(fn: () => void) {
  suppressed = true
  try {
    fn()
  } finally {
    suppressed = false
  }
}

function isTerminal(status: string) {
  return status === NODE_STATUS.configured || status === NODE_STATUS.error
}

function domainJoinEdgeIds(edges: ReturnType<typeof useTopologyStore.getState>["edges"]) {
  return new Set(
    edges.filter((e) => e.data?.edgeType === EDGE_TYPE.domainJoin).map((e) => e.id),
  )
}

let initialized = false

export function initProjectAutosave() {
  if (initialized) return
  initialized = true

  useTopologyStore.subscribe((state, prev) => {
    if (suppressed) return
    if (state.nodes === prev.nodes && state.edges === prev.edges && state.counters === prev.counters) {
      return
    }

    const prevStatusById = new Map(prev.nodes.map((n) => [n.id, n.data.status]))
    const justFinished = state.nodes.some((n) => {
      const prevStatus = prevStatusById.get(n.id)
      return prevStatus !== n.data.status && isTerminal(n.data.status)
    })

    const domainChanged =
      state.edges !== prev.edges &&
      !setsEqual(domainJoinEdgeIds(state.edges), domainJoinEdgeIds(prev.edges))

    if (justFinished || domainChanged) {
      useProjectsStore.getState().saveActiveSnapshot()
    } else {
      useProjectsStore.getState().markActiveDirty()
    }
  })
}

function setsEqual(a: Set<string>, b: Set<string>) {
  if (a.size !== b.size) return false
  for (const id of a) if (!b.has(id)) return false
  return true
}
