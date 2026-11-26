import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { AuthPage } from "@/components/auth/AuthPage";
import { safeNext } from "@/lib/client";
import { getMe } from "@/lib/session";

export const metadata: Metadata = { title: "Sign in", robots: { index: false } };

type Props = { searchParams: Promise<{ next?: string | string[] }> };

/** C7 · the customer door: email → code → name if new. */
export default async function SignInPage({ searchParams }: Props) {
  const raw = (await searchParams).next;
  const next = typeof raw === "string" ? raw : undefined;
  if (await getMe()) redirect(safeNext(next, "/"));
  return <AuthPage door="customer" next={next} />;
}
