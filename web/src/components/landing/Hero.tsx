export function Hero() {
  return (
    <section className="wrap hero">
      <div className="hero-top">
        <h1>The seat you pick<br />is <span>yours</span> for<br />ten minutes</h1>
        <div>
          <p className="lede">Choose seats on a live map. The moment you tap one, it's held for you and greys out for everyone else — <strong>no double bookings, no "sorry, that's gone" at checkout.</strong></p>
          <div className="hero-actions"><a className="btn btn-red" href="#shows">Book seats</a><a className="btn btn-line" href="#how">See how holds work</a></div>
        </div>
      </div>

      <div className="hall" aria-label="Live seat map example">
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
        <div className="checkout"><span className="sum"><b>D6, D7</b> 2 × ₹350 · Recliner</span><a className="btn btn-red" href="#">Pay ₹700</a></div>
      </div>
    </section>
  );
}
