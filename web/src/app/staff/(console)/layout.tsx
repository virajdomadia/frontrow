import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { SiteHeader } from "@/components/site/SiteHeader";
import { staffCounts, staffMe } from "@/components/staff/session";
import { DemoNotice } from "@/components/staff/ui";
import { buttonVariants } from "@/components/ui/button";

export const metadata: Metadata = { title: { default: "Staff", template: "%s · Staff · Frontrow" }, robots: { index: false, follow: false } };

/** The staff console shell: staff only; demo staff see everything with decisions switched off. */
export default async function StaffConsoleLayout({ children }: { children: React.ReactNode }) {
  const me = await staffMe();
  if (!me) redirect("/staff");
  if (!me.is_staff)
    return (
      <>
        <SiteHeader />
        <main id="main" className="mx-auto grid w-[min(1240px,100%-32px)] justify-items-start gap-4 py-16">
          <h1 className="font-cond text-[clamp(36px,6vw,60px)] leading-[.95] font-extrabold uppercase">This area is for Frontrow staff</h1>
          <p className="max-w-[50ch] text-muted-foreground">
            You&apos;re signed in as {me.email}, which isn&apos;t a staff account. Your tickets and cinemas are where they always are.
          </p>
          <Link href="/" className={buttonVariants()}>
            Back to Frontrow
          </Link>
        </main>
      </>
    );

  const counts = await staffCounts();
  const nav = [
    { key: "approvals", href: "/staff/businesses?status=pending", label: `Approvals (${counts.pending_businesses})` },
    { key: "requests", href: "/staff/requests", label: `Film requests (${counts.open_requests})` },
    { key: "films", href: "/staff/films", label: `Film catalogue (${counts.films})` },
  ];
  return (
    <>
      <SiteHeader nav={nav} badge="Staff" wide />
      <main id="main" className="mx-auto w-[min(1280px,100%-32px)] lg:w-[min(1280px,100%-64px)] py-8">
        {me.is_demo && <DemoNotice />}
        {children}
      </main>
    </>
  );
}
