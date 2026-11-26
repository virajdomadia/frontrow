import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { AuthPage } from "@/components/auth/AuthPage";
import { BusinessForm } from "@/components/owner/BusinessForm";
import { SiteHeader } from "@/components/site/SiteHeader";
import { getMe } from "@/lib/session";

export const metadata: Metadata = { title: "Register your business", robots: { index: false } };

/**
 * O2 · register. Signed out: the business door (email → code → business details). Signed in
 * without a business: just the details — one email is one person, the account stays the same.
 */
export default async function RegisterPage() {
  const me = await getMe();
  if (!me) return <AuthPage door="business" heading="Register your business" />;
  if (me.businesses.length) redirect("/owner");
  return (
    <>
      <SiteHeader active="business" />
      <main className="mx-auto grid w-[min(1180px,100%-32px)] content-start gap-10 py-10 lg:grid-cols-[1fr_440px] lg:gap-16 lg:py-16">
        <div className="grid content-start gap-5">
          <h1 className="font-cond text-[clamp(44px,7vw,88px)] leading-[.92] font-extrabold uppercase">Register your business</h1>
          <p className="max-w-[44ch] text-lg text-muted-foreground">
            You&apos;re signed in as {me.name} ({me.email}). Add your business to this account — you&apos;ll keep booking
            tickets with it too.
          </p>
          <p className="max-w-[44ch] text-[15px] text-ink-2">
            Your business starts as <b>pending verification</b>: set up cinemas, screens and shows straight away; they go
            public once Frontrow staff approve you.
          </p>
        </div>
        <div className="fr-stub p-6 shadow-[0_18px_40px_rgb(42_11_30_/_.12)] sm:p-8">
          <h2 className="mb-5 font-cond text-3xl font-extrabold uppercase">Business details</h2>
          <BusinessForm mode="register" />
        </div>
      </main>
    </>
  );
}
