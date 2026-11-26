"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import type { Cert } from "@/lib/types";
import { cn } from "@/lib/utils";
import { CertBadge } from "@/components/movies/badges";

/**
 * C5 · before the map: the certificate notice when the film needs one (A: 18+, ID may be
 * checked; UA: parental guidance), then "How many seats?" 1–10. A tap on the map then picks
 * that many seats together.
 */
export function HowMany({
  open,
  cert,
  certNote,
  title,
  initial,
  max,
  onPick,
  onClose,
}: {
  open: boolean;
  cert: Cert;
  certNote: string;
  title: string;
  initial: number;
  max: number;
  onPick: (n: number) => void;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [n, setN] = useState(initial);
  const [agreed, setAgreed] = useState(cert !== "A");

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) {
      setN(initial);
      d.showModal();
    }
    if (!open && d.open) d.close();
  }, [open, initial]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby="how-many"
      className="m-auto w-[min(480px,100%-32px)] rounded-card bg-paper p-6 text-ink shadow-[0_30px_80px_rgb(42_11_30_/_.35)] backdrop:bg-ink/55"
    >
      {cert !== "U" && (
        <div className={cn("mb-5 flex gap-3 rounded-card p-3.5", cert === "A" ? "bg-red-dark/10" : "bg-paper-2")}>
          <CertBadge cert={cert} className="mt-0.5 shrink-0" />
          <div className="grid gap-2 text-sm">
            <p>
              <b>{title}</b> is rated {cert}. {certNote}.
            </p>
            {cert === "A" && (
              <label className="flex cursor-pointer items-center gap-2 font-semibold">
                <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} className="size-4 accent-[#B8232F]" />
                Everyone in my booking is 18 or older
              </label>
            )}
          </div>
        </div>
      )}
      <h2 id="how-many" className="font-cond text-3xl font-extrabold uppercase">
        How many seats?
      </h2>
      <p className="mt-1 text-sm text-ink-2">Tap a seat on the map and we&apos;ll pick this many together.</p>
      <div role="radiogroup" aria-label="Number of seats" className="mt-4 grid grid-cols-5 gap-2">
        {Array.from({ length: max }, (_, i) => i + 1).map((k) => (
          <button
            key={k}
            type="button"
            role="radio"
            aria-checked={n === k}
            onClick={() => setN(k)}
            className={cn(
              "cursor-pointer rounded-btn border-2 py-2 font-cond text-2xl font-bold",
              n === k ? "border-red bg-red text-white" : "border-ink/15 hover:border-ink/50",
            )}
          >
            {k}
          </button>
        ))}
      </div>
      <Button type="button" className="mt-5 w-full" disabled={!agreed} onClick={() => onPick(n)}>
        Select {n} {n === 1 ? "seat" : "seats"}
      </Button>
    </dialog>
  );
}
