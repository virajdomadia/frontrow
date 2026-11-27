import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { BusinessForm } from "@/components/owner/BusinessForm";
import { OwnerHeader } from "@/components/owner/OwnerHeader";
import { api } from "@/lib/api";
import { getMe } from "@/lib/session";

// Every console page reads the owner's own data with their cookie — never cached.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: { default: "Cinema console", template: "%s · Cinema console · Frontrow" },
  robots: { index: false },
};

/**
 * The theatre owner's console (B8–B10). Signed out → the business door; an account without a
 * business → register one. Pending and rejected businesses see why nothing is public yet.
 */
export default async function OwnerLayout({ children }: { children: React.ReactNode }) {
  const me = await getMe();
  if (!me) redirect("/business/sign-in?next=/owner");
  if (!me.businesses.length) redirect("/business/register");
  const business = await api("/owner/business", { auth: true });

  return (
    <>
      <OwnerHeader business={business.name} />
      {me.is_demo && (
        <p role="note" className="mx-auto mt-4 w-[min(1280px,100%-32px)] rounded-card border border-amber/40 bg-amber/10 px-4 py-3 text-sm text-ink lg:w-[min(1280px,100%-64px)]">
          <b>You&apos;re the demo theatre owner.</b> {business.name} is a live, public cinema, so the demo can look but not
          save: every form opens, and saving says why it can&apos;t. Customers&apos; names and emails are masked.
        </p>
      )}
      {business.status === "pending" && (
        <div role="status" className="mx-auto mt-4 w-[min(1280px,100%-32px)] lg:w-[min(1280px,100%-64px)] rounded-card border border-amber/40 bg-amber/10 px-4 py-3 text-[15px]">
          <b className="font-semibold text-ink">Pending verification.</b>{" "}
          <span className="text-ink-2">
            Build everything now — cinemas, screens, shows. Nothing is public until Frontrow staff approve {business.name}; we
            usually call {business.phone} within a working day.
          </span>
        </div>
      )}
      {business.status === "rejected" && (
        <div role="alert" className="mx-auto mt-4 grid w-[min(1280px,100%-32px)] lg:w-[min(1280px,100%-64px)] gap-4 rounded-card border border-red/40 bg-red/5 px-4 py-4 md:grid-cols-[1fr_380px]">
          <div className="grid content-start gap-1.5">
            <b className="font-cond text-2xl font-bold uppercase text-red-dark">Not approved yet</b>
            <p className="text-[15px] text-ink-2">
              Frontrow staff said: <q className="font-medium text-ink">{business.review_note ?? "No reason given."}</q>
            </p>
            <p className="text-sm text-ink-3">Fix your details and send them again — you go straight back into the review queue.</p>
          </div>
          <BusinessForm mode="resubmit" initial={{ name: business.name, phone: business.phone }} />
        </div>
      )}
      {business.status === "suspended" && (
        <div role="alert" className="mx-auto mt-4 w-[min(1280px,100%-32px)] lg:w-[min(1280px,100%-64px)] rounded-card border border-red/40 bg-red/5 px-4 py-3 text-[15px] text-ink-2">
          <b className="text-red-dark">Suspended.</b> Your shows are hidden from customers; existing tickets still work. Contact
          Frontrow support.
        </div>
      )}
      <main id="main" className="mx-auto w-[min(1280px,100%-32px)] lg:w-[min(1280px,100%-64px)] pt-8 pb-20">{children}</main>
    </>
  );
}
