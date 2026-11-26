import type { Metadata } from "next";
import { FilmForm } from "@/components/staff/FilmForm";
import { staffMe } from "@/components/staff/session";
import { PageHead } from "@/components/staff/ui";

export const metadata: Metadata = { title: "Add a film" };

type Props = { searchParams: Promise<{ request?: string | string[]; title?: string | string[] }> };

const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : undefined);

/** Add a film to the shared catalogue — or answer an owner's request with it (`?request=`). */
export default async function NewFilmPage({ searchParams }: Props) {
  const params = await searchParams;
  const requestId = one(params.request);
  const title = one(params.title);
  const me = await staffMe();
  return (
    <>
      <PageHead
        title="Add a film"
        sub={requestId ? `Answering an owner's request for “${title ?? "a film"}” — saving links it, and they can schedule it straight away.` : "Every cinema on Frontrow can schedule it once it's now showing."}
        back={requestId ? { href: "/staff/requests", label: "Film requests" } : { href: "/staff/films", label: "Film catalogue" }}
      />
      <FilmForm requestId={requestId} initialTitle={title} demo={!!me?.is_demo} />
    </>
  );
}
