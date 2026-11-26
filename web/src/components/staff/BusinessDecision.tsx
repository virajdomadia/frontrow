"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { inputClass, labelClass } from "@/components/auth/CodeSignIn";
import { Button } from "@/components/ui/button";
import { ApiRequestError } from "@/lib/api-error";
import { messageOf, send } from "@/lib/client";
import { DEMO_REASON, FormError } from "./ui";

function friendly(e: unknown) {
  if (e instanceof ApiRequestError && e.body.code === "demo_read_only") return DEMO_REASON;
  return messageOf(e);
}

/** T4: Approve (their shows go public) or Reject with a reason the owner will see. */
export function BusinessDecision({
  id,
  name,
  status,
  demo,
}: {
  id: string;
  name: string;
  status: string;
  demo: boolean;
}) {
  const router = useRouter();
  const [rejecting, setRejecting] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function decide(action: "approve" | "reject") {
    setBusy(true);
    setError("");
    try {
      await send("PATCH", `/staff/businesses/${id}`, action === "reject" ? { action, note } : { action });
      setRejecting(false);
      setNote("");
      router.refresh();
    } catch (e) {
      setError(friendly(e));
    } finally {
      setBusy(false);
    }
  }

  const off = demo || busy;
  const title = demo ? DEMO_REASON : undefined;
  return (
    <div className="grid gap-3">
      {!rejecting ? (
        <div className="flex flex-wrap gap-2">
          {status !== "verified" && (
            <Button type="button" size="sm" disabled={off} title={title} onClick={() => decide("approve")}>
              {busy ? "Saving…" : status === "rejected" ? "Approve after all" : "Approve"}
            </Button>
          )}
          {status !== "rejected" && (
            <Button type="button" size="sm" variant="paper" disabled={off} title={title} onClick={() => setRejecting(true)}>
              Reject…
            </Button>
          )}
        </div>
      ) : (
        <form
          className="grid gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            void decide("reject");
          }}
        >
          <label className={labelClass}>
            Why are you rejecting {name}?
            <textarea
              required
              maxLength={300}
              rows={2}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              className={inputClass}
              placeholder="e.g. The phone number didn't answer — please check it and resubmit."
            />
            <span className="text-xs font-normal text-ink-3">The owner sees this in their console and can fix and resubmit.</span>
          </label>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" size="sm" disabled={off || !note.trim()}>
              {busy ? "Saving…" : "Reject business"}
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setRejecting(false)}>
              Cancel
            </Button>
          </div>
        </form>
      )}
      {demo && <p className="text-xs text-ink-3">{DEMO_REASON}</p>}
      <FormError message={error} />
    </div>
  );
}
