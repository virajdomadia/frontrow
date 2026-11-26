"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { messageOf, send } from "@/lib/client";

/**
 * S12 · cancel with an inline confirm. A showtime with tickets sold is blocked by the api
 * (409 `has_sales`) — its message is shown as-is, so the guard is visible, not hidden.
 */
export function CancelShowtime({ id, title }: { id: string; title: string }) {
  const router = useRouter();
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function cancel() {
    setBusy(true);
    setError("");
    try {
      await send("PATCH", `/organiser/showtimes/${id}`, { status: "cancelled" });
      setAsking(false);
      router.refresh();
    } catch (e) {
      setError(messageOf(e));
    } finally {
      setBusy(false);
    }
  }

  if (error)
    return (
      <div role="alert" className="grid max-w-[340px] gap-1.5 rounded-btn border border-amber/50 bg-amber/10 px-3 py-2 text-sm text-amber">
        {error}
        <button type="button" onClick={() => { setError(""); setAsking(false); }} className="cursor-pointer justify-self-start text-xs text-screen underline underline-offset-4">
          OK
        </button>
      </div>
    );
  if (!asking)
    return (
      <Button type="button" variant="ghost" size="sm" onClick={() => setAsking(true)}>
        Cancel
      </Button>
    );
  return (
    <div role="group" aria-label={`Cancel ${title}?`} className="flex flex-wrap items-center gap-2 rounded-btn bg-plum-3 px-3 py-1.5 text-sm">
      <span>Cancel this showtime? It stops selling at once.</span>
      <Button type="button" size="sm" disabled={busy} onClick={cancel}>
        {busy ? "Cancelling…" : "Yes, cancel"}
      </Button>
      <Button type="button" variant="ghost" size="sm" disabled={busy} onClick={() => setAsking(false)}>
        Keep it
      </Button>
    </div>
  );
}

/** Filter the list by event without a submit button (the URL carries it). */
export function EventFilter({ events, value }: { events: { id: string; title: string }[]; value?: string }) {
  const router = useRouter();
  return (
    <label className="flex items-center gap-2 text-sm text-muted-foreground">
      Event
      <select
        value={value ?? ""}
        onChange={(e) => router.push(e.target.value ? `/organiser/showtimes?event_id=${e.target.value}` : "/organiser/showtimes")}
        className="rounded-btn border border-input bg-plum-2 px-3 py-2 text-screen"
      >
        <option value="">All events</option>
        {events.map((e) => (
          <option key={e.id} value={e.id}>
            {e.title}
          </option>
        ))}
      </select>
    </label>
  );
}
