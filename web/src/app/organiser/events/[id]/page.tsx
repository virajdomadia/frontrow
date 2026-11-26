import { notFound } from "next/navigation";
import { EventForm } from "@/components/organiser/EventForm";
import { PageHead, StatusBadge } from "@/components/organiser/ui";
import { api, ApiRequestError } from "@/lib/api";

export const metadata = { title: "Edit event" };

type Props = { params: Promise<{ id: string }> };

export default async function EditEventPage({ params }: Props) {
  const { id } = await params;
  let event;
  try {
    event = await api("/organiser/events/{event_id}", { params: { event_id: id }, auth: true });
  } catch (e) {
    if (e instanceof ApiRequestError && e.status === 404) notFound();
    throw e;
  }
  return (
    <>
      <PageHead
        title={`Edit · ${event.title}`}
        sub={
          <span className="inline-flex items-center gap-2">
            <StatusBadge status={event.status} /> {event.upcoming_showtimes} upcoming showtimes · {event.tickets_sold.toLocaleString("en-IN")} tickets sold
          </span>
        }
        back={{ href: "/organiser/events", label: "Events" }}
      />
      <EventForm event={event} />
    </>
  );
}
