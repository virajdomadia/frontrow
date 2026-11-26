import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { AuthPage } from "@/components/auth/AuthPage";
import { safeNext } from "@/lib/client";
import { getMe } from "@/lib/session";

export const metadata: Metadata = { title: "Sign in", robots: { index: false } };

type Props = { searchParams: Promise<{ next?: string | string[] }> };

export default async function SignPage({ searchParams }: Props) {
  const raw = (await searchParams).next;
  const next = typeof raw === "string" ? raw : undefined;
  const me = await getMe();
  if (me) redirect(safeNext(next, me.role === "organiser" ? "/organiser" : "/events"));
  return (
    <main>
      <AuthPage mode="sign-in" next={next} />
    </main>
  );
}
