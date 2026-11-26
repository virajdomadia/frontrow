import { cn } from "@/lib/utils";

/** A quiet placeholder block for route `loading.tsx` files. */
export function Block({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn("animate-pulse rounded-card bg-plum-2 motion-reduce:animate-none", className)} />;
}

/** Announced once, so a screen reader knows something is coming. */
export function Loading({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div role="status" aria-live="polite">
      <span className="sr-only">{label}</span>
      {children}
    </div>
  );
}
