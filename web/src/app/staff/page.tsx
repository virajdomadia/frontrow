import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { AuthPage } from "@/components/auth/AuthPage";
import { staffMe } from "@/components/staff/session";

export const metadata: Metadata = { title: "Staff", robots: { index: false, follow: false } };

/** T1 · the hidden staff door (R1): seeded staff accounts only; same answer for any email. */
export default async function StaffDoor() {
  const me = await staffMe();
  if (me?.is_staff) redirect("/staff/businesses?status=pending");
  return <AuthPage door="staff" next="/staff/businesses?status=pending" />;
}
