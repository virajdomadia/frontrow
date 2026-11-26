import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { FlowHeader } from "@/components/booking/FlowHeader";
import { Checkout } from "@/components/checkout/Checkout";
import { api, ApiRequestError } from "@/lib/api";
import { requireMe } from "@/lib/session";

export const metadata: Metadata = { title: "Checkout", robots: { index: false } };

type Props = { params: Promise<{ orderId: string }> };

/** S5 / S8: the order is per-user and live, so this always renders on request. */
export default async function CheckoutPage({ params }: Props) {
  const { orderId } = await params;
  await requireMe(`/checkout/${orderId}`);
  let order;
  try {
    order = await api("/orders/{order_id}", { params: { order_id: orderId }, auth: true });
  } catch (e) {
    if (e instanceof ApiRequestError && e.status === 404) notFound();
    throw e;
  }
  return (
    <>
      <FlowHeader step={order.status === "paid" ? 2 : 1} back={`/book/${order.showtime.id}`} backLabel="Back to the seat map" />
      <main>
        <Checkout initial={order} />
      </main>
    </>
  );
}
