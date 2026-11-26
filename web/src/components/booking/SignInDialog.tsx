"use client";

import { X } from "lucide-react";
import { useEffect, useRef } from "react";
import { CodeSignIn } from "@/components/auth/CodeSignIn";
import { DemoButtons } from "@/components/auth/DemoButtons";
import type { Me } from "@/lib/types";

/**
 * Inline sign-in at Proceed (C7, R5): a modal `<dialog>` (focus trapped, Esc closes) so a visitor
 * signs in by email code without leaving the map — and keeps the seats they're holding.
 */
export function SignInDialog({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: (me: Me) => void }) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby="signin-title"
      className="m-auto max-h-[calc(100dvh-32px)] w-[min(440px,100%-32px)] overflow-y-auto rounded-card bg-paper p-6 text-ink shadow-[0_30px_80px_rgb(42_11_30_/_.35)] backdrop:bg-ink/60 backdrop:backdrop-blur-[2px]"
    >
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <h2 id="signin-title" className="font-cond text-3xl font-extrabold uppercase">
            Sign in to pay
          </h2>
          <p className="mt-1 text-sm text-ink-2">Your seats stay held while you sign in with an emailed code.</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="-mt-1 -mr-2 cursor-pointer rounded-btn p-2 text-ink-2 hover:bg-ink/10 hover:text-ink"
        >
          <X className="size-5" aria-hidden="true" />
        </button>
      </div>
      {open && (
        <>
          <CodeSignIn door="customer" onDone={onDone} submitLabel="Sign in and continue" />
          <div className="mt-5 grid gap-2 border-t border-dashed border-ink/25 pt-4">
            <p className="text-center text-xs font-semibold tracking-[.12em] text-ink-2 uppercase">Or try it as the demo customer</p>
            <DemoButtons only="customer" onDone={onDone} />
          </div>
        </>
      )}
    </dialog>
  );
}
