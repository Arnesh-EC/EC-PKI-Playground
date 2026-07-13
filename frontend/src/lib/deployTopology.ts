/** Convert the React Flow canvas into the backend's versioned semantic graph. */

import type { Edge, Node } from "@xyflow/react"

import { EDGE_TYPE } from "@/constants/topology"
import type { TopologyPayload, TopologyRole } from "@/lib/api"
import type { MachineData } from "@/store/topology"

function topologyRole(data: MachineData): TopologyRole {
  switch (data.typeId) {
    case "domainController":
      return "domainController"
    case "certificateAuthority":
      return data.config?.caType === "Issuing" ? "issuingCa" : "rootCa"
    case "webServer":
      return "webServer"
    case "client":
      return "client"
    default:
      return "standalone"
  }
}

export function buildDeployTopology(
  nodes: Node<MachineData>[],
  edges: Edge[],
): TopologyPayload {
  return {
    version: 1,
    nodes: nodes.map((node) => ({
      id: node.id,
      name: node.data.name,
      role: topologyRole(node.data),
      config: node.data.config ?? {},
    })),
    edges: edges.flatMap((edge) => {
      const edgeType = edge.data?.edgeType
      const kind =
        edgeType === EDGE_TYPE.domainJoin
          ? "domainMembership"
          : edgeType === EDGE_TYPE.caHierarchy
            ? "caParent"
            : edgeType === EDGE_TYPE.webServerCert
              ? "caPublication"
              : null
      return kind
        ? [{ id: edge.id, kind, source: edge.source, target: edge.target }]
        : []
    }),
  }
}
