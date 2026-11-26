import { ShowtimeForm } from "@/components/organiser/ShowtimeForm";
import { PageHead } from "@/components/organiser/ui";
import { api } from "@/lib/api";

export const metadata = { title: "New showtime" };

type Props = { searchParams: Promise<{ event_id?: string; venue_id?: string }> };

export default async function NewShowtimePage({ searchParams }: Props) {
  const { event_id, venue_id } = await searchParams;
  const [events, venues] = await Promise.all([
    api("/organiser/events", { auth: true }),
    api("/organiser/venues", { auth: true }),
  ]);
  return (
    <>
      <PageHead
        title="New showtime"
        sub="Pick the event, the venue, when it starts and what each tier costs. It goes on sale at once."
        back={{ href: "/organiser/showtimes", label: "Showtimes" }}
      />
      <ShowtimeForm events={events} venues={venues} eventId={event_id} venueId={venue_id} />
    </>
  );
}
