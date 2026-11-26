import Image from "next/image";
import Link from "next/link";
import { TEMPLATE_LABEL } from "@/components/owner/format";
import { Empty, PageHead } from "@/components/owner/ui";
import { buttonVariants } from "@/components/ui/button";
import { api } from "@/lib/api";

export const metadata = { title: "Cinemas" };

/** O3 · the business's cinemas and their screens. */
export default async function CinemasPage() {
  const cinemas = await api("/owner/cinemas", { auth: true });
  return (
    <>
      <PageHead
        title="Cinemas"
        sub="Each cinema has screens; each screen has a seat map built from a template."
        action={
          <Link href="/owner/cinemas/new" className={buttonVariants()}>
            Add cinema
          </Link>
        }
      />
      {cinemas.length ? (
        <ul className="grid list-none gap-4 p-0 lg:grid-cols-2">
          {cinemas.map((c) => (
            <li key={c.id} className="grid overflow-hidden rounded-card border border-border bg-plum-2 sm:grid-cols-[180px_1fr]">
              <div className="relative min-h-[120px] bg-paper-2">
                {c.photo_url ? (
                  <Image src={c.photo_url} alt="" fill sizes="180px" className="object-cover" />
                ) : (
                  <span aria-hidden="true" className="grid size-full place-items-center font-cond text-5xl font-extrabold text-ink/20">
                    {c.name[0]}
                  </span>
                )}
              </div>
              <div className="grid gap-3 p-4">
                <div>
                  <h2 className="font-cond text-2xl font-bold uppercase">
                    <Link href={`/owner/cinemas/${c.id}`} className="no-underline hover:underline">
                      {c.name}
                    </Link>
                  </h2>
                  <p className="text-sm text-ink-2">{c.area} · {c.upcoming_shows} upcoming shows</p>
                </div>
                {c.screens.length ? (
                  <ul className="grid list-none gap-1 p-0 text-sm">
                    {c.screens.map((s) => (
                      <li key={s.id} className="flex flex-wrap justify-between gap-2 border-t border-border pt-1">
                        <Link href={`/owner/screens/${s.id}`} className="font-semibold">
                          {s.name}
                        </Link>
                        <span className="text-ink-2">
                          {TEMPLATE_LABEL[s.template]} · {s.seat_count} seats · {s.formats.join(" / ")}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-ink-3">No screens yet.</p>
                )}
                <div className="flex flex-wrap gap-2">
                  <Link href={`/owner/cinemas/${c.id}`} className={buttonVariants({ variant: "paper", size: "sm" })}>
                    Edit
                  </Link>
                  <Link href={`/owner/cinemas/${c.id}/screens/new`} className={buttonVariants({ size: "sm" })}>
                    Add screen
                  </Link>
                </div>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <Empty title="No cinemas yet" body="Add your first cinema, then its screens." href="/owner/cinemas/new" cta="Add cinema" />
      )}
    </>
  );
}
