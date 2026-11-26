import { BulkShowForm } from "@/components/owner/BulkShowForm";
import { PageHead } from "@/components/owner/ui";
import { api } from "@/lib/api";

export const metadata = { title: "Schedule shows" };

type Props = { searchParams: Promise<{ film?: string | string[]; screen?: string | string[] }> };

/** O6 · bulk scheduling. `?film=` / `?screen=` preselect from the Films and Screens pages. */
export default async function ScheduleShowsPage({ searchParams }: Props) {
  const sp = await searchParams;
  const [catalogue, cinemas] = await Promise.all([api("/films", { auth: true }), api("/owner/cinemas", { auth: true })]);
  return (
    <>
      <PageHead
        title="Schedule shows"
        sub="Every show in the range is created at once — or none, if any of them would overlap another show on the screen."
        back={{ href: "/owner/shows", label: "Shows" }}
      />
      <BulkShowForm
        films={catalogue.films}
        cinemas={cinemas}
        initialFilm={typeof sp.film === "string" ? sp.film : undefined}
        initialScreen={typeof sp.screen === "string" ? sp.screen : undefined}
      />
    </>
  );
}
