import { api, ApiRequestError } from "@/lib/api";
import { ics } from "@/lib/calendar";
import { SITE_URL } from "@/lib/site";

/** "Add to calendar" (R6): the booking as an `.ics` file, for the ticket's owner only. */
export async function GET(_: Request, { params }: { params: Promise<{ orderId: string }> }) {
  const { orderId } = await params;
  let bundle;
  try {
    bundle = await api("/tickets/{order_id}", { params: { order_id: orderId }, auth: true });
  } catch (e) {
    if (e instanceof ApiRequestError && (e.status === 401 || e.status === 404))
      return new Response("Not found", { status: 404, headers: { "Cache-Control": "no-store" } });
    throw e;
  }
  const { order } = bundle;
  const st = order.show;
  const body = ics({
    uid: order.id,
    title: st.film.title,
    start: st.starts_at,
    end: st.ends_at,
    location: `${st.cinema.name}, ${st.cinema.address}`,
    description: `Frontrow tickets — seats ${order.seats.map((s) => s.label).join(", ")}. Show each seat's QR at the door.`,
    url: `${SITE_URL}/tickets/${order.id}`,
  });
  return new Response(body, {
    headers: {
      "Content-Type": "text/calendar; charset=utf-8",
      "Content-Disposition": `attachment; filename="${st.film.slug}.ics"`,
      "Cache-Control": "private, no-store",
    },
  });
}
