import type { Metadata } from "next";
import Link from "next/link";
import { DemoButtons } from "@/components/auth/DemoButtons";
import { SiteFooter, SiteHeader } from "@/components/site/SiteHeader";
import { buttonVariants } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "For cinemas",
  description: "Sell your cinema's shows on Frontrow: screens from templates, a month of shows in one go, a live seat map shared with your box office, and QR scanning at the door.",
};

const STEPS = [
  { n: "1", title: "Register", body: "Sign in with your email and tell us your business name and phone. You can build everything straight away." },
  { n: "2", title: "Cinemas & screens", body: "Add each cinema, then its screens from a template — a multiplex grid or stalls + balcony — with a live seat-map preview." },
  { n: "3", title: "Schedule shows", body: "Pick films from the shared catalogue, then a language, format, days, times and a price per tier. A month of shows in one go; overlaps are refused." },
  { n: "4", title: "Go live", body: "Frontrow staff verify you once. Your shows appear on every film's page, and the door page scans M-tickets on any phone." },
];

/** O1 · the business door: what a cinema gets, how to start, and the demo owner. */
export default function BusinessPage() {
  return (
    <>
      <SiteHeader active="business" />
      <main className="mx-auto w-[min(1240px,100%-32px)] pt-10 pb-6 lg:pt-16">
        <section className="grid items-end gap-8 lg:grid-cols-[1.2fr_.8fr]">
          <div className="grid gap-5">
            <p className="font-cond text-lg font-bold tracking-[.14em] text-red-dark uppercase">For cinemas in Bengaluru</p>
            <h1 className="font-cond text-[clamp(48px,8vw,104px)] leading-[.9] font-extrabold uppercase">
              Fill your seats. <span className="text-red">Live.</span>
            </h1>
            <p className="max-w-[48ch] text-lg text-muted-foreground">
              Frontrow sells your shows on a live seat map: a seat a customer taps is held for ten minutes and greys out for
              everyone else, so two people can never buy the same seat.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href="/business/register" className={buttonVariants({ size: "lg" })}>
                Register your cinema
              </Link>
              <Link href="/business/sign-in" className={buttonVariants({ variant: "outline", size: "lg" })}>
                Business sign-in
              </Link>
            </div>
          </div>
          <div className="fr-stub grid gap-3 p-5 sm:p-6">
            <h2 className="font-cond text-2xl font-extrabold uppercase">Look around first</h2>
            <p className="text-sm text-ink-2">
              Sign in as the owner of Orbit Cinemas — two cinemas, three screens, a fortnight of shows and real bookings —
              no email needed.
            </p>
            <DemoButtons only="owner" />
          </div>
        </section>

        <section aria-labelledby="how" className="mt-16">
          <h2 id="how" className="font-cond text-[clamp(32px,4vw,48px)] font-extrabold uppercase">
            From sign-up to a bookable show
          </h2>
          <ol className="mt-6 grid list-none gap-4 p-0 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((s) => (
              <li key={s.n} className="rounded-card border border-border bg-plum-2 p-5">
                <span className="font-cond text-4xl font-extrabold text-red">{s.n}</span>
                <h3 className="mt-2 font-cond text-2xl font-bold uppercase">{s.title}</h3>
                <p className="mt-2 text-[15px] text-muted-foreground">{s.body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="mt-16 grid gap-4 md:grid-cols-3">
          {[
            ["One map, no double-sells", "Seats are held in Redis for ten minutes and sold under a database guard — a seat sells exactly once."],
            ["Bookings and CSV", "Every paid booking per show — who, which seats, how much — with a CSV export for your accounts."],
            ["Scan at the door", "Ushers open the door page on any phone and scan M-ticket QR codes; a ticket gets in once."],
          ].map(([t, b]) => (
            <div key={t} className="border-t-2 border-ink pt-4">
              <h3 className="font-cond text-xl font-bold uppercase">{t}</h3>
              <p className="mt-1.5 text-[15px] text-muted-foreground">{b}</p>
            </div>
          ))}
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
