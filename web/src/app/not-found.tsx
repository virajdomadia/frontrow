import Link from "next/link";
import { SiteFooter, SiteHeader } from "@/components/site/SiteHeader";
import { buttonVariants } from "@/components/ui/button";

export default function NotFound() {
  return (
    <>
      <SiteHeader />
      <main className="mx-auto grid w-[min(1240px,100%-32px)] justify-items-start gap-4 pt-16">
        <p className="font-cond text-xl font-bold tracking-[.14em] text-amber uppercase">Row Z · Seat 404</p>
        <h1 className="font-cond text-[clamp(40px,6vw,64px)] leading-[.95] font-extrabold uppercase">
          This seat doesn&apos;t exist
        </h1>
        <p className="max-w-[48ch] text-muted-foreground">
          The show may have ended or the link is mistyped. Everything that&apos;s on is one click away.
        </p>
        <Link href="/events" className={buttonVariants()}>
          See what&apos;s on
        </Link>
      </main>
      <SiteFooter />
    </>
  );
}
