"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { inputClass, labelClass } from "@/components/auth/CodeSignIn";
import { Button, buttonVariants } from "@/components/ui/button";
import { ApiRequestError } from "@/lib/api-error";
import { messageOf, send } from "@/lib/client";
import { cn } from "@/lib/utils";
import { DEMO_REASON, FormError } from "./ui";

type Mode = "idle" | "link" | "decline";

/** T3: answer an owner's film request — add it, link a film already in the catalogue, or decline. */
export function RequestActions({
  id,
  title,
  films,
  demo,
}: {
  id: string;
  title: string;
  films: { id: string; title: string }[];
  demo: boolean;
}) {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("idle");
  const [filmId, setFilmId] = useState(films[0]?.id ?? "");
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function patch(body: Record<string, unknown>) {
    setBusy(true);
    setError("");
    try {
      await send("PATCH", `/staff/film-requests/${id}`, body);
      setMode("idle");
      router.refresh();
    } catch (e) {
      setError(e instanceof ApiRequestError && e.body.code === "demo_read_only" ? DEMO_REASON : messageOf(e));
    } finally {
      setBusy(false);
    }
  }

  const off = demo || busy;
  const tip = demo ? DEMO_REASON : undefined;
  const addHref = `/staff/films/new?request=${encodeURIComponent(id)}&title=${encodeURIComponent(title)}`;
  return (
    <div className="grid gap-3">
      {mode === "idle" && (
        <div className="flex flex-wrap gap-2">
          {demo ? (
            <Button type="button" size="sm" disabled title={tip}>
              Add to catalogue
            </Button>
          ) : (
            <Link href={addHref} className={buttonVariants({ size: "sm" })}>
              Add to catalogue
            </Link>
          )}
          <Button type="button" size="sm" variant="paper" disabled={off || films.length === 0} title={tip} onClick={() => setMode("link")}>
            Link existing film…
          </Button>
          <Button type="button" size="sm" variant="paper" disabled={off} title={tip} onClick={() => setMode("decline")}>
            Decline…
          </Button>
        </div>
      )}

      {mode === "link" && (
        <form
          className="grid gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            void patch({ action: "link", film_id: filmId });
          }}
        >
          <label className={labelClass}>
            It&apos;s already in the catalogue as
            <select value={filmId} onChange={(e) => setFilmId(e.target.value)} className={inputClass}>
              {films.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.title}
                </option>
              ))}
            </select>
          </label>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" size="sm" disabled={off || !filmId}>
              {busy ? "Saving…" : "Link film"}
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setMode("idle")}>
              Cancel
            </Button>
          </div>
        </form>
      )}

      {mode === "decline" && (
        <form
          className="grid gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            void patch({ action: "decline", reply });
          }}
        >
          <label className={labelClass}>
            Why not?
            <textarea
              required
              maxLength={300}
              rows={2}
              value={reply}
              onChange={(e) => setReply(e.target.value)}
              className={cn(inputClass)}
              placeholder="e.g. No distributor confirmation yet — ask again once prints are confirmed."
            />
            <span className="text-xs font-normal text-ink-3">The owner sees this next to their request.</span>
          </label>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" size="sm" disabled={off || !reply.trim()}>
              {busy ? "Saving…" : "Decline request"}
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setMode("idle")}>
              Cancel
            </Button>
          </div>
        </form>
      )}
      {demo && <p className="text-xs text-ink-3">{DEMO_REASON}</p>}
      <FormError message={error} />
    </div>
  );
}
