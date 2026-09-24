import Link from "next/link";

export function Cta() {
  return (
    <section className="wrap cta">
      <h2>Grab the good seats</h2>
      <p>Open the map, tap a seat, and it's yours while you pay.</p>
      <Link className="btn btn-red" href="/events">Book seats</Link>
    </section>
  );
}
