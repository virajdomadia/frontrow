import { Logo } from "@/components/site/Logo";
import { AuthForm } from "./AuthForm";

/** S9 shell: the plum house on the left, a paper card with the form on the right. */
export function AuthPage({ mode, next }: { mode: "sign-in" | "sign-up"; next?: string }) {
  const title = mode === "sign-in" ? "Welcome back" : "Get a front-row seat";
  const lede =
    mode === "sign-in"
      ? "Sign in to pay for held seats, see your tickets, or run your venues."
      : "Book seats on a live map, or sell your own shows from venue templates.";
  return (
    <div className="mx-auto grid min-h-dvh w-[min(1180px,100%-32px)] content-start gap-10 py-6 lg:grid-cols-[1fr_440px] lg:content-center lg:gap-16">
      <div className="grid content-start gap-6 lg:content-center">
        <Logo />
        <h1 className="font-cond text-[clamp(44px,7vw,92px)] leading-[.92] font-extrabold uppercase">{title}</h1>
        <p className="max-w-[40ch] text-lg text-muted-foreground">{lede}</p>
        <ul className="hidden list-none gap-2 p-0 text-sm text-muted-foreground lg:grid">
          <li>· Seats are held for 10 minutes while you pay</li>
          <li>· One QR per seat, checked at the door</li>
          <li>· Test-mode payments — no real money moves</li>
        </ul>
      </div>
      <div className="rounded-card bg-paper p-6 text-ink shadow-[0_20px_50px_rgba(0,0,0,.45)] sm:p-8">
        <h2 className="mb-5 font-cond text-3xl font-extrabold uppercase">{mode === "sign-in" ? "Sign in" : "Create account"}</h2>
        <AuthForm mode={mode} next={next} />
      </div>
    </div>
  );
}
