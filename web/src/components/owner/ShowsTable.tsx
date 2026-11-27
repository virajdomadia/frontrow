import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { rupees } from "@/lib/format";
import type { OwnerShow } from "@/lib/types";
import { clock } from "./format";
import { FillBar, StatusBadge } from "./ui";

/** One day's shows: time, film, version, screen, fill, revenue, public or not, Bookings + Door. */
export function ShowsTable({ shows, now = Date.now() }: { shows: OwnerShow[]; now?: number }) {
  return (
    <div className="overflow-x-auto rounded-card border border-border bg-plum-2">
      <table className="w-full min-w-[860px] border-collapse text-left text-sm">
        <caption className="sr-only">Shows, earliest first</caption>
        <thead>
          <tr className="border-b border-border text-xs tracking-[.08em] text-ink-2 uppercase">
            <th scope="col" className="px-4 py-3 font-semibold">Time</th>
            <th scope="col" className="px-4 py-3 font-semibold">Film</th>
            <th scope="col" className="px-4 py-3 font-semibold">Screen</th>
            <th scope="col" className="px-4 py-3 font-semibold">Sold</th>
            <th scope="col" className="px-4 py-3 text-right font-semibold">Revenue</th>
            <th scope="col" className="px-4 py-3 font-semibold">Status</th>
            <th scope="col" className="px-4 py-3"><span className="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          {shows.map((s) => {
            const played = new Date(s.ends_at).getTime() < now;
            return (
              <tr key={s.id} className="border-b border-border last:border-0">
                <td className="px-4 py-3 font-cond text-2xl font-bold tabular-nums">{clock(s.starts_at)}</td>
                <td className="px-4 py-3">
                  <b className="block font-semibold">{s.film.title}</b>
                  <span className="text-xs text-ink-2">
                    {s.language} · {s.format}
                  </span>
                </td>
                <td className="px-4 py-3 text-ink-2">
                  {s.cinema_name}
                  <span className="block text-xs text-ink-3">{s.screen_name}</span>
                </td>
                <td className="px-4 py-3">
                  <FillBar sold={s.sold} total={s.seat_count} className="w-[150px]" />
                  {s.checked_in > 0 && <span className="text-xs text-ink-3">{s.checked_in} scanned in</span>}
                </td>
                <td className="px-4 py-3 text-right font-semibold tabular-nums">{rupees(s.revenue_paise)}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={s.status === "cancelled" ? "cancelled" : played ? "past" : s.public ? "public" : "private"} />
                </td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-2">
                    <Link href={`/owner/shows/${s.id}/bookings`} className={buttonVariants({ variant: "paper", size: "sm" })}>
                      Bookings
                    </Link>
                    <Link href={`/owner/checkin/${s.id}`} className={buttonVariants({ variant: "paper", size: "sm" })}>
                      Door
                    </Link>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
