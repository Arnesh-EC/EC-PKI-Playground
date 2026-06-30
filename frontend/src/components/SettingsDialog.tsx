import { useState } from "react"
import { AlertDialog } from "@base-ui/react/alert-dialog"
import { Settings } from "lucide-react"

import { Button } from "@/components/ui/button"

/**
 * Settings entry point next to the theme toggle. Currently a placeholder —
 * the dialog shell is wired up so future settings have a home without
 * touching the header again.
 */
export function SettingsDialog() {
  const [open, setOpen] = useState(false)

  return (
    <AlertDialog.Root open={open} onOpenChange={setOpen}>
      <AlertDialog.Trigger
        render={
          <Button variant="ghost" size="icon-sm" aria-label="Settings" title="Settings">
            <Settings className="h-4 w-4" />
          </Button>
        }
      />
      <AlertDialog.Portal>
        <AlertDialog.Backdrop className="fixed inset-0 z-50 bg-black/40 backdrop-blur-[1px] data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0" />
        <AlertDialog.Popup className="fixed left-1/2 top-1/2 z-50 w-[min(360px,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 rounded-xl border bg-popover p-5 text-popover-foreground shadow-lg ring-1 ring-foreground/10 data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95 data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95">
          <AlertDialog.Title className="text-sm font-semibold">
            Settings
          </AlertDialog.Title>
          <AlertDialog.Description className="mt-2 text-xs text-muted-foreground">
            More settings coming soon.
          </AlertDialog.Description>
          <div className="mt-5 flex justify-end">
            <Button size="sm" onClick={() => setOpen(false)}>
              Close
            </Button>
          </div>
        </AlertDialog.Popup>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  )
}
