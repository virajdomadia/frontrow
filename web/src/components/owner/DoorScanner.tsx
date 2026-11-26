"use client";

import { Camera, CameraOff } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { messageOf, send } from "@/lib/client";
import type { CheckInResult } from "@/lib/types";
import { cn } from "@/lib/utils";
import { field } from "./ui";

// The Shape Detection API isn't in TypeScript's DOM lib yet.
type Detected = { rawValue: string };
type Detector = { detect: (source: HTMLVideoElement) => Promise<Detected[]> };
type DetectorCtor = new (opts: { formats: string[] }) => Detector;

const LOOK: Record<CheckInResult["result"], { box: string; title: string }> = {
  valid: { box: "border-[#1f6e57] bg-[#dff3ea] text-[#0f4434]", title: "Valid — let them in" },
  used: { box: "border-[#a35a12] bg-[#fbead3] text-[#5c3008]", title: "Already used" },
  wrong_show: { box: "border-red-dark bg-[#fbe0e2] text-[#6d1018]", title: "Wrong show" },
  invalid: { box: "border-red-dark bg-[#fbe0e2] text-[#6d1018]", title: "Not a ticket" },
};

/**
 * O9 · the door (B10), for an usher's phone: the camera reads M-ticket QR codes where the browser
 * has a BarcodeDetector; the paste/type box always works. Each scan is one `POST /checkin` —
 * the api marks a ticket used exactly once, however many phones scan at the same door.
 */
export function DoorScanner({ showId, initialAdmitted, sold }: { showId: string; initialAdmitted: number; sold: number }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const lastRef = useRef<{ token: string; at: number }>({ token: "", at: 0 });
  const busyRef = useRef(false);
  const [supported, setSupported] = useState<boolean | null>(null);
  const [cameraOn, setCameraOn] = useState(false);
  const [cameraError, setCameraError] = useState("");
  const [result, setResult] = useState<CheckInResult | null>(null);
  const [error, setError] = useState("");
  const [counts, setCounts] = useState({ admitted: initialAdmitted, sold });
  const [token, setToken] = useState("");
  const [scans, setScans] = useState(0);

  useEffect(() => {
    setSupported(typeof window !== "undefined" && "BarcodeDetector" in window && !!navigator.mediaDevices?.getUserMedia);
  }, []);

  const check = useCallback(
    async (raw: string) => {
      const value = raw.trim();
      if (!value || busyRef.current) return;
      busyRef.current = true;
      setError("");
      try {
        const res = await send<CheckInResult>("POST", "/checkin", { token: value, show_id: showId });
        setResult(res);
        setCounts({ admitted: res.admitted, sold: res.sold });
        setScans((n) => n + 1);
        setToken("");
        if (navigator.vibrate) navigator.vibrate(res.result === "valid" ? 80 : [60, 60, 60]);
      } catch (e) {
        setError(messageOf(e, "Couldn't check that ticket. Try again."));
      } finally {
        busyRef.current = false;
      }
    },
    [showId],
  );

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setCameraOn(false);
  }, []);

  async function startCamera() {
    setCameraError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setCameraOn(true);
    } catch {
      setCameraError("The camera isn't available — allow camera access, or type the code below.");
    }
  }

  // Read the video a few times a second while the camera is on.
  useEffect(() => {
    if (!cameraOn) return;
    const Ctor = (window as unknown as { BarcodeDetector: DetectorCtor }).BarcodeDetector;
    const detector = new Ctor({ formats: ["qr_code"] });
    let live = true;
    const tick = async () => {
      if (!live || !videoRef.current) return;
      try {
        const found = await detector.detect(videoRef.current);
        const value = found[0]?.rawValue;
        const now = Date.now();
        // The same code held in front of the camera is one scan, not ten.
        if (value && !(value === lastRef.current.token && now - lastRef.current.at < 4000)) {
          lastRef.current = { token: value, at: now };
          await check(value);
        }
      } catch {
        // a frame that couldn't be read; try the next one
      }
      if (live) window.setTimeout(tick, 350);
    };
    void tick();
    return () => {
      live = false;
    };
  }, [cameraOn, check]);

  useEffect(() => stopCamera, [stopCamera]);

  const look = result ? LOOK[result.result] : null;

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_380px]">
      <div className="grid content-start gap-4">
        <div
          aria-live="assertive"
          className={cn(
            "grid min-h-[180px] content-center gap-1 rounded-card border-4 px-5 py-6 text-center",
            look ? look.box : "border-dashed border-ink/25 bg-plum-2 text-ink-2",
          )}
        >
          {result && look ? (
            <>
              <p className="font-cond text-[clamp(36px,8vw,60px)] leading-none font-extrabold uppercase">{look.title}</p>
              {result.seat && <p className="font-cond text-4xl font-bold">Seat {result.seat}</p>}
              <p className="text-lg font-medium">
                {result.name ? `${result.name} · ` : ""}
                {result.message}
              </p>
              <p className="text-xs opacity-70">Scan #{scans}</p>
            </>
          ) : (
            <p className="text-lg">Ready — scan an M-ticket QR or type its code.</p>
          )}
        </div>
        {error && (
          <p role="alert" className="rounded-btn bg-red-dark/10 px-3 py-2 text-sm font-medium text-red-dark">
            {error}
          </p>
        )}

        <div className="grid gap-2">
          <div className="relative overflow-hidden rounded-card border border-border bg-ink">
            <video ref={videoRef} muted playsInline className={cn("aspect-[4/3] w-full object-cover", !cameraOn && "hidden")} />
            {cameraOn && <div aria-hidden="true" className="pointer-events-none absolute inset-[18%] rounded-card border-4 border-white/80" />}
            {!cameraOn && (
              <div className="grid aspect-[4/3] w-full place-items-center p-6 text-center text-paper/80">
                {supported === false
                  ? "This browser can't read QR codes from the camera — type or paste the ticket code below (Chrome on Android can)."
                  : "Camera off"}
              </div>
            )}
          </div>
          {supported && (
            <Button type="button" variant={cameraOn ? "paper" : "default"} onClick={cameraOn ? stopCamera : startCamera} className="w-full">
              {cameraOn ? <CameraOff /> : <Camera />}
              {cameraOn ? "Stop camera" : "Scan with camera"}
            </Button>
          )}
          {cameraError && <p className="text-sm font-medium text-red-dark">{cameraError}</p>}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            void check(token);
          }}
          className="grid gap-2"
        >
          <label className={field.label}>
            Ticket code
            <input
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="Paste the code under the QR"
              autoComplete="off"
              spellCheck={false}
              className={cn(field.input, "font-mono text-sm")}
            />
          </label>
          <Button type="submit" variant="paper" disabled={!token.trim()}>
            Check ticket
          </Button>
        </form>
      </div>

      <aside className="grid content-start gap-3">
        <div className="rounded-card border border-border bg-plum-2 px-5 py-4">
          <p className="text-xs font-semibold tracking-[.1em] text-muted-foreground uppercase">Admitted</p>
          <p className="font-cond text-6xl leading-none font-extrabold tabular-nums">
            {counts.admitted}
            <span className="text-2xl text-ink-3"> / {counts.sold}</span>
          </p>
          <p className="mt-1 text-sm text-ink-2">tickets sold for this show</p>
        </div>
        <p className="text-sm text-ink-3">
          Any number of phones can scan at once: each ticket gets in exactly once, and a second scan shows when it was first
          used.
        </p>
      </aside>
    </div>
  );
}
