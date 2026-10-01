import type { components } from "./api-types";

type S = components["schemas"];

export type EventCard = S["EventCard"];
export type EventDetail = S["EventDetail"];
export type EventList = S["EventList"];
export type ShowtimeSummary = S["ShowtimeSummary"];
export type Fill = ShowtimeSummary["fill"];
