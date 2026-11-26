"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { fieldErrors, messageOf, send } from "@/lib/client";
import type { OrganiserEvent } from "@/lib/types";
import { cn } from "@/lib/utils";
import { field, FormError } from "./ui";

export const POSTERS = [
  "neon-alley",
  "the-last-dune",
  "undertow",
  "hollowmere",
  "glass-city",
  "static-bloom",
  "midnight-brass",
  "rhythm-collective",
].map((p) => `/img/posters/${p}.jpg`);

const RATINGS = ["U", "UA", "UA 7+", "UA 13+", "UA 16+", "A"];

const MESSAGES: Record<string, string> = {
  title: "2–80 characters",
  genre: "2–40 characters",
  duration_min: "Between 30 and 400 minutes",
  synopsis: "10–1,200 characters",
  poster_url: "Pick a poster",
};

/** S11 · create or edit an event. The slug is set once from the title, so links never break. */
export function EventForm({ event }: { event?: OrganiserEvent }) {
  const router = useRouter();
  const [type, setType] = useState<"movie" | "concert">(event?.type ?? "movie");
  const [poster, setPoster] = useState(event?.poster_url ?? POSTERS[0]);
  const [status, setStatus] = useState<"live" | "draft">(event?.status ?? "live");
  const [busy, setBusy] = useState<"save" | "showtime" | null>(null);
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const then = ((e.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null)?.value === "showtime" ? "showtime" : "save";
    const data = new FormData(e.currentTarget);
    const text = (k: string) => String(data.get(k) ?? "").trim();
    const body = {
      title: text("title"),
      type,
      genre: text("genre"),
      duration_min: Number(text("duration_min")),
      rating: type === "movie" ? text("rating") || null : null,
      synopsis: text("synopsis"),
      cast_lineup: text("cast_lineup")
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean),
      poster_url: poster,
      status,
    };
    setBusy(then);
    setError("");
    setFields({});
    try {
      const saved = event
        ? await send<OrganiserEvent>("PATCH", `/organiser/events/${event.id}`, body)
        : await send<OrganiserEvent>("POST", "/organiser/events", body);
      router.push(then === "showtime" ? `/organiser/showtimes/new?event_id=${saved.id}` : `/organiser/events?saved=${saved.slug}`);
      router.refresh();
    } catch (err) {
      const f = fieldErrors(err);
      setFields(f);
      setError(Object.keys(f).length ? "Check the highlighted fields." : messageOf(err));
      setBusy(null);
    }
  }

  const err = (k: string) =>
    fields[k] ? <span className={field.error}>{MESSAGES[k.split(".")[0]] ?? fields[k]}</span> : null;
  const bad = (k: string) => Object.keys(fields).some((f) => f === k || f.startsWith(`${k}.`));

  return (
    <form onSubmit={submit} className="grid items-start gap-6 lg:grid-cols-[1fr_340px]">
      <div className="grid gap-4 rounded-card bg-paper p-5 text-ink sm:p-6">
        <label className={field.label}>
          Title
          <input name="title" required minLength={2} maxLength={80} defaultValue={event?.title} className={field.input} aria-invalid={bad("title")} />
          {event ? <span className={field.hint}>Link: /events/{event.slug} (stays the same if you rename)</span> : err("title")}
        </label>

        <div className="grid gap-4 sm:grid-cols-2">
          <fieldset className="border-0 p-0">
            <legend className={field.legend}>Type</legend>
            <div className="grid grid-cols-2 gap-2">
              {(["movie", "concert"] as const).map((t) => (
                <label
                  key={t}
                  className={cn(
                    "cursor-pointer rounded-btn border-2 px-3 py-2 text-center font-cond text-lg font-bold uppercase has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-amber",
                    type === t ? "border-ink bg-white/60" : "border-ink/15 hover:border-ink/40",
                  )}
                >
                  <input type="radio" name="type" value={t} checked={type === t} onChange={() => setType(t)} className="sr-only" />
                  {t === "movie" ? "Movie" : "Concert"}
                </label>
              ))}
            </div>
          </fieldset>
          <label className={field.label}>
            Genre
            <input
              name="genre"
              required
              minLength={2}
              maxLength={40}
              defaultValue={event?.genre}
              placeholder={type === "movie" ? "Thriller" : "Indie rock"}
              className={field.input}
              aria-invalid={bad("genre")}
            />
            {err("genre")}
          </label>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className={field.label}>
            Running time (minutes)
            <input
              name="duration_min"
              type="number"
              inputMode="numeric"
              required
              min={30}
              max={400}
              defaultValue={event?.duration_min ?? (type === "movie" ? 120 : 110)}
              className={field.input}
              aria-invalid={bad("duration_min")}
            />
            {err("duration_min")}
          </label>
          {type === "movie" ? (
            <label className={field.label}>
              Certificate
              <select name="rating" defaultValue={event?.rating ?? "UA"} className={field.input}>
                {RATINGS.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <p className="self-end pb-3 text-xs text-ink-3">Concerts carry no certificate.</p>
          )}
        </div>

        <label className={field.label}>
          Synopsis
          <textarea
            name="synopsis"
            required
            minLength={10}
            maxLength={1200}
            rows={4}
            defaultValue={event?.synopsis}
            className={field.input}
            aria-invalid={bad("synopsis")}
          />
          {err("synopsis")}
        </label>

        <label className={field.label}>
          {type === "movie" ? "Cast" : "Line-up"}
          <textarea
            name="cast_lineup"
            rows={3}
            defaultValue={event?.cast_lineup?.join("\n")}
            placeholder={type === "movie" ? "One name per line" : "Headliner\nopening: Support act"}
            className={field.input}
            aria-invalid={bad("cast_lineup")}
          />
          <span className={field.hint}>One per line, up to 12</span>
        </label>

        <fieldset className="border-0 p-0">
          <legend className={field.legend}>Status</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {(
              [
                ["live", "Live", "Listed on the site; showtimes are bookable"],
                ["draft", "Draft", "Hidden from customers until you publish"],
              ] as const
            ).map(([value, title, sub]) => (
              <label
                key={value}
                className={cn(
                  "cursor-pointer rounded-card border-2 px-3 py-2 has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-amber",
                  status === value ? "border-ink bg-white/60" : "border-ink/15 hover:border-ink/40",
                )}
              >
                <input type="radio" name="status" value={value} checked={status === value} onChange={() => setStatus(value)} className="sr-only" />
                <b className="block font-cond text-lg font-bold uppercase">{title}</b>
                <span className="text-xs text-ink-2">{sub}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <FormError message={error} />
        <div className="flex flex-wrap gap-2">
          <Button type="submit" value="save" disabled={busy !== null}>
            {busy === "save" ? "Saving…" : event ? "Save changes" : "Create event"}
          </Button>
          <Button type="submit" value="showtime" variant="paper" disabled={busy !== null}>
            {busy === "showtime" ? "Saving…" : "Save & add a showtime"}
          </Button>
        </div>
      </div>

      <fieldset className="grid content-start gap-3 border-0 p-0 lg:sticky lg:top-6">
        <legend className="mb-2 font-cond text-2xl font-bold uppercase">Poster</legend>
        <div className="relative aspect-[2/3] w-full max-w-[340px] overflow-hidden rounded-card bg-plum-2">
          <Image src={poster} alt="Selected poster" fill sizes="340px" className="object-cover" />
        </div>
        <div className="grid grid-cols-4 gap-2">
          {POSTERS.map((p) => (
            <label
              key={p}
              className={cn(
                "relative aspect-[2/3] cursor-pointer overflow-hidden rounded-btn border-2 has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-amber",
                poster === p ? "border-red" : "border-transparent opacity-75 hover:opacity-100",
              )}
            >
              <input
                type="radio"
                name="poster"
                checked={poster === p}
                onChange={() => setPoster(p)}
                className="sr-only"
                aria-label={`Poster ${p.split("/").pop()?.replace(".jpg", "").replace(/-/g, " ")}`}
              />
              <Image src={p} alt="" fill sizes="80px" className="object-cover" />
            </label>
          ))}
        </div>
        <p className="text-xs text-faint">Posters come from the bundled CC photo library; uploads arrive in a later version.</p>
      </fieldset>
    </form>
  );
}
