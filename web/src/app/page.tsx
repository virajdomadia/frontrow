import Link from "next/link";
import { DemoButtons } from "@/components/auth/DemoButtons";
import { TryItLive } from "@/components/landing/TryItLive";
import { FilmCard } from "@/components/movies/FilmCard";
import { SearchBox } from "@/components/movies/SearchBox";
import { SiteFooter, SiteHeader } from "@/components/site/SiteHeader";
import { buttonVariants } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Home as HomeData } from "@/lib/types";
import { cn } from "@/lib/utils";

export const revalidate = 60;

// A still of the seat map for the hero: free seats in tier colours, a few sold, someone else's
// holds in grey, and "your" two in red.
const ROWS = 7;
const COLS = 14;
function look(r: number, c: number) {
  if (r === 4 && (c === 6 || c === 7)) return "bg-red shadow-[0_0_0_3px_rgb(201_45_58_/_.25)]";
  if ((r * 7 + c * 3) % 11 === 0 || (r === 1 && c > 9)) return "bg-plum-3 outline outline-1 -outline-offset-1 outline-ink/20";
  if ((r + c * 5) % 13 === 0) return "bg-held";
  return r < 4 ? "bg-classic/80" : r < 6 ? "bg-prime/85" : "bg-recliner/80";
}

/** C1 · Home: what Frontrow is, search, Now showing, Coming soon, demo buttons for all roles. */
export default async function Home() {
  // At build time (CI) there is no api: render an empty strip and let ISR fill it within a minute.
  const home = await api("/home", { revalidate: 60, tags: ["home"] }).catch((): HomeData => ({ now_showing: [], coming_soon: [] }));
  return (
    <>
      <SiteHeader />
      <main id="main">
        <section className="mx-auto grid w-[min(1240px,100%-32px)] items-center gap-10 pt-8 pb-12 lg:grid-cols-[1.1fr_.9fr] lg:pt-14">
          <div className="grid gap-5">
            <p className="font-cond text-[15px] font-semibold tracking-[.14em] text-red-dark uppercase">Movie tickets · Bengaluru</p>
            <h1 className="font-cond text-[clamp(52px,8.5vw,112px)] leading-[.88] font-extrabold uppercase">
              Pick your seat, <span className="text-red">live.</span>
            </h1>
            <p className="max-w-[46ch] text-lg text-muted-foreground">
              Tap a seat and it&apos;s <strong className="font-semibold text-ink">held for you for ten minutes</strong>, greyed out for
              everyone else until you pay. Your M-ticket is scanned at the door.
            </p>
            <SearchBox className="max-w-[520px]" />
            <div className="grid max-w-[680px] gap-2 pt-1">
              <p className="text-xs font-semibold tracking-[.12em] text-ink-2 uppercase">Look around in one click — no email needed</p>
              <DemoButtons />
            </div>
          </div>
          <div aria-hidden="true" className="fr-stub p-4 shadow-[0_24px_50px_rgb(42_11_30_/_.14)] sm:p-6">
            <div className="mx-[12%] mb-1 h-1.5 rounded-full bg-gradient-to-r from-transparent via-ink/60 to-transparent" />
            <p className="mb-5 text-center font-cond text-xs tracking-[.3em] text-ink-3 uppercase">Screen</p>
            <div className="grid gap-[5px] sm:gap-[7px]">
              {Array.from({ length: ROWS }, (_, r) => (
                <div key={r} className="flex justify-center gap-[4px] sm:gap-[6px]">
                  {Array.from({ length: COLS }, (_, c) => (
                    <span key={c} className={cn("h-3 w-3.5 rounded-[3px_3px_2px_2px] sm:h-[18px] sm:w-[20px]", look(r, c), c === 6 && "mr-2 sm:mr-3")} />
                  ))}
                </div>
              ))}
            </div>
            <div className="mt-5 flex items-center justify-between rounded-btn bg-paper-2 px-4 py-3">
              <span className="text-sm text-ink-2">
                <b className="font-cond text-xl text-ink">E7, E8</b> held for you
              </span>
              <span className="font-mono text-2xl font-semibold text-red-dark tabular-nums">09:41</span>
            </div>
            <div className="mt-4 flex flex-wrap justify-center gap-4 text-xs text-ink-2">
              <span className="flex items-center gap-1.5"><i className="inline-block h-3 w-3.5 rounded-sm bg-classic/80" />Free</span>
              <span className="flex items-center gap-1.5"><i className="inline-block h-3 w-3.5 rounded-sm bg-held" />Someone&apos;s holding</span>
              <span className="flex items-center gap-1.5"><i className="inline-block h-3 w-3.5 rounded-sm bg-plum-3 outline outline-1 -outline-offset-1 outline-ink/20" />Sold</span>
              <span className="flex items-center gap-1.5"><i className="inline-block h-3 w-3.5 rounded-sm bg-red" />Yours</span>
            </div>
          </div>
        </section>

        <section aria-labelledby="now" className="mx-auto w-[min(1240px,100%-32px)] py-8">
          <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
            <h2 id="now" className="font-cond text-[clamp(34px,4.5vw,56px)] font-extrabold uppercase">
              Now showing
            </h2>
            <Link href="/movies" className="text-sm font-semibold text-ink underline underline-offset-4">
              All movies
            </Link>
          </div>
          {home.now_showing.length ? (
            // Four films fill four columns, not four fifths of five.
            <div className={cn("grid grid-cols-2 gap-x-5 gap-y-8 sm:grid-cols-3", home.now_showing.length === 4 ? "lg:grid-cols-4" : "lg:grid-cols-5")}>
              {home.now_showing.map((f, i) => (
                <FilmCard key={f.id} film={f} priority={i < 5} />
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground">No shows on sale right now. Check back in a minute.</p>
          )}
        </section>

        {home.coming_soon.length > 0 && (
          <section aria-labelledby="soon" className="mx-auto w-[min(1240px,100%-32px)] py-8">
            <h2 id="soon" className="mb-6 font-cond text-[clamp(30px,4vw,48px)] font-extrabold uppercase">
              Coming soon
            </h2>
            <div className="grid grid-cols-2 gap-x-5 gap-y-8 sm:grid-cols-3 lg:grid-cols-5">
              {home.coming_soon.map((f) => (
                <FilmCard key={f.id} film={f} />
              ))}
            </div>
          </section>
        )}

        <section aria-labelledby="how" className="mt-10 bg-plum-2 py-14">
          <div className="mx-auto w-[min(1240px,100%-32px)]">
            <h2 id="how" className="font-cond text-[clamp(34px,4.5vw,56px)] font-extrabold uppercase">
              Try it live
            </h2>
            <p className="mt-3 mb-8 max-w-[60ch] text-muted-foreground">
              Two people, one hall. Tap a seat on either map and watch it grey out on the other, pushed by the same engine that
              holds real tickets. Two people can never hold the same seat.
            </p>
            <TryItLive />
          </div>
        </section>

        <section aria-labelledby="cinemas" className="mx-auto mt-14 w-[min(1240px,100%-32px)]">
          <div className="grid items-center gap-6 rounded-card bg-oxblood px-6 py-10 text-oxblood-ink sm:px-10 lg:grid-cols-[1fr_auto]">
            <div>
              <h2 id="cinemas" className="font-cond text-[clamp(32px,4vw,52px)] font-extrabold text-white uppercase">
                Run a cinema?
              </h2>
              <p className="mt-2 max-w-[56ch] text-oxblood-ink/85">
                Set up your screens from templates, pick films from the shared catalogue and schedule a month of shows in one go.
                Your box office and the website sell from the same live map.
              </p>
            </div>
            <Link href="/business" className={buttonVariants({ variant: "paper", size: "lg" })}>
              Frontrow for cinemas
            </Link>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
