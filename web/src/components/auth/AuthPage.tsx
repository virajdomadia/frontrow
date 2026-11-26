import { SiteHeader } from "@/components/site/SiteHeader";
import type { Door } from "@/lib/types";
import { CodeSignIn } from "./CodeSignIn";
import { DemoButtons, type DemoRole } from "./DemoButtons";

const COPY: Record<Door, { title: string; lede: string; points: string[]; card: string; demo: DemoRole }> = {
  customer: {
    title: "Pick your seat, live",
    lede: "Sign in with your email to pay for held seats and keep your M-tickets in one place.",
    points: ["A 6-digit code by email — no password", "Seats stay held while you sign in", "One QR per seat, scanned at the door"],
    card: "Sign in",
    demo: "customer",
  },
  business: {
    title: "Sell your shows on Frontrow",
    lede: "Set up your cinemas and screens, pick films from the shared catalogue, and schedule a month of shows in one go.",
    points: ["Screens from templates with a live seat-map preview", "Online sales on the same live map as your box office", "Verified once by Frontrow staff, then you're public"],
    card: "Business sign-in",
    demo: "owner",
  },
  staff: {
    title: "Frontrow staff",
    lede: "The film catalogue, film requests and cinema approvals.",
    points: ["Staff accounts only"],
    card: "Staff sign-in",
    demo: "staff",
  },
};

/** The three sign-in doors (R1): copy on the left, the email-code card and a demo button on the right. */
export function AuthPage({ door, next, heading }: { door: Door; next?: string; heading?: string }) {
  const c = COPY[door];
  return (
    <>
      <SiteHeader active={door === "business" ? "business" : undefined} />
      <main className="mx-auto grid w-[min(1180px,100%-32px)] content-start gap-10 py-10 lg:grid-cols-[1fr_440px] lg:gap-16 lg:py-16">
        <div className="grid content-start gap-5">
          <h1 className="font-cond text-[clamp(44px,7vw,88px)] leading-[.92] font-extrabold uppercase">{c.title}</h1>
          <p className="max-w-[44ch] text-lg text-muted-foreground">{c.lede}</p>
          <ul className="grid list-none gap-2 p-0 text-[15px] text-ink-2">
            {c.points.map((p) => (
              <li key={p} className="flex gap-2">
                <span aria-hidden="true" className="mt-2 inline-block size-1.5 shrink-0 rounded-full bg-red" />
                {p}
              </li>
            ))}
          </ul>
        </div>
        <div className="fr-stub p-6 shadow-[0_18px_40px_rgb(42_11_30_/_.12)] sm:p-8">
          <h2 className="mb-5 font-cond text-3xl font-extrabold uppercase">{heading ?? c.card}</h2>
          <CodeSignIn door={door} next={next} />
          <div className="mt-6 grid gap-2.5 border-t border-dashed border-ink/25 pt-4">
            <p className="text-center text-xs font-semibold tracking-[.12em] text-ink-2 uppercase">Or look around as a demo</p>
            <DemoButtons next={next} only={c.demo} />
          </div>
        </div>
      </main>
    </>
  );
}
