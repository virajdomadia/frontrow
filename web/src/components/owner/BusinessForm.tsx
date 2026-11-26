"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { fieldErrors, messageOf, send } from "@/lib/client";
import { field, FormError } from "./ui";

/**
 * Business details. `register`: a signed-in account adds a business (POST, pending until staff
 * verify it). `resubmit`: a rejected business fixes its details and goes back into the queue.
 */
export function BusinessForm({
  mode,
  initial,
}: {
  mode: "register" | "resubmit";
  initial?: { name: string; phone: string };
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const body = { name: String(data.get("name") ?? ""), phone: String(data.get("phone") ?? "") };
    setBusy(true);
    setError("");
    setFields({});
    try {
      await send(mode === "register" ? "POST" : "PATCH", "/owner/business", body);
      router.push("/owner");
      router.refresh();
      if (mode === "resubmit") setBusy(false);
    } catch (err) {
      const f = fieldErrors(err);
      setFields(f);
      setError(Object.keys(f).length ? "Check the highlighted fields." : messageOf(err));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <label className={field.label}>
        Business name
        <input
          name="name"
          required
          minLength={2}
          maxLength={80}
          defaultValue={initial?.name}
          autoComplete="organization"
          placeholder="e.g. Sunrise Talkies"
          className={field.input}
          aria-invalid={!!fields.name}
        />
      </label>
      <label className={field.label}>
        Phone
        <input
          name="phone"
          required
          type="tel"
          minLength={6}
          maxLength={20}
          defaultValue={initial?.phone}
          autoComplete="tel"
          placeholder="+91 80 1234 5678"
          className={field.input}
          aria-invalid={!!fields.phone}
        />
        <span className={field.hint}>Frontrow staff call this number once to verify you.</span>
      </label>
      <FormError message={error} />
      <Button type="submit" disabled={busy}>
        {busy ? "Saving…" : mode === "register" ? "Register business" : "Send for review again"}
      </Button>
    </form>
  );
}
