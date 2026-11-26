"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ApiRequestError } from "@/lib/api-error";
import { fieldErrors, messageOf, send } from "@/lib/client";
import { field, FormError } from "./ui";

/** O5 · ask Frontrow staff to add a film that isn't in the shared catalogue yet. */
export function FilmRequestForm() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [existing, setExisting] = useState<{ id: string; slug: string } | null>(null);
  const [sent, setSent] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    const title = String(data.get("title") ?? "");
    setBusy(true);
    setError("");
    setExisting(null);
    setSent("");
    setFields({});
    try {
      await send("POST", "/owner/film-requests", { title, note: String(data.get("note") ?? "") || null });
      form.reset();
      setSent(title);
      router.refresh();
    } catch (err) {
      if (err instanceof ApiRequestError && err.status === 409) {
        setExisting((err.body.details as { film?: { id: string; slug: string } } | undefined)?.film ?? null);
      }
      setFields(fieldErrors(err));
      setError(messageOf(err));
    }
    setBusy(false);
  }

  return (
    <form onSubmit={submit} className="fr-stub grid gap-4 p-5 text-ink">
      <h2 className="font-cond text-2xl font-extrabold uppercase">Request a missing film</h2>
      <p className="text-sm text-ink-2">Frontrow staff add it to the shared catalogue — usually within a day — and you&apos;ll see it below.</p>
      <label className={field.label}>
        Film title
        <input name="title" required maxLength={120} placeholder="Kaveri Express" className={field.input} aria-invalid={!!fields.title} />
      </label>
      <label className={field.label}>
        Note for staff (optional)
        <textarea
          name="note"
          maxLength={500}
          rows={3}
          placeholder="Language, format, release date, distributor…"
          className={field.input}
        />
      </label>
      <FormError message={error} />
      {existing && (
        <p className="-mt-2 text-sm">
          <Link href={`/owner/shows/new?film=${existing.id}`} className="font-semibold underline underline-offset-4">
            Schedule it now →
          </Link>
        </p>
      )}
      {sent && (
        <p role="status" className="rounded-btn bg-mint/15 px-3 py-2 text-sm font-medium text-[#1f6e57]">
          Request for “{sent}” sent to Frontrow staff.
        </p>
      )}
      <Button type="submit" disabled={busy}>
        {busy ? "Sending…" : "Send request"}
      </Button>
    </form>
  );
}
