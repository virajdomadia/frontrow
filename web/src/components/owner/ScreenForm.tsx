"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import type { Layout } from "@/components/seat-map/core";
import { Button } from "@/components/ui/button";
import { fieldErrors, messageOf, send } from "@/lib/client";
import type { OwnerScreen } from "@/lib/types";
import { cn } from "@/lib/utils";
import { LayoutPreview } from "./LayoutPreview";
import { field, FormError } from "./ui";

type Template = "grid" | "stalls_balcony";
type Format = "2D" | "3D" | "IMAX";
type Band = { label: string; rows: number };

const FORMATS: Format[] = ["2D", "3D", "IMAX"];

// Defaults and ranges mirror api/app/schemas/layouts.py.
const GRID = { rows: 14, seats_per_row: 18, aisle_after: 9, stage_label: "SCREEN" };
const STALLS = { stalls_rows: 12, stalls_seats: 28, front_rows: 5, balcony_rows: 6, balcony_seats: 24, curve: 0.5, stage_label: "SCREEN" };

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
};

const TEMPLATES: { value: Template; title: string; sub: string }[] = [
  { value: "grid", title: "Cinema grid", sub: "Multiplex · straight rows · centre aisle · tiers by row" },
  { value: "stalls_balcony", title: "Stalls + balcony", sub: "Older single screens · curved rows · front, rear, balcony" },
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

/** O4 · new screen: template + knobs + formats, with a live preview drawn by the real seat map. */
export function ScreenForm({ cinemaId, cinemaName, suggestedName }: { cinemaId: string; cinemaName: string; suggestedName: string }) {
  const router = useRouter();
  const [name, setName] = useState(suggestedName);
  const [formats, setFormats] = useState<Format[]>(["2D"]);
  const [template, setTemplate] = useState<Template>("grid");
  const [grid, setGrid] = useState(GRID);
  const [bands, setBands] = useState<Band[]>([
    { label: "Classic", rows: 6 },
    { label: "Prime", rows: 6 },
    { label: "Recliner", rows: 2 },
  ]);
  const [stalls, setStalls] = useState(STALLS);
  const [layout, setLayout] = useState<Layout | null>(null);
  const [previewError, setPreviewError] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});

  const values = (template === "grid" ? grid : stalls) as unknown as Record<string, number>;
  const bandTotal = bands.reduce((a, b) => a + (Number.isFinite(b.rows) ? b.rows : 0), 0);

  const knobs = useMemo(() => {
    if (template === "grid") {
      const keys = tierKeys(bands);
      return { template, ...grid, tiers: bands.map((b, i) => ({ key: keys[i], label: b.label.trim() || `Tier ${i + 1}`, rows: b.rows })) };
    }
    return { template, ...stalls };
  }, [template, grid, bands, stalls]);
  const knobsKey = JSON.stringify(knobs);

  // Debounced preview: the api generates the layout exactly as it will be saved.
  useEffect(() => {
    const ctrl = new AbortController();
    const t = setTimeout(async () => {
      try {
        setLayout(await send<Layout>("POST", "/owner/screens/preview", { knobs: JSON.parse(knobsKey) }, { signal: ctrl.signal }));
        setPreviewError("");
      } catch (e) {
        if ((e as Error)?.name === "AbortError") return;
        const first = Object.values(fieldErrors(e))[0];
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
    else setStalls((s) => ({ ...s, [key]: n }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setFields({});
    try {
      const screen = await send<OwnerScreen>("POST", `/owner/cinemas/${cinemaId}/screens`, { name, formats, knobs });
      router.push(`/owner/cinemas/${cinemaId}?added=${encodeURIComponent(screen.name)}`);
      router.refresh();
    } catch (err) {
      const f = fieldErrors(err);
      setFields(f);
      setError(f.name ? "Check the highlighted fields." : messageOf(err));
      setBusy(false);
    }
  }

  const seats = layout ? layout.sections.reduce((a, s) => a + s.rows.reduce((b, r) => b + r.seats.length, 0), 0) : null;

  return (
    <form onSubmit={submit} className="grid items-start gap-6 lg:grid-cols-[minmax(0,440px)_1fr]">
      <div className="fr-stub grid gap-5 p-5 text-ink sm:p-6">
        <p className="text-sm text-ink-2">
          Adding a screen to <b className="text-ink">{cinemaName}</b>.
        </p>
        <label className={field.label}>
          Screen name
          <input
            required
            maxLength={40}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Screen 3"
            className={field.input}
            aria-invalid={!!fields.name}
          />
          {fields.name && <span className={field.error}>{fields.name === "taken" ? "This cinema already has a screen with this name" : fields.name}</span>}
        </label>

        <fieldset className="border-0 p-0">
          <legend className={field.legend}>Formats this screen can play</legend>
          <div className="flex flex-wrap gap-2">
            {FORMATS.map((f) => {
              const on = formats.includes(f);
              return (
                <label
                  key={f}
                  className={cn(
                    "cursor-pointer rounded-btn border-2 px-3.5 py-1.5 font-cond text-lg font-bold uppercase has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-amber",
                    on ? "border-ink bg-ink text-paper" : "border-ink/20 hover:border-ink/50",
                  )}
                >
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={() => setFormats((fs) => (on ? fs.filter((x) => x !== f) : [...fs, f]))}
                    className="sr-only"
                  />
                  {f}
                </label>
              );
            })}
          </div>
          {formats.length === 0 && <span className={cn(field.error, "mt-1 block")}>Pick at least one format</span>}
        </fieldset>

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
                <input type="radio" name="template" value={t.value} checked={template === t.value} onChange={() => setTemplate(t.value)} className="sr-only" />
                <b className="block font-cond text-xl font-bold uppercase">{t.title}</b>
                <span className="text-xs text-ink-2">{t.sub}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset className="border-0 p-0">
          <legend className={field.legend}>Size</legend>
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

        {template === "grid" ? (
          <fieldset className="border-0 p-0">
            <legend className={field.legend}>Seat tiers, front to back</legend>
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
                Tiers cover {bandTotal} of {Number.isFinite(grid.rows) ? grid.rows : "?"} rows
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
        ) : (
          <p className={field.hint}>Tiers: Front stalls, Rear stalls and Balcony — you price each one per show.</p>
        )}

        <FormError message={error} />
        <Button type="submit" disabled={busy || !!previewError || !layout || formats.length === 0} className="w-full">
          {busy ? "Generating seats…" : seats ? `Create screen · ${seats.toLocaleString("en-IN")} seats` : "Create screen"}
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
          <p role="alert" className="grid h-[340px] place-items-center rounded-card border border-dashed border-amber/50 px-6 text-center font-medium text-[#8a4a10] sm:h-[420px]">
            {previewError}
          </p>
        ) : layout ? (
          <LayoutPreview layout={layout} />
        ) : (
          <div className="h-[340px] animate-pulse rounded-card bg-plum-2 sm:h-[420px]" aria-label="Loading preview" />
        )}
        <p className="text-xs text-faint">This is the seat map customers will see. Seats are generated once, when you create the screen.</p>
      </div>
    </form>
  );
}
