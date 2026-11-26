import { notFound } from "next/navigation";
import { ScreenForm } from "@/components/owner/ScreenForm";
import { PageHead } from "@/components/owner/ui";
import { api, ApiRequestError } from "@/lib/api";

export const metadata = { title: "Add a screen" };

type Props = { params: Promise<{ id: string }> };

/** O4 · new screen from a template, with the live seat-map preview. */
export default async function NewScreenPage({ params }: Props) {
  const { id } = await params;
  let cinema;
  try {
    cinema = await api("/owner/cinemas/{cinema_id}", { params: { cinema_id: id }, auth: true });
  } catch (e) {
    if (e instanceof ApiRequestError && e.status === 404) notFound();
    throw e;
  }
  const taken = new Set(cinema.screens.map((s) => s.name.toLowerCase()));
  let n = cinema.screens.length + 1;
  while (taken.has(`screen ${n}`)) n += 1;
  return (
    <>
      <PageHead title="Add a screen" sub={cinema.name} back={{ href: `/owner/cinemas/${cinema.id}`, label: cinema.name }} />
      <ScreenForm cinemaId={cinema.id} cinemaName={cinema.name} suggestedName={`Screen ${n}`} />
    </>
  );
}
