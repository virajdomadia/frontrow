import Link from "next/link";
import { DemoButtons } from "@/components/auth/DemoButtons";

export function Organisers() {
  return (
    <section className="wrap ticket-sec" id="organisers">
      <div className="ticket-in">
        <div className="ticket" aria-label="Example ticket">
          <div className="tk-main">
            <div className="film">Neon Alley</div>
            <div className="meta"><span>Seats<b>D6, D7</b></span><span>Show<b>Fri 7:30 PM</b></span><span>Screen<b>1 · Recliner</b></span></div>
          </div>
          <div className="tk-stub"><div className="qr" aria-hidden="true">
            <i></i><i></i><i></i><i className="o"></i><i></i><i className="o"></i><i></i><i></i>
            <i></i><i className="o"></i><i></i><i className="o"></i><i></i><i className="o"></i><i className="o"></i><i></i>
            <i></i><i className="o"></i><i></i><i></i><i className="o"></i><i></i><i className="o"></i><i></i>
            <i></i><i></i><i></i><i className="o"></i><i></i><i></i><i></i><i></i>
            <i className="o"></i><i></i><i className="o"></i><i></i><i className="o"></i><i></i><i className="o"></i><i className="o"></i>
            <i></i><i></i><i></i><i className="o"></i><i></i><i className="o"></i><i></i><i></i>
            <i></i><i className="o"></i><i></i><i></i><i className="o"></i><i></i><i className="o"></i><i></i>
            <i></i><i></i><i></i><i className="o"></i><i></i><i></i><i></i><i className="o"></i>
          </div></div>
        </div>
        <div>
          <h2>A ticket that can't be faked, and a dashboard that shows every seat</h2>
          <p>Tickets carry a signed QR that's checked at the door. Organisers create shows from venue templates, set prices per section, and watch sales fill in seat by seat.</p>
          <div className="mt-6 grid max-w-[360px] gap-3">
            <DemoButtons only="organiser" next="/organiser" />
            <p className="text-sm text-muted-foreground">
              Or <Link href="/sign-up" className="text-screen underline underline-offset-4">create an organiser account</Link> and put your own venue on sale in three minutes.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
