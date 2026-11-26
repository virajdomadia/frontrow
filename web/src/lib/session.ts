import { redirect } from "next/navigation";
import { api, ApiRequestError } from "./api";
import type { Me } from "./types";

/** The signed-in user for this request (reads the viewer's cookie; the page becomes dynamic). */
export async function getMe(): Promise<Me | null> {
  try {
    return await api("/auth/me", { auth: true });
  } catch (e) {
    if (e instanceof ApiRequestError && e.status === 401) return null;
    throw e;
  }
}

/** Signed in, or off to sign in and back here afterwards (R7). */
export async function requireMe(next: string): Promise<Me> {
  const me = await getMe();
  if (!me) redirect(`/sign-in?next=${encodeURIComponent(next)}`);
  return me;
}
