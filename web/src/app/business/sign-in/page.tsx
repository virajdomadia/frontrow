import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { AuthPage } from "@/components/auth/AuthPage";
import { safeNext } from "@/lib/client";
import { getMe } from "@/lib/session";

export const metadata: Metadata = { title: "Business sign-in", robots: { index: false } };

type Props = { searchParams: Promise<{ next?: string | string[] }> };

/** O2 · business door: email → code; a new email registers a business on the way. */
export default async function BusinessSignInPage({ searchParams }: Props) {
  const raw = (await searchParams).next;
  const next = typeof raw === "string" ? raw : undefined;
  const me = await getMe();
  if (me) redirect(me.businesses.length ? safeNext(next, "/owner") : "/business/register");
  return <AuthPage door="business" next={next} heading="Business sign-in" />;
}
