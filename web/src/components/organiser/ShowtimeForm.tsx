"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { fieldErrors, messageOf, send } from "@/lib/client";
import type { OrganiserEvent, OrganiserShowtime, OrganiserVenue } from "@/lib/types";
import { istInputs, istIso, TEMPLATE_LABEL } from "./format";
import { field, FormError } from "./ui";

// A sensible starting price per tier, by position front→back, when nothing has been typed yet.
const SUGGEST: Record<string, number> = {
  classic: 220, prime: 320, recliner: 550,
  front: 1500, rear: 900, balcony: 600,
  floor: 3500, gold: 2500, silver: 1500, bronze: 900,
}; // prettier-ignore

function tomorrowAt(hhmm: string) {
  const d = istInputs(new Date(Date.now() + 86_400_000));
  return { date: d.date, time: hhmm };
}

/** S12 · new showtime: event + venue + IST start + a price per tier (leave one blank = not on sale). */
export function ShowtimeForm({
  events,
  venues,
  eventId,
  venueId,
}: {
  events: OrganiserEvent[];
  venues: OrganiserVenue[];
  eventId?: string;
  venueId?: string;
}) {
  const router = useRouter();
  const [event, setEvent] = useState(events.find((e) => e.id === eventId)?.id ?? events[0]?.id ?? "");
  const [venue, setVenue] = useState(venues.find((v) => v.id === venueId)?.id ?? venues[0]?.id ?? "");
  const start = tomorrowAt("19:30");
  const [date, setDate] = useState(start.date);
  const [time, setTime] = useState(start.time);
  const [prices, setPrices] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});

  const chosenVenue = venues.find((v) => v.id === venue);
  const chosenEvent = events.find((e) => e.id === event);
  const today = istInputs(new Date()).date;

  const priceOf = (key: string) => prices[key] ?? (SUGGEST[key] !== undefined ? String(SUGGEST[key]) : "");
  const tiers = (chosenVenue?.tiers ?? [])
    .map((t) => ({ key: t.key, label: t.label, rupees: priceOf(t.key).trim() }))
    .filter((t) => t.rupees !== "");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!tiers.length) {
      setError("Price at least one tier — a blank tier is not on sale.");
      return;
    }
    setBusy(true);
    setError("");
    setFields({});
    try {
      const created = await send<OrganiserShowtime>("POST", "/organiser/showtimes", {
        event_id: event,
        venue_id: venue,
        starts_at: istIso(date, time),
        tiers: tiers.map((t) => ({ tier_key: t.key, label: t.label, price_paise: Math.round(Number(t.rupees) * 100) })),
      });
      router.push(`/organiser/showtimes?created=${created.id}`);
      router.refresh();
    } catch (err) {
      const f = fieldErrors(err);
      setFields(f);
      const first = Object.values(f)[0];
      setError(first ? (first.startsWith("Input should be") || first.startsWith("Value error") ? "Check the prices: ₹10 – ₹1,00,000 per seat." : first) : messageOf(err));
      setBusy(false);
    }
  }

  if (!events.length || !venues.length)
    return (
      <div className="grid justify-items-start gap-3 rounded-card bg-paper p-6 text-ink">
        <h2 className="font-cond text-2xl font-bold uppercase">First, {!venues.length ? "a venue" : "an event"}</h2>
        <p className="max-w-[52ch] text-ink-2">
          A showtime is an event at a venue. You need {!venues.length && !events.length ? "both a venue and an event" : !venues.length ? "a venue" : "an event"} before you can schedule one.
        </p>
        <div className="flex flex-wrap gap-2">
          {!venues.length && (
            <Link href="/organiser/venues/new" className="font-semibold text-ink underline underline-offset-4">
              Create a venue
            </Link>
          )}
          {!events.length && (
            <Link href="/organiser/events/new" className="font-semibold text-ink underline underline-offset-4">
              Create an event
            </Link>
          )}
        </div>
      </div>
    );

  return (
    <form onSubmit={submit} className="grid max-w-[720px] gap-5 rounded-card bg-paper p-5 text-ink sm:p-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className={field.label}>
          Event
          <select value={event} onChange={(e) => setEvent(e.target.value)} className={field.input} required>
            {events.map((e) => (
              <option key={e.id} value={e.id}>
                {e.title}
                {e.status === "draft" ? " (draft)" : ""}
              </option>
            ))}
          </select>
          {chosenEvent?.status === "draft" && (
            <span className={field.hint}>This event is a draft — the showtime won&apos;t be bookable until you publish it.</span>
          )}
        </label>
        <label className={field.label}>
          Venue
          <select value={venue} onChange={(e) => setVenue(e.target.value)} className={field.input} required>
            {venues.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
          </select>
          {chosenVenue && (
            <span className={field.hint}>
              {TEMPLATE_LABEL[chosenVenue.template]} · {chosenVenue.seat_count.toLocaleString("en-IN")} seats
            </span>
          )}
        </label>
      </div>

      <fieldset className="border-0 p-0">
        <legend className={field.legend}>Starts (Bengaluru time, IST)</legend>
        <div className="grid grid-cols-2 gap-3">
          <label className={field.label}>
            <span className="sr-only">Date</span>
            <input type="date" required min={today} value={date} onChange={(e) => setDate(e.target.value)} className={field.input} aria-invalid={!!fields.starts_at} />
          </label>
          <label className={field.label}>
            <span className="sr-only">Time</span>
            <input type="time" required step={300} value={time} onChange={(e) => setTime(e.target.value)} className={field.input} aria-invalid={!!fields.starts_at} />
          </label>
        </div>
        {fields.starts_at && <span className={field.error}>{fields.starts_at}</span>}
      </fieldset>

      <fieldset className="border-0 p-0">
        <legend className={field.legend}>Price per seat, by tier</legend>
        <ul className="grid list-none gap-2 p-0">
          {(chosenVenue?.tiers ?? []).map((t) => (
            <li key={`${venue}-${t.key}`}>
              <label className="grid grid-cols-[1fr_150px] items-center gap-3 rounded-btn bg-paper-2 px-3 py-2 text-sm font-semibold text-ink-2">
                {t.label}
                <span className="relative">
                  <span aria-hidden="true" className="absolute top-1/2 left-3 -translate-y-1/2 text-ink-2">
                    ₹
                  </span>
                  <input
                    type="number"
                    inputMode="numeric"
                    min={10}
                    max={100000}
                    step={1}
                    placeholder="Not on sale"
                    value={priceOf(t.key)}
                    onChange={(e) => setPrices((p) => ({ ...p, [t.key]: e.target.value }))}
                    className={`${field.input} pl-7`}
                    aria-label={`${t.label} price in rupees`}
                  />
                </span>
              </label>
            </li>
          ))}
        </ul>
        <span className={`${field.hint} mt-1.5 block`}>Leave a tier blank to keep it off sale. A ₹30 convenience fee per ticket is added at checkout.</span>
      </fieldset>

      <FormError message={error} />
      <Button type="submit" disabled={busy} className="w-full sm:w-auto sm:justify-self-start">
        {busy ? "Scheduling…" : "Schedule showtime"}
      </Button>
    </form>
  );
}
