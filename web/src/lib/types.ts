import type { components } from "./api-types";

type S = components["schemas"];

export type EventCard = S["EventCard"];
export type EventDetail = S["EventDetail"];
export type EventList = S["EventList"];
export type ShowtimeSummary = S["ShowtimeSummary"];
export type Fill = ShowtimeSummary["fill"];
export type ShowtimeDetail = S["ShowtimeDetail"];
export type TierPrice = S["TierPrice"];
export type Layout = S["Layout"];
export type SeatSnapshot = S["SeatState"];
