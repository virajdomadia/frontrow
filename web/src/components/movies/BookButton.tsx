"use client";

import Link from "next/link";
import { X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button, buttonVariants } from "@/components/ui/button";
import type { Version } from "@/lib/types";
import { cn } from "@/lib/utils";

export function showsHref(slug: string, v?: { language: string; format: string }) {
  return v ? `/movies/${slug}/shows?language=${encodeURIComponent(v.language)}&format=${encodeURIComponent(v.format)}` : `/movies/${slug}/shows`;
}

/**
 * "Book tickets" (C2 → C3 → C4). One language + format: straight to the showtimes. More than
 * one: a sheet to pick it first (BookMyShow's flow), grouped by language.
 */
export function BookButton({ slug, title, versions, label = "Book tickets", className }: {
  slug: string;
  title: string;
  versions: Version[];
  label?: string;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  if (versions.length <= 1)
    return (
      <Link href={showsHref(slug, versions[0])} className={cn(buttonVariants({ size: "lg" }), className)}>
        {label}
      </Link>
    );

  const byLanguage = new Map<string, Version[]>();
  for (const v of versions) byLanguage.set(v.language, [...(byLanguage.get(v.language) ?? []), v]);

  return (
    <>
      <Button size="lg" onClick={() => setOpen(true)} className={className}>
        {label}
      </Button>
      <dialog
        ref={ref}
        onClose={() => setOpen(false)}
        aria-labelledby="pick-version"
        className="m-auto w-[min(460px,100%-32px)] rounded-card bg-paper p-6 text-ink shadow-[0_30px_80px_rgb(42_11_30_/_.35)] backdrop:bg-ink/60"
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 id="pick-version" className="font-cond text-3xl font-extrabold uppercase">
              {title}
            </h2>
            <p className="text-sm text-ink-2">Pick a language and format</p>
          </div>
          <button type="button" onClick={() => setOpen(false)} aria-label="Close" className="-mt-1 -mr-2 cursor-pointer rounded-btn p-2 text-ink-2 hover:bg-ink/10">
            <X className="size-5" aria-hidden="true" />
          </button>
        </div>
        <div className="grid gap-4">
          {[...byLanguage.entries()].map(([language, list]) => (
            <div key={language} className="grid gap-2">
              <h3 className="font-cond text-lg font-bold tracking-[.06em] uppercase">{language}</h3>
              <div className="flex flex-wrap gap-2">
                {list.map((v) => (
                  <Link
                    key={v.format}
                    href={showsHref(slug, v)}
                    className="rounded-btn border-2 border-ink/20 px-4 py-2 no-underline hover:border-red hover:text-red-dark"
                  >
                    <b className="font-cond text-lg">{v.format}</b>
                    <span className="ml-2 text-xs text-ink-3">{v.show_count} shows</span>
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      </dialog>
    </>
  );
}
