import type { Metadata } from "next";
import Link from "next/link";
import { SiteFooter, SiteHeader } from "@/components/site/SiteHeader";
import { buttonVariants } from "@/components/ui/button";

// Placeholder until F1 renders the seat map here (docs/07-plan.md, milestone 1.1).
export const metadata: Metadata = { title: "Pick your seats", robots: { index: false } };

export default function BookPage() {
  return (
    <>
      <SiteHeader />
      <main className="mx-auto grid w-[min(1240px,100%-32px)] justify-items-start gap-4 pt-16">
        <h1 className="font-cond text-[clamp(40px,6vw,64px)] leading-[.95] font-extrabold uppercase">
          The seat map opens <span className="text-red">soon</span>
        </h1>
        <p className="max-w-[52ch] text-muted-foreground">
          Seat selection with live ten-minute holds is the next part of Frontrow being built. Until then you can browse
          every show and showtime.
        </p>
        <Link href="/events" className={buttonVariants()}>
          Back to shows
        </Link>
      </main>
      <SiteFooter />
    </>
  );
}
