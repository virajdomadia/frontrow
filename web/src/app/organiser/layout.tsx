import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { ConsoleNav } from "@/components/organiser/ConsoleNav";
import { AccountLinks } from "@/components/site/AccountLinks";
import { Logo } from "@/components/site/Logo";
import { buttonVariants } from "@/components/ui/button";
import { getMe } from "@/lib/session";

// Every console page reads the organiser's own data with their cookie — never cached.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: { default: "Organiser console", template: "%s · Organiser · Frontrow" },
  robots: { index: false },
};

/** R7/R8 guard: signed out → sign in and come back; a customer gets a friendly dead end. */
export default async function OrganiserLayout({ children }: { children: React.ReactNode }) {
  const me = await getMe();
  if (!me) redirect("/sign-in?next=/organiser");

  if (me.role !== "organiser")
    return (
      <>
        <header className="border-b border-border">
          <div className="mx-auto flex w-[min(1240px,100%-32px)] items-center justify-between gap-4 py-4">
            <Logo />
            <AccountLinks className="text-[15px] font-medium" />
          </div>
        </header>
        <main className="mx-auto grid w-[min(1240px,100%-32px)] justify-items-start gap-4 pt-16 pb-20">
          <p className="font-cond text-xl font-bold tracking-[.14em] text-amber uppercase">Staff only · Backstage</p>
          <h1 className="font-cond text-[clamp(40px,6vw,64px)] leading-[.95] font-extrabold uppercase">
            The console is for organisers
          </h1>
          <p className="max-w-[52ch] text-muted-foreground">
            You&apos;re signed in as {me.name}, a customer account. To run venues and sell shows, sign out and
            create an organiser account — or try the demo organiser from the sign-in page.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link href="/my-tickets" className={buttonVariants()}>
              My tickets
            </Link>
            <Link href="/sign-up" className={buttonVariants({ variant: "outline" })}>
              Create an organiser account
            </Link>
          </div>
        </main>
      </>
    );

  return (
    <>
      <header className="border-b border-border bg-plum">
        <div className="mx-auto w-[min(1240px,100%-32px)]">
          <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 pt-4">
            <div className="flex items-center gap-3">
              <Logo />
              <span className="rounded-sm bg-red px-2 py-0.5 font-cond text-sm font-bold tracking-[.12em] text-white uppercase">
                Organiser
              </span>
            </div>
            <div className="flex items-center gap-5 text-[15px] font-medium">
              <span className="hidden text-screen md:inline">{me.name}</span>
              <Link href="/events" className="text-muted-foreground no-underline hover:text-screen">
                Public site
              </Link>
              <AccountLinks />
            </div>
          </div>
          <div className="mt-2">
            <ConsoleNav />
          </div>
        </div>
      </header>
      <main className="mx-auto w-[min(1240px,100%-32px)] pt-8 pb-20">{children}</main>
    </>
  );
}
