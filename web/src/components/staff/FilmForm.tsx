"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { inputClass, labelClass } from "@/components/auth/CodeSignIn";
import { Button } from "@/components/ui/button";
import { ApiRequestError } from "@/lib/api-error";
import { fieldErrors, messageOf, send } from "@/lib/client";
import type { StaffFilm } from "@/lib/types";
import { cn } from "@/lib/utils";
import { DEMO_REASON, FormError } from "./ui";

/** v1 posters are the bundled typographic ones (api/scripts/make_posters.py); uploads are out of scope. */
const POSTERS = [
  "ramayana-part-1",
  "yeh-prem-mol-liya",
  "maatrubhumi",
  "eetha",
  "king",
  "golmaal-5",
  "love-and-war",
  "hunger-games-sunrise-on-the-reaping",
  "how-to-rob-a-bank",
  "avengers-doomsday",
  "dune-part-three",
].map((p) => `/img/posters/${p}.png`);

const FORMATS = ["2D", "3D", "IMAX"] as const;
const CERTS = [
  ["", "Not yet certified"],
  ["U", "U — all ages"],
  ["UA 7+", "UA 7+ — parental guidance under 7"],
  ["UA 13+", "UA 13+ — parental guidance under 13"],
  ["UA 16+", "UA 16+ — parental guidance under 16"],
  ["UA", "UA — parental guidance (pre-2024 certificate)"],
  ["A", "A — adults only (18+)"],
] as const;
const STATUSES = [
  ["coming_soon", "Coming soon"],
  ["now_showing", "Now showing"],
  ["ended", "Ended"],
] as const;

type Cast = { name: string; role: string };

const list = (s: string) =>
  s
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);

function todayIst() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).format(new Date());
}

/** T2: every field of a catalogue film. New films POST (with `request_id` when answering an
 * owner's request); edits PATCH the full film. */
export function FilmForm({
  film,
  requestId,
  initialTitle,
  demo,
}: {
  film?: StaffFilm;
  requestId?: string;
  initialTitle?: string;
  demo: boolean;
}) {
  const router = useRouter();
  const [cast, setCast] = useState<Cast[]>(
    film?.cast_crew.length ? film.cast_crew.map((c) => ({ name: c.name, role: c.role })) : [
      { name: "", role: "Director" },
      { name: "", role: "Actor" },
    ],
  );
  const [formats, setFormats] = useState<string[]>(film?.formats ?? ["2D"]);
  const [poster, setPoster] = useState(film?.poster_url ?? POSTERS[0]);
  const [banner, setBanner] = useState<string>(film?.banner_url ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});

  const err = (key: string) =>
    Object.entries(fields).find(([k]) => k === key || k.startsWith(`${key}.`))?.[1];

  function setCastAt(i: number, patch: Partial<Cast>) {
    setCast((c) => c.map((row, j) => (j === i ? { ...row, ...patch } : row)));
  }

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (demo) return;
    const data = new FormData(e.currentTarget);
    const body = {
      title: String(data.get("title") ?? "").trim(),
      synopsis: String(data.get("synopsis") ?? "").trim(),
      cast_crew: cast.filter((c) => c.name.trim()).map((c) => ({ name: c.name.trim(), role: c.role.trim() || "Actor" })),
      runtime_min: data.get("runtime_min") ? Number(data.get("runtime_min")) : null, // blank: not announced
      cert: String(data.get("cert") ?? "") || null, // blank: not yet certified
      genres: list(String(data.get("genres") ?? "")),
      languages: list(String(data.get("languages") ?? "")),
      formats,
      poster_url: poster,
      banner_url: banner || null,
      trailer_url: String(data.get("trailer_url") ?? "").trim() || null,
      release_date: String(data.get("release_date")),
      status: String(data.get("status")),
      ...(requestId && !film ? { request_id: requestId } : {}),
    };
    setBusy(true);
    setError("");
    setFields({});
    try {
      if (film) await send("PATCH", `/staff/films/${film.id}`, body);
      else await send("POST", "/staff/films", body);
      router.push(requestId ? "/staff/requests?status=added" : "/staff/films");
      router.refresh();
    } catch (e) {
      setError(
        e instanceof ApiRequestError && e.body.code === "demo_read_only"
          ? DEMO_REASON
          : e instanceof ApiRequestError && e.status === 422
            ? "Some fields need a look — see the notes below each one."
            : messageOf(e),
      );
      setFields(fieldErrors(e));
      setBusy(false);
    }
  }

  const note = (k: string) => {
    const m = err(k);
    return m ? <span className="text-xs font-medium text-red-dark">{m}</span> : null;
  };

  return (
    <form onSubmit={submit} className="grid gap-6 lg:grid-cols-[1fr_340px]">
      <div className="grid content-start gap-5 rounded-card border border-border bg-plum-2 p-5 sm:p-6">
        <label className={labelClass}>
          Title
          <input name="title" required maxLength={120} defaultValue={film?.title ?? initialTitle ?? ""} className={inputClass} aria-invalid={!!err("title")} />
          {note("title")}
        </label>
        <label className={labelClass}>
          Synopsis
          <textarea
            name="synopsis"
            required
            minLength={20}
            maxLength={1500}
            rows={4}
            defaultValue={film?.synopsis ?? ""}
            className={inputClass}
            aria-invalid={!!err("synopsis")}
          />
          {note("synopsis")}
        </label>

        <fieldset className="grid gap-2 border-0 p-0">
          <legend className="mb-1.5 text-sm font-semibold text-ink-2">Cast &amp; crew</legend>
          {cast.map((c, i) => (
            <div key={i} className="grid grid-cols-[1fr_150px_auto] gap-2">
              <input
                aria-label={`Name ${i + 1}`}
                placeholder="Name"
                value={c.name}
                maxLength={60}
                onChange={(e) => setCastAt(i, { name: e.target.value })}
                className={inputClass}
              />
              <input
                aria-label={`Role ${i + 1}`}
                placeholder="Role"
                value={c.role}
                maxLength={60}
                list="film-roles"
                onChange={(e) => setCastAt(i, { role: e.target.value })}
                className={inputClass}
              />
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={cast.length <= 1}
                onClick={() => setCast((all) => all.filter((_, j) => j !== i))}
                aria-label={`Remove ${c.name || `row ${i + 1}`}`}
              >
                ✕
              </Button>
            </div>
          ))}
          <datalist id="film-roles">
            <option value="Director" />
            <option value="Actor" />
            <option value="Writer" />
            <option value="Music" />
            <option value="Producer" />
          </datalist>
          <div>
            <Button type="button" variant="paper" size="sm" disabled={cast.length >= 20} onClick={() => setCast((all) => [...all, { name: "", role: "Actor" }])}>
              Add a person
            </Button>
          </div>
          {note("cast_crew")}
        </fieldset>

        <div className="grid gap-4 sm:grid-cols-3">
          <label className={labelClass}>
            Runtime (minutes, blank if not announced)
            <input name="runtime_min" type="number" min={40} max={240} defaultValue={film ? (film.runtime_min ?? "") : 120} className={inputClass} aria-invalid={!!err("runtime_min")} />
            {note("runtime_min")}
          </label>
          <label className={labelClass}>
            Certificate
            <select name="cert" defaultValue={film ? (film.cert ?? "") : "UA 13+"} className={inputClass}>
              {CERTS.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
          <label className={labelClass}>
            Release date
            <input name="release_date" type="date" required defaultValue={film?.release_date ?? todayIst()} className={inputClass} aria-invalid={!!err("release_date")} />
            {note("release_date")}
          </label>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className={labelClass}>
            Genres
            <input name="genres" required defaultValue={film?.genres.join(", ") ?? ""} placeholder="Drama, Thriller" className={inputClass} aria-invalid={!!err("genres")} />
            <span className="text-xs font-normal text-ink-3">Comma-separated, up to 4.</span>
            {note("genres")}
          </label>
          <label className={labelClass}>
            Languages
            <input name="languages" required defaultValue={film?.languages.join(", ") ?? ""} placeholder="Kannada, Hindi, English" className={inputClass} aria-invalid={!!err("languages")} />
            <span className="text-xs font-normal text-ink-3">Comma-separated, up to 6. Owners schedule shows in these.</span>
            {note("languages")}
          </label>
        </div>

        <fieldset className="grid gap-2 border-0 p-0">
          <legend className="mb-1.5 text-sm font-semibold text-ink-2">Formats</legend>
          <div className="flex flex-wrap gap-4">
            {FORMATS.map((f) => (
              <label key={f} className="flex items-center gap-2 text-[15px]">
                <input
                  type="checkbox"
                  checked={formats.includes(f)}
                  onChange={(e) => setFormats((all) => (e.target.checked ? [...all, f] : all.filter((x) => x !== f)))}
                  className="size-4 accent-[var(--red)]"
                />
                {f}
              </label>
            ))}
          </div>
          {note("formats")}
        </fieldset>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className={labelClass}>
            Trailer (optional)
            <input name="trailer_url" type="url" defaultValue={film?.trailer_url ?? ""} placeholder="https://www.youtube.com/watch?v=…" className={inputClass} aria-invalid={!!err("trailer_url")} />
            <span className="text-xs font-normal text-ink-3">A YouTube or Vimeo link.</span>
            {note("trailer_url")}
          </label>
          <label className={labelClass}>
            Status
            <select name="status" defaultValue={film?.status ?? "coming_soon"} className={inputClass}>
              {STATUSES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
            <span className="text-xs font-normal text-ink-3">Customers see now-showing films with shows; ended films take no new shows.</span>
          </label>
        </div>
      </div>

      <aside className="grid content-start gap-5">
        <div className="grid gap-3 rounded-card border border-border bg-plum-2 p-5">
          <h2 className="font-cond text-xl font-bold uppercase">Poster</h2>
          <div className="relative aspect-[2/3] overflow-hidden rounded-card bg-plum-3">
            <Image src={poster} alt="Selected poster" fill sizes="340px" className="object-cover" />
          </div>
          <PosterPicker value={poster} onChange={setPoster} label="Poster" />
          {note("poster_url")}
          <p className="text-xs text-ink-3">Films are real, so posters are our own typographic art (api/scripts/make_posters.py) — never studio artwork.</p>
        </div>
        <div className="grid gap-3 rounded-card border border-border bg-plum-2 p-5">
          <h2 className="font-cond text-xl font-bold uppercase">Banner</h2>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={!banner} onChange={(e) => setBanner(e.target.checked ? "" : poster)} className="size-4 accent-[var(--red)]" />
            No separate banner (the movie page uses the poster)
          </label>
          {banner && <PosterPicker value={banner} onChange={setBanner} label="Banner" />}
          {note("banner_url")}
        </div>
        <FormError message={error} />
        <Button type="submit" disabled={busy || demo || formats.length === 0} title={demo ? DEMO_REASON : undefined} className="w-full">
          {busy ? "Saving…" : film ? "Save changes" : requestId ? "Add film and answer request" : "Add to catalogue"}
        </Button>
        {demo && <p className="text-xs text-ink-3">{DEMO_REASON}</p>}
      </aside>
    </form>
  );
}

function PosterPicker({ value, onChange, label }: { value: string; onChange: (v: string) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={`${label} from the library`} className="grid grid-cols-4 gap-2">
      {POSTERS.map((p) => (
        <button
          key={p}
          type="button"
          role="radio"
          aria-checked={value === p}
          aria-label={p.split("/").pop()?.replace(".jpg", "").replaceAll("-", " ")}
          onClick={() => onChange(p)}
          className={cn(
            "relative aspect-[2/3] cursor-pointer overflow-hidden rounded-sm border-2 p-0",
            value === p ? "border-red" : "border-transparent opacity-80 hover:opacity-100",
          )}
        >
          <Image src={p} alt="" fill sizes="256px" className="object-cover" />
        </button>
      ))}
    </div>
  );
}
