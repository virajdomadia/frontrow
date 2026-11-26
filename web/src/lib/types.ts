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

export type Me = S["Me"];
export type Order = S["Order"];
export type OrderSeat = S["OrderSeatOut"];
export type TicketBundle = S["TicketBundle"];
export type TicketOut = S["TicketOut"];
export type MyTickets = S["MyTickets"];
export type TicketGroup = S["TicketGroup"];
export type HoldGranted = S["HoldGranted"];

export type OrganiserVenue = S["OrganiserVenue"];
export type OrganiserVenueDetail = S["OrganiserVenueDetail"];
export type OrganiserEvent = S["OrganiserEvent"];
export type OrganiserShowtime = S["OrganiserShowtime"];
export type Bookings = S["Bookings"];
export type Booking = S["Booking"];
