/**
 * Auth mode and capability registries.
 *
 * These are the frontend mirrors of the backend's AuthMode / Capability enums
 * (core/authz.py). String values must stay in sync with the backend.
 *
 * Types are derived from the const objects — there are no hand-written unions.
 * Add or rename a value here and the type updates automatically.
 */

export const AUTH_MODES = {
  login: "login",
  guest: "guest",
} as const

export type AuthMode = (typeof AUTH_MODES)[keyof typeof AUTH_MODES]

export const ROLES = {
  operator: "operator",
  guest: "guest",
} as const

export type Role = (typeof ROLES)[keyof typeof ROLES]

export const CAPABILITIES = {
  vmList: "vm:list",
  vmRead: "vm:read",
  vmClone: "vm:clone",
  vmUpdate: "vm:update",
  vmPower: "vm:power",
  configGenerate: "config:generate",
  isoAuthor: "iso:author", // operator-only — authored/uploaded config ISOs (Phase E)
  vmExecArbitrary: "vm:exec-arbitrary", // reserved — future orchestrator phase
  deploy: "deploy",
  projectRead: "project:read", // operator-only — gates server-side project persistence
  projectWrite: "project:write",
} as const

export type Capability = (typeof CAPABILITIES)[keyof typeof CAPABILITIES]
