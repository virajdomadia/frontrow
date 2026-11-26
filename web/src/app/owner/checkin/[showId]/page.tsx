import Link from "next/link";
import { notFound } from "next/navigation";
import { DoorScanner } from "@/components/owner/DoorScanner";
import { dateTime } from "@/components/owner/format";
import { PageHead } from "@/components/owner/ui";
import { api, ApiRequestError } from "@/lib/api";

export const metadata = { title: "Door" };

type Props = { params: Promise<{ showId: string }> };

/** O9 · scan at the door (B10). */
export default async function DoorPage({ params }: Props) {
  const { showId } = await params;
  let data;
  try {
    data = await api("/owner/shows/{show_id}/bookings", { params: { show_id: showId }, auth: true });
  } catch (e) {
    if (e instanceof ApiRequestError && e.status === 404) notFound();
    throw e;
  }
  const { show } = data;
  return (
    <>
      <PageHead
        title={`Door · ${show.film.title}`}
        sub={`${dateTime(show.starts_at)} · ${show.cinema_name} · ${show.screen_name}`}
        back={{ href: `/owner/shows/${show.id}/bookings`, label: "Bookings" }}
      />
      <DoorScanner showId={show.id} initialAdmitted={show.checked_in} sold={show.sold} />
      <p className="mt-8 text-sm text-ink-3">
        Testing without a phone? Open a booking&apos;s M-ticket as the customer (
        <Link href="/my-tickets" className="underline underline-offset-4">
          My tickets
        </Link>
        ) and paste the code printed under its QR.
      </p>
    </>
  );
}
