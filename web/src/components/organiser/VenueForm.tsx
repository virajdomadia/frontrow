"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import type { Layout } from "@/components/seat-map/core";
import { Button } from "@/components/ui/button";
import { fieldErrors, messageOf, send } from "@/lib/client";
import type { OrganiserVenue } from "@/lib/types";
import { cn } from "@/lib/utils";
import { LayoutPreview } from "./LayoutPreview";
import { field, FormError } from "./ui";

type Template = "grid" | "stalls_balcony" | "arena";
type Band = { label: string; rows: number };

// Defaults and ranges mirror api/app/schemas/layouts.py.
const GRID = { rows: 14, seats_per_row: 18, aisle_after: 9, stage_label: "SCREEN" };
const STALLS = { stalls_rows: 12, stalls_seats: 28, front_rows: 5, balcony_rows: 6, balcony_seats: 24, curve: 0.5, stage_label: "STAGE" };
const ARENA = { sections: 8, rows_per_section: 12, seats_per_row: 16, floor_rows: 20, floor_seats: 20, floor_radius: 360, stage_label: "STAGE" };

type Knob = { key: string; label: string; min: number; max: number; step?: number; hint?: string };

const KNOBS: Record<Template, Knob[]> = {
  grid: [
    { key: "rows", label: "Rows", min: 8, max: 20 },
    { key: "seats_per_row", label: "Seats per row", min: 10, max: 24 },
    { key: "aisle_after", label: "Aisle after seat", min: 2, max: 22, hint: "Centre aisle position" },
  ],
  stalls_balcony: [
    { key: "stalls_rows", label: "Stalls rows", min: 8, max: 16 },
    { key: "stalls_seats", label: "Seats per stalls row", min: 18, max: 36 },
    { key: "front_rows", label: "Front stalls rows", min: 2, max: 8, hint: "Priced as front; the rest are rear" },
    { key: "balcony_rows", label: "Balcony rows", min: 3, max: 10 },
    { key: "balcony_seats", label: "Seats per balcony row", min: 14, max: 30 },
    { key: "curve", label: "Row curve", min: 0, max: 1, step: 0.1, hint: "0 = straight, 1 = tight arc" },
  ],
  arena: [
    { key: "sections", label: "Sections", min: 6, max: 12, hint: "Wedges around the floor" },
    { key: "rows_per_section", label: "Rows per section", min: 6, max: 14 },
    { key: "seats_per_row", label: "Max seats per row", min: 10, max: 20 },
    { key: "floor_rows", label: "Floor rows", min: 0, max: 24, hint: "0 = no floor seating" },
    { key: "floor_seats", label: "Floor seats per row", min: 0, max: 24 },
    { key: "floor_radius", label: "Floor radius", min: 200, max: 420, step: 10 },
  ],
};

const TEMPLATES: { value: Template; title: string; sub: string }[] = [
  { value: "grid", title: "Cinema grid", sub: "Straight rows · centre aisle · tiers by row" },
  { value: "stalls_balcony", title: "Stalls + balcony", sub: "Auditorium · curved rows · two blocks" },
  { value: "arena", title: "Arena", sub: "Wedge sections around a floor" },
];

const PHOTOS = [
  { src: "/img/venues/orbit-cinemas.jpg", alt: "Cinema auditorium" },
  { src: "/img/venues/cadence-hall.jpg", alt: "Concert hall" },
  { src: "/img/venues/yard-arena.jpg", alt: "Arena stage at night" },
];

/** "Recliner +" → "recliner"; unique, and always a valid tier key (`^[a-z][a-z0-9_-]*`). */
function tierKeys(bands: Band[]) {
  const seen = new Set<string>();
  return bands.map((b, i) => {
    let key = b.label.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 20);
    if (!/^[a-z]/.test(key)) key = `tier${i + 1}${key ? `-${key}` : ""}`.slice(0, 20);
    while (seen.has(key)) key = `${key}-${i + 1}`;
    seen.add(key);
    return key;
  });
}

/** S10 · new venue: template + knobs with a live preview drawn by the real seat map. */
export function VenueForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [photo, setPhoto] = useState<string | null>(null);
  const [template, setTemplate] = useState<Template>("grid");
  const [grid, setGrid] = useState(GRID);
  const [bands, setBands] = useState<Band[]>([
    { label: "Classic", rows: 6 },
    { label: "Prime", rows: 6 },
    { label: "Recliner", rows: 2 },
  ]);
  const [stalls, setStalls] = useState(STALLS);
  const [arena, setArena] = useState(ARENA);
  const [layout, setLayout] = useState<Layout | null>(null);
  const [previewError, setPreviewError] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});

  const values = (template === "grid" ? grid : template === "stalls_balcony" ? stalls : arena) as unknown as Record<string, number>;
  const bandTotal = bands.reduce((a, b) => a + (Number.isFinite(b.rows) ? b.rows : 0), 0);

  const knobs = useMemo(() => {
    if (template === "grid") {
      const keys = tierKeys(bands);
      return { template, ...grid, tiers: bands.map((b, i) => ({ key: keys[i], label: b.label.trim() || `Tier ${i + 1}`, rows: b.rows })) };
    }
    return template === "stalls_balcony" ? { template, ...stalls } : { template, ...arena };
  }, [template, grid, bands, stalls, arena]);
  const knobsKey = JSON.stringify(knobs);

  // Debounced preview: the api generates the layout exactly as it will be saved.
  useEffect(() => {
    const ctrl = new AbortController();
    const t = setTimeout(async () => {
      try {
        setLayout(await send<Layout>("POST", "/organiser/venues/preview", { knobs: JSON.parse(knobsKey) }, { signal: ctrl.signal }));
        setPreviewError("");
      } catch (e) {
        if ((e as Error)?.name === "AbortError") return;
        const f = fieldErrors(e);
        const first = Object.values(f)[0];
        setPreviewError(first ? first.replace(/^Value error, /, "") : messageOf(e));
      }
    }, 300);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [knobsKey]);

  function setKnob(key: string, raw: string) {
    const n = raw === "" ? NaN : Number(raw);
    if (template === "grid") setGrid((g) => ({ ...g, [key]: n }));
    else if (template === "stalls_balcony") setStalls((s) => ({ ...s, [key]: n }));
    else setArena((a) => ({ ...a, [key]: n }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setFields({});
    try {
      const venue = await send<OrganiserVenue>("POST", "/organiser/venues", {
        name,
        address,
        photo_url: photo,
        knobs,
      });
      router.push(`/organiser/venues/${venue.id}?created=1`);
      router.refresh();
    } catch (err) {
      const f = fieldErrors(err);
      setFields(f);
      setError(f.name || f.address ? "Check the highlighted fields." : messageOf(err));
      setBusy(false);
    }
  }

  const seats = layout ? layout.sections.reduce((a, s) => a + s.rows.reduce((b, r) => b + r.seats.length, 0), 0) : null;

  return (
    <form onSubmit={submit} className="grid items-start gap-6 lg:grid-cols-[minmax(0,440px)_1fr]">
      <div className="grid gap-5 rounded-card bg-paper p-5 text-ink sm:p-6">
        <label className={field.label}>
          Venue name
          <input
            required
            minLength={2}
            maxLength={80}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Lumen Cinemas · Screen 1"
            className={field.input}
            aria-invalid={!!fields.name}
          />
          {fields.name && <span className={field.error}>{fields.name === "taken" ? "You already have a venue with this name" : fields.name}</span>}
        </label>
        <label className={field.label}>
          Address
          <input
            required
            minLength={4}
            maxLength={200}
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="12 Church Street, Bengaluru 560001"
            autoComplete="street-address"
            className={field.input}
            aria-invalid={!!fields.address}
          />
        </label>

        <fieldset className="border-0 p-0">
          <legend className={field.legend}>Layout template</legend>
          <div className="grid gap-2">
            {TEMPLATES.map((t) => (
              <label
                key={t.value}
                className={cn(
                  "cursor-pointer rounded-card border-2 px-3.5 py-2.5 transition-colors has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-amber",
                  template === t.value ? "border-ink bg-white/60" : "border-ink/15 hover:border-ink/40",
                )}
              >
                <input
                  type="radio"
                  name="template"
                  value={t.value}
                  checked={template === t.value}
                  onChange={() => setTemplate(t.value)}
                  className="sr-only"
                />
                <b className="block font-cond text-xl font-bold uppercase">{t.title}</b>
                <span className="text-xs text-ink-2">{t.sub}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset className="border-0 p-0">
          <legend className={field.legend}>Knobs</legend>
          <div className="grid grid-cols-2 gap-3">
            {KNOBS[template].map((k) => (
              <label key={`${template}-${k.key}`} className={field.label}>
                {k.label}
                <input
                  type="number"
                  inputMode="decimal"
                  required
                  min={k.min}
                  max={k.max}
                  step={k.step ?? 1}
                  value={Number.isFinite(values[k.key]) ? values[k.key] : ""}
                  onChange={(e) => setKnob(k.key, e.target.value)}
                  className={field.input}
                />
                <span className={field.hint}>
                  {k.min}–{k.max}
                  {k.hint ? ` · ${k.hint}` : ""}
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        {template === "grid" && (
          <fieldset className="border-0 p-0">
            <legend className={field.legend}>Tier bands, front to back</legend>
            <ul className="grid list-none gap-2 p-0">
              {bands.map((b, i) => (
                <li key={i} className="grid grid-cols-[1fr_88px_auto] items-end gap-2">
                  <label className={field.label}>
                    <span className="sr-only">Tier {i + 1} name</span>
                    <input
                      value={b.label}
                      maxLength={40}
                      required
                      onChange={(e) => setBands((bs) => bs.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))}
                      className={field.input}
                    />
                  </label>
                  <label className={field.label}>
                    <span className="sr-only">Rows in {b.label || `tier ${i + 1}`}</span>
                    <input
                      type="number"
                      min={1}
                      max={20}
                      required
                      value={Number.isFinite(b.rows) ? b.rows : ""}
                      onChange={(e) =>
                        setBands((bs) => bs.map((x, j) => (j === i ? { ...x, rows: e.target.value === "" ? NaN : Number(e.target.value) } : x)))
                      }
                      className={field.input}
                    />
                  </label>
                  <Button
                    type="button"
                    variant="paper"
                    size="sm"
                    disabled={bands.length === 1}
                    onClick={() => setBands((bs) => bs.filter((_, j) => j !== i))}
                    aria-label={`Remove ${b.label || `tier ${i + 1}`}`}
                    className="h-[46px]"
                  >
                    ✕
                  </Button>
                </li>
              ))}
            </ul>
            <div className="mt-2 flex items-center justify-between gap-3">
              <span className={cn("text-xs", bandTotal === grid.rows ? "text-ink-3" : "font-semibold text-red-dark")}>
                Bands cover {bandTotal} of {Number.isFinite(grid.rows) ? grid.rows : "?"} rows
              </span>
              <Button
                type="button"
                variant="paper"
                size="sm"
                disabled={bands.length >= 4}
                onClick={() => setBands((bs) => [...bs, { label: `Tier ${bs.length + 1}`, rows: 1 }])}
              >
                Add tier
              </Button>
            </div>
          </fieldset>
        )}

        <fieldset className="border-0 p-0">
          <legend className={field.legend}>Photo (optional)</legend>
          <div className="grid grid-cols-4 gap-2">
            <PhotoChoice checked={photo === null} onChange={() => setPhoto(null)} label="None">
              <span className="grid size-full place-items-center text-xs text-ink-2">None</span>
            </PhotoChoice>
            {PHOTOS.map((p) => (
              <PhotoChoice key={p.src} checked={photo === p.src} onChange={() => setPhoto(p.src)} label={p.alt}>
                <Image src={p.src} alt="" fill sizes="120px" className="object-cover" />
              </PhotoChoice>
            ))}
          </div>
          <span className={cn(field.hint, "mt-1.5 block")}>From the CC photo library; uploads arrive in a later version.</span>
        </fieldset>

        <FormError message={error} />
        <Button type="submit" disabled={busy || !!previewError || !layout} className="w-full">
          {busy ? "Generating seats…" : seats ? `Create venue · ${seats.toLocaleString("en-IN")} seats` : "Create venue"}
        </Button>
      </div>

      <div className="grid gap-2 lg:sticky lg:top-6">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="font-cond text-2xl font-bold uppercase">Live preview</h2>
          <span className="text-sm text-muted-foreground tabular-nums" aria-live="polite">
            {seats !== null && !previewError ? `${seats.toLocaleString("en-IN")} seats` : ""}
          </span>
        </div>
        {previewError ? (
          <p role="alert" className="grid h-[340px] place-items-center rounded-card border border-dashed border-amber/50 px-6 text-center text-amber sm:h-[420px]">
            {previewError}
          </p>
        ) : layout ? (
          <LayoutPreview layout={layout} />
        ) : (
          <div className="h-[340px] animate-pulse rounded-card bg-plum-2 sm:h-[420px]" aria-label="Loading preview" />
        )}
        <p className="text-xs text-faint">This is the seat map customers will see. Seats are generated once, when you create the venue.</p>
      </div>
    </form>
  );
}

function PhotoChoice({
  checked,
  onChange,
  label,
  children,
}: {
  checked: boolean;
  onChange: () => void;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label
      className={cn(
        "relative aspect-[4/3] cursor-pointer overflow-hidden rounded-btn border-2 bg-paper-2 has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-amber",
        checked ? "border-ink" : "border-transparent",
      )}
    >
      <input type="radio" name="photo" checked={checked} onChange={onChange} className="sr-only" aria-label={label} />
      {children}
    </label>
  );
}
