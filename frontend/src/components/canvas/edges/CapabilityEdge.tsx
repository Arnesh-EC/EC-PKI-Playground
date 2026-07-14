import { useState } from "react"
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  getSmoothStepPath,
  type EdgeProps,
} from "@xyflow/react"

import { EDGE_TYPE } from "@/constants/topology"
import type { EdgeType } from "@/constants/topology"
import {
  CONNECTION_PORT_GUIDANCE,
  connectionGuidance,
} from "@/lib/topology"
import { cn } from "@/lib/utils"

export function CapabilityEdge(props: EdgeProps) {
  const [hovered, setHovered] = useState(false)
  const edgeType = props.data?.edgeType as EdgeType | undefined
  if (!edgeType) return null

  const guidance = connectionGuidance(edgeType, {
    rootIssuer: props.data?.rootIssuer === true,
  })
  const [path, labelX, labelY] =
    edgeType === EDGE_TYPE.webServerCert
      ? getBezierPath(props)
      : getSmoothStepPath(props)
  const expanded = hovered || props.selected

  return (
    <>
      <BaseEdge
        id={props.id}
        path={path}
        markerEnd={props.markerEnd}
        style={props.style}
      />
      <EdgeLabelRenderer>
        <div
          className="nodrag nopan absolute z-10"
          style={{
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
          }}
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
        >
          <button
            type="button"
            aria-expanded={expanded}
            aria-label={`${guidance.intent}. Show connection requirements.`}
            onFocus={() => setHovered(true)}
            onBlur={() => setHovered(false)}
            className={cn(
              "max-w-52 rounded-full border bg-background/95 px-2 py-1 text-[10px] font-semibold shadow-sm",
              "transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              props.selected && "ring-2 ring-ring",
            )}
          >
            {guidance.intent}
          </button>

          {expanded && (
            <div className="absolute left-1/2 top-full mt-2 w-80 -translate-x-1/2 rounded-lg border bg-popover p-3 text-popover-foreground shadow-xl">
              <p className="text-[11px] font-semibold">Capabilities</p>
              <div className="mt-1.5 space-y-1.5">
                {guidance.ports.map((port) => {
                  const item = CONNECTION_PORT_GUIDANCE[port]
                  return (
                    <div key={port} className="text-[10px] leading-snug">
                      <span className="font-medium">{item.label}:</span>{" "}
                      <span className="text-muted-foreground">
                        {item.capabilities.join(" · ")}
                      </span>
                    </div>
                  )
                })}
              </div>

              <p className="mt-3 text-[11px] font-semibold">Requirements</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[10px] text-muted-foreground">
                {guidance.requirements.map((requirement) => (
                  <li key={requirement}>{requirement}</li>
                ))}
              </ul>

              <p className="mt-3 text-[11px] font-semibold">Generated operations</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[10px] text-muted-foreground">
                {guidance.operations.map((operation) => (
                  <li key={operation}>{operation}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </EdgeLabelRenderer>
    </>
  )
}
