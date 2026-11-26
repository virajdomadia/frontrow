import Link from "next/link";
import { DemoButtons } from "@/components/auth/DemoButtons";

export function Hero() {
  return (
    <section className="wrap hero">
      <div className="hero-top">
        <h1>The seat you pick<br />is <span>yours</span> for<br />ten minutes</h1>
        <div>
          <p className="lede">Choose seats on a live map. The moment you tap one, it's held for you and greys out for everyone else — <strong>no double bookings, no "sorry, that's gone" at checkout.</strong></p>
          <div className="hero-actions"><Link className="btn btn-red" href="/events">Book seats</Link><a className="btn btn-line" href="#how">See how holds work</a></div>
          <div className="mt-6 max-w-[460px]">
            <p className="mb-2 text-xs font-semibold tracking-[.14em] text-muted-foreground uppercase">Try it in one click</p>
            <DemoButtons />
          </div>
        </div>
      </div>

      {/* A picture of the seat map, not a control: hidden from assistive tech and inert, so its
          seats and the mock Pay button are never announced or focused (QA 2026-11-19). */}
      <div className="hall" aria-hidden="true" inert>
        <div className="hold-pill">Held for you <b>09:41</b></div>
        <div className="screen"></div>
        <div className="screen-label">Screen</div>
        <div className="rows">
          <div className="row"><span className="lbl">A</span><i className="seat sold"></i><i className="seat sold"></i><i className="seat sold"></i><i className="seat aisle sold"></i><i className="seat sold"></i><i className="seat sold"></i><i className="seat sold"></i><i className="seat sold"></i><i className="seat sold"></i><i className="seat sold"></i><i className="seat aisle sold"></i><i className="seat sold"></i><i className="seat sold"></i><i className="seat sold"></i></div>
          <div className="row"><span className="lbl">B</span><i className="seat sold"></i><i className="seat sold"></i><i className="seat"></i><i className="seat aisle"></i><i className="seat sold"></i><i className="seat sold"></i><i className="seat held h1"></i><i className="seat sold"></i><i className="seat sold"></i><i className="seat"></i><i className="seat aisle"></i><i className="seat sold"></i><i className="seat sold"></i><i className="seat sold"></i></div>
          <div className="row"><span className="lbl">C</span><i className="seat"></i><i className="seat"></i><i className="seat"></i><i className="seat aisle"></i><i className="seat"></i><i className="seat held h2"></i><i className="seat held h3"></i><i className="seat"></i><i className="seat"></i><i className="seat"></i><i className="seat aisle"></i><i className="seat sold"></i><i className="seat"></i><i className="seat"></i></div>
          <div className="row"><span className="lbl">D</span><i className="seat"></i><i className="seat"></i><i className="seat"></i><i className="seat aisle"></i><i className="seat"></i><i className="seat mine"></i><i className="seat mine"></i><i className="seat"></i><i className="seat"></i><i className="seat held h4"></i><i className="seat aisle"></i><i className="seat"></i><i className="seat"></i><i className="seat"></i></div>
          <div className="row"><span className="lbl">E</span><i className="seat"></i><i className="seat held h5"></i><i className="seat held h6"></i><i className="seat aisle"></i><i className="seat"></i><i className="seat"></i><i className="seat"></i><i className="seat"></i><i className="seat"></i><i className="seat"></i><i className="seat aisle"></i><i className="seat"></i><i className="seat"></i><i className="seat"></i></div>
          <div className="row"><span className="lbl">F</span><i className="seat"></i><i className="seat"></i><i className="seat"></i><i className="seat aisle"></i><i className="seat"></i><i className="seat"></i><i className="seat"></i><i className="seat held h7"></i><i className="seat"></i><i className="seat"></i><i className="seat aisle"></i><i className="seat"></i><i className="seat"></i><i className="seat"></i></div>
          <div className="row"><span className="lbl">G</span><i className="seat"></i><i className="seat"></i><i className="seat"></i><i className="seat aisle"></i><i className="seat"></i><i className="seat"></i><i className="seat"></i><i className="seat"></i><i className="seat"></i><i className="seat"></i><i className="seat aisle"></i><i className="seat"></i><i className="seat"></i><i className="seat"></i></div>
        </div>
        <div className="legend"><span><i></i> Available</span><span><i className="a"></i> Held by someone</span><span><i className="m"></i> Yours</span><span><i className="s"></i> Sold</span></div>
        <div className="checkout"><span className="sum"><b>D6, D7</b> 2 × ₹550 · Recliner</span><span className="btn btn-red">Pay ₹1,160</span></div>
      </div>
    </section>
  );
}
