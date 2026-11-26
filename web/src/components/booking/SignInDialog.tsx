"use client";

import { X } from "lucide-react";
import { useEffect, useRef } from "react";
import { AuthForm } from "@/components/auth/AuthForm";
import type { Me } from "@/lib/types";

/**
 * Inline sign-in at Proceed (R5): a modal `<dialog>` (focus trapped, Esc closes) so a visitor
 * signs in or signs up without leaving the map — and keeps the seats they're holding.
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
      className="m-auto max-h-[calc(100dvh-32px)] w-[min(440px,100%-32px)] overflow-y-auto rounded-card bg-paper p-6 text-ink shadow-[0_30px_80px_rgba(0,0,0,.6)] backdrop:bg-plum/80 backdrop:backdrop-blur-[2px]"
    >
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <h2 id="signin-title" className="font-cond text-3xl font-extrabold uppercase">
            Sign in to pay
          </h2>
          <p className="mt-1 text-sm text-ink-2">Your seats stay held while you sign in or create an account.</p>
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
      {open && <AuthForm mode="sign-in" onDone={onDone} compact />}
    </dialog>
  );
}
