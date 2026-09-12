export function How() {
  return (
    <section className="hard" id="how">
      <div className="wrap hard-in">
        <div>
          <h2>Two people, one seat, same second</h2>
          <p>That's the problem every ticketing site quietly gets wrong. Frontrow puts a timed hold on the seat the instant you tap it, and only one hold can ever win. Here's what happens under the hood when you and someone else go for D6 at once.</p>
        </div>
        <div className="timeline">
          <div className="tl"><div className="t">0.000 s</div><div className="e">You tap D6</div><div className="d">A hold key for D6 is written with a 10-minute expiry. Yours is first, so it succeeds.</div></div>
          <div className="tl"><div className="t">0.004 s</div><div className="e">Someone else taps D6</div><div className="d">Their hold write finds the key already exists. They see "just taken" and pick another seat.</div></div>
          <div className="tl"><div className="t">0.020 s</div><div className="e">Everyone's map updates</div><div className="d">D6 turns amber for all viewers of this show — no refresh needed.</div></div>
          <div className="tl"><div className="t">4 min later</div><div className="e">You pay</div><div className="d">Payment confirmed, the seat is written as sold inside a database transaction, and your ticket is issued.</div></div>
          <div className="tl"><div className="t">If you didn't pay</div><div className="e">The hold expires</div><div className="d">D6 goes back to available for everyone within a second. Nothing is lost.</div></div>
        </div>
      </div>
    </section>
  );
}
