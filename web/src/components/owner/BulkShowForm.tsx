"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Button, buttonVariants } from "@/components/ui/button";
import { ApiRequestError } from "@/lib/api-error";
import { fieldErrors, messageOf, send } from "@/lib/client";
import type { BulkResult, FilmCard, OwnerCinema } from "@/lib/types";
import { cn } from "@/lib/utils";
import { dateTime, istInputs } from "./format";
import { field, FormError } from "./ui";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const DEFAULT_PRICE: Record<string, number> = { classic: 180, prime: 260, recliner: 450, front: 120, rear: 160, balcony: 220 };

function addDays(key: string, n: number) {
  const d = new Date(`${key}T12:00:00+05:30`);
  d.setUTCDate(d.getUTCDate() + n);
  return istInputs(d).date;
}

/**
 * O6 · bulk scheduling (B9): film + language + format + screen + days + times + a price per
 * tier, over a date range of up to 60 days. The api creates every show or none, and names the
 * show a time clashes with (runtime + cleaning gap).
 */
export function BulkShowForm({
  films,
  cinemas,
  initialFilm,
  initialScreen,
}: {
  films: FilmCard[];
  cinemas: OwnerCinema[];
  initialFilm?: string;
  initialScreen?: string;
}) {
  const screens = useMemo(() => cinemas.flatMap((c) => c.screens.map((s) => ({ ...s, cinema: c.name }))), [cinemas]);
  const today = istInputs(new Date()).date;
  const [filmId, setFilmId] = useState(films.some((f) => f.id === initialFilm) ? initialFilm! : (films[0]?.id ?? ""));
  const [screenId, setScreenId] = useState(screens.some((s) => s.id === initialScreen) ? initialScreen! : (screens[0]?.id ?? ""));
  const film = films.find((f) => f.id === filmId);
  const screen = screens.find((s) => s.id === screenId);
  const formats = film && screen ? film.formats.filter((f) => screen.formats.includes(f)) : [];
  const [language, setLanguage] = useState(film?.languages[0] ?? "");
  const [format, setFormat] = useState(formats[0] ?? "");
  const [days, setDays] = useState<number[]>([0, 1, 2, 3, 4, 5, 6]);
  const [times, setTimes] = useState<string[]>(["10:00"]);
  const [from, setFrom] = useState(today);
  const [to, setTo] = useState(addDays(today, 6));
  const [prices, setPrices] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [result, setResult] = useState<BulkResult | null>(null);

  const lang = film?.languages.includes(language) ? language : (film?.languages[0] ?? "");
  const fmt = formats.includes(format) ? format : (formats[0] ?? "");
  const priceOf = (key: string) => prices[key] ?? String(DEFAULT_PRICE[key] ?? 200);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!film || !screen) return;
    setBusy(true);
    setError("");
    setFields({});
    setResult(null);
    try {
      const body = {
        screen_id: screen.id,
        film_id: film.id,
        language: lang,
        format: fmt,
        days,
        times,
        from_date: from,
        to_date: to,
        prices: Object.fromEntries(screen.tiers.map((t) => [t.key, Math.round(Number(priceOf(t.key)) * 100)])),
      };
      setResult(await send<BulkResult>("POST", "/owner/shows/bulk", body));
    } catch (err) {
      const f = fieldErrors(err);
      setFields(f);
      setError(
        err instanceof ApiRequestError && err.body.code === "overlap"
          ? `Nothing was created. ${err.body.message}.`
          : Object.keys(f).length && err instanceof ApiRequestError && err.body.code === "validation" && err.body.message === "Request validation failed"
            ? "Check the highlighted fields."
            : messageOf(err),
      );
    }
    setBusy(false);
  }

  if (!films.length || !screens.length)
    return (
      <div className="fr-stub grid justify-items-start gap-3 p-6 text-ink">
        <h2 className="font-cond text-2xl font-bold uppercase">{screens.length ? "No films to schedule" : "Add a screen first"}</h2>
        <p className="text-ink-2">
          {screens.length ? "The catalogue is empty — request a film from staff." : "Shows run on a screen. Add a cinema and its screens, then come back."}
        </p>
        <Link href={screens.length ? "/owner/films" : "/owner/cinemas"} className={buttonVariants({ size: "sm" })}>
          {screens.length ? "Request a film" : "Set up cinemas"}
        </Link>
      </div>
    );

  if (result) {
    const firstDay = istInputs(result.first).date;
    return (
      <div role="status" className="fr-stub grid justify-items-start gap-3 p-6 text-ink">
        <h2 className="font-cond text-3xl font-extrabold uppercase">{result.created} shows scheduled</h2>
        <p className="text-ink-2">
          {film?.title} · {lang} · {fmt} on {screen?.cinema} · {screen?.name}. First {dateTime(result.first)}, last {dateTime(result.last)}.
        </p>
        <div className="flex flex-wrap gap-2">
          <Link href={`/owner/shows?date=${firstDay}`} className={buttonVariants({ size: "sm" })}>
            See that day
          </Link>
          <Button type="button" variant="paper" size="sm" onClick={() => setResult(null)}>
            Schedule more
          </Button>
        </div>
      </div>
    );
  }

  const err = (k: string) => fields[k] ?? Object.entries(fields).find(([key]) => key.startsWith(`${k}.`))?.[1];

  return (
    <form onSubmit={submit} className="fr-stub grid max-w-[880px] gap-6 p-5 text-ink sm:p-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className={field.label}>
          Film
          <select value={filmId} onChange={(e) => setFilmId(e.target.value)} className={field.input}>
            {films.map((f) => (
              <option key={f.id} value={f.id}>
                {f.title} ({f.cert}, {f.runtime_min} min){f.status === "coming_soon" ? " — coming soon" : ""}
              </option>
            ))}
          </select>
        </label>
        <label className={field.label}>
          Screen
          <select value={screenId} onChange={(e) => setScreenId(e.target.value)} className={field.input}>
            {cinemas
              .filter((c) => c.screens.length)
              .map((c) => (
                <optgroup key={c.id} label={c.name}>
                  {c.screens.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} · {s.seat_count} seats · {s.formats.join("/")}
                    </option>
                  ))}
                </optgroup>
              ))}
          </select>
        </label>
        <label className={field.label}>
          Language
          <select value={lang} onChange={(e) => setLanguage(e.target.value)} className={field.input} aria-invalid={!!err("language")}>
            {film?.languages.map((l) => (
              <option key={l}>{l}</option>
            ))}
          </select>
          {err("language") && <span className={field.error}>{err("language")}</span>}
        </label>
        <label className={field.label}>
          Format
          <select value={fmt} onChange={(e) => setFormat(e.target.value)} className={field.input} disabled={!formats.length} aria-invalid={!!err("format")}>
            {formats.map((f) => (
              <option key={f}>{f}</option>
            ))}
          </select>
          {!formats.length && (
            <span className={field.error}>
              {film?.title} comes in {film?.formats.join("/")}; {screen?.name} plays {screen?.formats.join("/")}. Pick another screen.
            </span>
          )}
          {err("format") && <span className={field.error}>{err("format")}</span>}
        </label>
      </div>

      <fieldset className="border-0 p-0">
        <legend className={field.legend}>Days of the week</legend>
        <div className="flex flex-wrap gap-2">
          {DAYS.map((d, i) => {
            const on = days.includes(i);
            return (
              <label
                key={d}
                className={cn(
                  "cursor-pointer rounded-btn border-2 px-3 py-1.5 font-cond text-lg font-bold uppercase has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-amber",
                  on ? "border-ink bg-ink text-paper" : "border-ink/20 hover:border-ink/50",
                )}
              >
                <input
                  type="checkbox"
                  checked={on}
                  onChange={() => setDays((ds) => (on ? ds.filter((x) => x !== i) : [...ds, i].sort()))}
                  className="sr-only"
                />
                {d}
              </label>
            );
          })}
        </div>
        {!days.length && <span className={cn(field.error, "mt-1 block")}>Pick at least one day</span>}
      </fieldset>

      <fieldset className="border-0 p-0">
        <legend className={field.legend}>Start times (IST)</legend>
        <ul className="flex list-none flex-wrap gap-2 p-0">
          {times.map((t, i) => (
            <li key={i} className="flex items-center gap-1">
              <input
                type="time"
                required
                value={t}
                onChange={(e) => setTimes((ts) => ts.map((x, j) => (j === i ? e.target.value : x)))}
                className={cn(field.input, "w-[130px]")}
                aria-label={`Start time ${i + 1}`}
              />
              <Button
                type="button"
                variant="paper"
                size="sm"
                disabled={times.length === 1}
                onClick={() => setTimes((ts) => ts.filter((_, j) => j !== i))}
                aria-label={`Remove ${t}`}
                className="h-[46px]"
              >
                ✕
              </Button>
            </li>
          ))}
          <li>
            <Button type="button" variant="paper" size="sm" disabled={times.length >= 8} onClick={() => setTimes((ts) => [...ts, "18:00"])} className="h-[46px]">
              Add time
            </Button>
          </li>
        </ul>
        <span className={cn(field.hint, "mt-1 block")}>
          {film ? `${film.title} runs ${film.runtime_min} min; leave room for 15 min of cleaning between shows.` : ""}
        </span>
        {err("times") && <span className={cn(field.error, "block")}>{err("times")}</span>}
      </fieldset>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className={field.label}>
          From
          <input type="date" required min={today} value={from} onChange={(e) => setFrom(e.target.value)} className={field.input} aria-invalid={!!err("from_date")} />
          {err("from_date") && <span className={field.error}>{err("from_date")}</span>}
        </label>
        <label className={field.label}>
          To
          <input type="date" required min={from} max={addDays(from, 59)} value={to} onChange={(e) => setTo(e.target.value)} className={field.input} aria-invalid={!!err("to_date")} />
          <span className={field.hint}>Up to 60 days at a time.</span>
          {err("to_date") && <span className={field.error}>{err("to_date")}</span>}
        </label>
      </div>

      {screen && (
        <fieldset className="border-0 p-0">
          <legend className={field.legend}>Ticket price per tier (₹) — customers also pay a ₹30 fee</legend>
          <div className="grid gap-3 sm:grid-cols-3">
            {screen.tiers.map((t) => (
              <label key={t.key} className={field.label}>
                {t.label}
                <input
                  type="number"
                  required
                  min={50}
                  max={2000}
                  step={10}
                  inputMode="numeric"
                  value={priceOf(t.key)}
                  onChange={(e) => setPrices((p) => ({ ...p, [t.key]: e.target.value }))}
                  className={field.input}
                  aria-invalid={!!err(`prices.${t.key}`)}
                />
              </label>
            ))}
          </div>
          {err("prices") && <span className={cn(field.error, "mt-1 block")}>{err("prices")}</span>}
        </fieldset>
      )}

      <FormError message={error} />
      <Button type="submit" disabled={busy || !days.length || !fmt || !lang} className="w-full sm:w-auto sm:justify-self-start">
        {busy ? "Scheduling…" : "Schedule shows"}
      </Button>
    </form>
  );
}
