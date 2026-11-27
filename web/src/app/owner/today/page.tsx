import { TodayBoard } from "@/components/owner/TodayBoard";
import { api } from "@/lib/api";
import { getMe } from "@/lib/session";

export const metadata = { title: "Today" };

/** L3 · The Today board: every show today, live sales, and the live map with blocked seats. */
export default async function TodayPage() {
  const [today, me] = await Promise.all([api("/owner/today", { auth: true }), getMe()]);
  return <TodayBoard initial={today} demo={Boolean(me?.is_demo)} />;
}
