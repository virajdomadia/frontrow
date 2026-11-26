import { PageHead } from "@/components/organiser/ui";
import { VenueForm } from "@/components/organiser/VenueForm";

export const metadata = { title: "New venue" };

export default function NewVenuePage() {
  return (
    <>
      <PageHead
        title="New venue"
        sub="Pick a template and tune it. The preview is the exact map customers will book from."
        back={{ href: "/organiser/venues", label: "Venues" }}
      />
      <VenueForm />
    </>
  );
}
