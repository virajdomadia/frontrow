export function Shows() {
  return (
    <section className="wrap shows" id="shows">
      <h2>Now showing</h2>
      <p className="sub">Films and live shows, one seat map each. The number on the poster is how full it is right now.</p>
      <div className="posters">
        <a className="poster p1" href="#"><span className="fill">92% full</span><h3>Kantara 2</h3><p className="when">Fri 7:30 PM · Screen 1</p></a>
        <a className="poster p2" href="#"><span className="fill">61% full</span><h3>Dune: Part Three</h3><p className="when">Sat 9:00 PM · IMAX</p></a>
        <a className="poster p3" href="#"><span className="fill">38% full</span><h3>Prateek Kuhad live</h3><p className="when">Sun 8:00 PM · Arena</p></a>
        <a className="poster p4" href="#"><span className="fill">14% full</span><h3>Zakir Khan</h3><p className="when">Thu 8:30 PM · Hall B</p></a>
      </div>
    </section>
  );
}
