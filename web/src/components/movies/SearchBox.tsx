import { Search } from "lucide-react";
import { cn } from "@/lib/utils";

/** Search by film title or genre — a plain GET form to /movies, so it works without JS. */
export function SearchBox({ defaultValue, className }: { defaultValue?: string; className?: string }) {
  return (
    <form action="/movies" role="search" className={cn("flex", className)}>
      <label className="relative flex-1">
        <span className="sr-only">Search movies</span>
        <Search aria-hidden="true" className="pointer-events-none absolute top-1/2 left-3.5 size-5 -translate-y-1/2 text-ink-3" />
        <input
          type="search"
          name="q"
          defaultValue={defaultValue}
          maxLength={60}
          placeholder="Search movies, e.g. Neon Alley or comedy"
          className="w-full rounded-l-btn border border-r-0 border-ink/25 bg-white/85 py-3 pr-3 pl-11 text-[16px] text-ink placeholder:text-ink-3 focus-visible:border-ink focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-amber"
        />
      </label>
      <button
        type="submit"
        className="cursor-pointer rounded-r-btn bg-ink px-5 font-cond text-lg font-bold tracking-[.05em] text-paper uppercase hover:bg-[#3A1230]"
      >
        Search
      </button>
    </form>
  );
}
