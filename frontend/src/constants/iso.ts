/**
 * Authored config-ISO limits — frontend mirrors of the backend caps in
 * `routers/deploy.py` / `routers/iso.py`. Client-side checks are a
 * courtesy (early toasts instead of a 422 after Deploy); the backend re-checks
 * everything authoritatively.
 */

export const ISO_MAX_FILES = 20
export const ISO_FILE_MAX_BYTES = 256 * 1024
export const ISO_OP_MAX_BYTES = 512 * 1024
export const ISO_UPLOAD_MAX_BYTES = 128 * 1024 * 1024

/** Mirrors `_ISO_FILE_NAME` in deploy.py — letters/digits/._- plus .ps1/.sh. */
export const ISO_FILE_NAME_RE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}\.(ps1|sh)$/

export const ISO_MODES = {
  pack: "pack",
  uploadIso: "uploadIso",
} as const

export type IsoMode = (typeof ISO_MODES)[keyof typeof ISO_MODES]
