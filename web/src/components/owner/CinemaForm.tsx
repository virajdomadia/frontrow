"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { fieldErrors, messageOf, send } from "@/lib/client";
import type { OwnerCinema } from "@/lib/types";
import { cn } from "@/lib/utils";
import { field, FormError } from "./ui";

// Mirrors `Facility` in api/app/schemas/owner.py.
const FACILITIES = ["Dolby Atmos", "4K laser", "Recliners", "Wheelchair access", "Food court", "Parking", "M-ticket"] as const;
type Facility = (typeof FACILITIES)[number];

const PHOTOS = [
  { src: "/img/cinemas/orbit-cinemas.jpg", alt: "Multiplex auditorium" },
  { src: "/img/cinemas/cadence-hall.jpg", alt: "Single-screen hall with a balcony" },
];

/** O3 · add or edit a cinema: name, area, address, facilities, a photo from the CC library. */
export function CinemaForm({ cinema }: { cinema?: OwnerCinema }) {
  const router = useRouter();
  const [facilities, setFacilities] = useState<Facility[]>((cinema?.facilities ?? []) as Facility[]);
  const [photo, setPhoto] = useState<string | null>(cinema?.photo_url ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [fields, setFields] = useState<Record<string, string>>({});

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    setSaved(false);
    setFields({});
    const body = {
      name: String(data.get("name") ?? ""),
      area: String(data.get("area") ?? ""),
      address: String(data.get("address") ?? ""),
      facilities,
      photo_url: photo,
    };
    try {
      if (cinema) {
        await send<OwnerCinema>("PATCH", `/owner/cinemas/${cinema.id}`, body);
        setSaved(true);
        setBusy(false);
        router.refresh();
      } else {
        const made = await send<OwnerCinema>("POST", "/owner/cinemas", body);
        router.push(`/owner/cinemas/${made.id}?new=1`);
        router.refresh();
      }
    } catch (err) {
      const f = fieldErrors(err);
      setFields(f);
      setError(Object.keys(f).length ? "Check the highlighted fields." : messageOf(err));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="fr-stub grid gap-5 p-5 text-ink sm:p-6">
      <label className={field.label}>
        Cinema name
        <input
          name="name"
          required
          minLength={2}
          maxLength={80}
          defaultValue={cinema?.name}
          placeholder="Sunrise Talkies · Jayanagar"
          className={field.input}
          aria-invalid={!!fields.name}
        />
        {fields.name && <span className={field.error}>{fields.name === "taken" ? "You already have a cinema with this name" : fields.name}</span>}
      </label>
      <div className="grid gap-4 sm:grid-cols-[200px_1fr]">
        <label className={field.label}>
          Area
          <input
            name="area"
            required
            minLength={2}
            maxLength={60}
            defaultValue={cinema?.area}
            placeholder="Jayanagar"
            className={field.input}
            aria-invalid={!!fields.area}
          />
        </label>
        <label className={field.label}>
          Address
          <input
            name="address"
            required
            minLength={6}
            maxLength={200}
            defaultValue={cinema?.address}
            placeholder="11th Main, 4th Block, Jayanagar, Bengaluru 560011"
            autoComplete="street-address"
            className={field.input}
            aria-invalid={!!fields.address}
          />
        </label>
      </div>

      <fieldset className="border-0 p-0">
        <legend className={field.legend}>Facilities</legend>
        <div className="flex flex-wrap gap-2">
          {FACILITIES.map((f) => {
            const on = facilities.includes(f);
            return (
              <label
                key={f}
                className={cn(
                  "cursor-pointer rounded-chip border px-3 py-1.5 text-sm font-medium has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-amber",
                  on ? "border-ink bg-ink text-paper" : "border-ink/25 text-ink-2 hover:border-ink/60",
                )}
              >
                <input
                  type="checkbox"
                  checked={on}
                  onChange={() => setFacilities((xs) => (on ? xs.filter((x) => x !== f) : [...xs, f]))}
                  className="sr-only"
                />
                {f}
              </label>
            );
          })}
        </div>
      </fieldset>

      <fieldset className="border-0 p-0">
        <legend className={field.legend}>Photo (optional)</legend>
        <div className="grid max-w-[420px] grid-cols-3 gap-2">
          <PhotoChoice checked={photo === null} onChange={() => setPhoto(null)} label="No photo">
            <span className="grid size-full place-items-center text-xs text-ink-2">None</span>
          </PhotoChoice>
          {PHOTOS.map((p) => (
            <PhotoChoice key={p.src} checked={photo === p.src} onChange={() => setPhoto(p.src)} label={p.alt}>
              <Image src={p.src} alt="" fill sizes="140px" className="object-cover" />
            </PhotoChoice>
          ))}
        </div>
        <span className={cn(field.hint, "mt-1.5 block")}>From the CC photo library; your own photos arrive with uploads in a later version.</span>
      </fieldset>

      <FormError message={error} />
      {saved && (
        <p role="status" className="rounded-btn bg-mint/15 px-3 py-2 text-sm font-medium text-[#1f6e57]">
          Saved.
        </p>
      )}
      <Button type="submit" disabled={busy} className="w-full sm:w-auto sm:justify-self-start">
        {busy ? "Saving…" : cinema ? "Save cinema" : "Add cinema"}
      </Button>
    </form>
  );
}

function PhotoChoice({ checked, onChange, label, children }: { checked: boolean; onChange: () => void; label: string; children: React.ReactNode }) {
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
