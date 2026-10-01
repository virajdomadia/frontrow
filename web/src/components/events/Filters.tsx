"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { DATE_PRESETS, eventsHref, type FilterKey, type Filters } from "@/lib/filters";
import { cn } from "@/lib/utils";

type Option = { value: string; label: string; count?: number };

const chip =
  "inline-flex items-center gap-1.5 rounded-btn border border-screen/20 px-3 py-[7px] text-sm font-medium whitespace-nowrap text-muted-foreground no-underline transition-colors hover:border-screen/50 hover:text-screen";
const chipOn = "border-screen bg-screen font-semibold text-plum hover:border-screen hover:text-plum";

/** The S2 filter bar. Every control writes the URL; the page re-renders on the server. */
export function Filters({
  current,
  genres,
  venues,
  today,
}: {
  current: Filters;
  genres: Option[];
  venues: Option[];
  /** IST date, YYYY-MM-DD — the date picker's minimum. */
  today: string;
}) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const go = (patch: Filters) => start(() => router.push(eventsHref(current, patch), { scroll: false }));
  const isDay = current.date && /^\d{4}-/.test(current.date);

  return (
    <div
      className={cn("mt-5 flex flex-wrap items-center gap-2 transition-opacity", pending && "opacity-60")}
      aria-busy={pending}
    >
      <div role="group" aria-label="When" className="flex flex-wrap gap-2">
        <Link
          href={eventsHref(current, { date: undefined })}
          scroll={false}
          aria-current={!current.date ? "true" : undefined}
          className={cn(chip, !current.date && chipOn)}
        >
          Any day
        </Link>
        {DATE_PRESETS.map((p) => (
          <Link
            key={p.value}
            href={eventsHref(current, { date: p.value })}
            scroll={false}
            aria-current={current.date === p.value ? "true" : undefined}
            className={cn(chip, current.date === p.value && chipOn)}
          >
            {p.label}
          </Link>
        ))}
        <label className={cn(chip, "relative cursor-pointer pr-2", isDay && chipOn)}>
          <span className="sr-only">Pick a date</span>
          <input
            type="date"
            min={today}
            value={isDay ? current.date : ""}
            onChange={(e) => go({ date: e.target.value || undefined })}
            className="w-[8.2rem] bg-transparent text-inherit [color-scheme:dark]"
          />
        </label>
      </div>

      <span aria-hidden="true" className="mx-1.5 hidden h-6 w-px bg-screen/15 sm:block" />

      <Select
        label="Type"
        name="type"
        value={current.type}
        placeholder="All types"
        options={[
          { value: "movie", label: "Movies" },
          { value: "concert", label: "Concerts" },
        ]}
        onChange={go}
      />
      <Select label="Genre" name="genre" value={current.genre} placeholder="Any genre" options={genres} onChange={go} />
      <Select label="Venue" name="venue" value={current.venue} placeholder="Any venue" options={venues} onChange={go} />
      <div className="sm:ml-auto">
        <Select
          label="Sort"
          name="sort"
          value={current.sort ?? "soonest"}
          options={[
            { value: "soonest", label: "Sort: soonest" },
            { value: "price", label: "Sort: price" },
            { value: "title", label: "Sort: A–Z" },
          ]}
          onChange={go}
        />
      </div>
    </div>
  );
}

function Select({
  label,
  name,
  value,
  placeholder,
  options,
  onChange,
}: {
  label: string;
  name: FilterKey;
  value?: string;
  placeholder?: string;
  options: Option[];
  onChange: (patch: Filters) => void;
}) {
  const on = Boolean(value) && name !== "sort";
  // A value from the URL that today's facets don't list (e.g. a genre with no shows that day)
  // stays selectable, so the control never claims "Any" while a filter is applied.
  const all = value && !options.some((o) => o.value === value) ? [...options, { value, label: value, count: 0 }] : options;
  return (
    <label className={cn(chip, "relative pr-7", on && chipOn)}>
      <span className="sr-only">{label}</span>
      <select
        name={name}
        value={value ?? ""}
        onChange={(e) => onChange({ [name]: e.target.value || undefined })}
        className="cursor-pointer appearance-none bg-transparent text-inherit [&>option]:bg-plum-2 [&>option]:text-screen"
      >
        {placeholder && <option value="">{placeholder}</option>}
        {all.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
            {o.count != null ? ` (${o.count})` : ""}
          </option>
        ))}
      </select>
      <svg aria-hidden="true" viewBox="0 0 10 6" className="pointer-events-none absolute right-2.5 size-2.5 opacity-70">
        <path d="M1 1l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.6" />
      </svg>
    </label>
  );
}
