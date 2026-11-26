import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Logo } from "@/components/site/Logo";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const STEPS = ["Seats", "Pay", "Ticket"];

/** The booking flow's header: back, logo, and where you are in Seats → Pay → Ticket. */
export function FlowHeader({ step, back, backLabel }: { step: 0 | 1 | 2; back: string; backLabel: string }) {
  return (
    <header className="no-print border-b border-border">
      <nav aria-label="Booking" className="mx-auto flex w-[min(1440px,100%)] items-center justify-between gap-4 px-4 py-4 lg:px-10">
        <div className="flex items-center gap-2 sm:gap-5">
          <Link href={back} aria-label={backLabel} className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "px-2")}>
            <ArrowLeft />
          </Link>
          <Logo />
        </div>
        <ol className="flex list-none gap-4 p-0 font-cond text-[15px] font-semibold tracking-[.06em] text-faint uppercase sm:gap-6 sm:text-[17px]">
          {STEPS.map((s, i) => (
            <li
              key={s}
              aria-current={i === step ? "step" : undefined}
              className={cn("items-center aria-[current=step]:text-screen", i === step ? "flex" : "hidden sm:flex", i < step && "sm:text-muted-foreground")}
            >
              {i === step && <span aria-hidden="true" className="mr-2 inline-block size-2 rounded-full bg-red" />}
              <span className="hidden sm:inline">{i + 1}&nbsp;</span>
              {s}
            </li>
          ))}
        </ol>
      </nav>
    </header>
  );
}
