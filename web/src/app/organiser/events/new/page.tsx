import { EventForm } from "@/components/organiser/EventForm";
import { PageHead } from "@/components/organiser/ui";

export const metadata = { title: "New event" };

export default function NewEventPage() {
  return (
    <>
      <PageHead title="New event" sub="Live events appear on the site as soon as they have a showtime." back={{ href: "/organiser/events", label: "Events" }} />
      <EventForm />
    </>
  );
}
