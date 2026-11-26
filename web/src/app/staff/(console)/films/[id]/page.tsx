import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { FilmForm } from "@/components/staff/FilmForm";
import { staffMe } from "@/components/staff/session";
import { PageHead } from "@/components/staff/ui";
import { api, ApiRequestError } from "@/lib/api";

export const metadata: Metadata = { title: "Edit film" };

type Props = { params: Promise<{ id: string }> };

/** Edit a catalogue film, or move its status on (coming soon → now showing → ended). */
export default async function EditFilmPage({ params }: Props) {
  const { id } = await params;
  const me = await staffMe();
  let film;
  try {
    film = await api("/staff/films/{film_id}", { auth: true, params: { film_id: id } });
  } catch (e) {
    if (e instanceof ApiRequestError && (e.status === 404 || e.status === 422)) notFound();
    throw e;
  }
  return (
    <>
      <PageHead
        title={film.title}
        sub={
          <>
            {film.scheduled_shows} upcoming shows across Frontrow ·{" "}
            <Link href={`/movies/${film.slug}`}>see the movie page</Link>
          </>
        }
        back={{ href: "/staff/films", label: "Film catalogue" }}
      />
      <FilmForm film={film} demo={!!me?.is_demo} />
    </>
  );
}
