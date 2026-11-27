import type { components } from "./api-types";

type S = components["schemas"];

// Catalogue (customer)
export type FilmCard = S["FilmCard"];
export type FilmDetail = S["FilmDetail"];
export type FilmList = S["FilmList"];
export type FilmShows = S["FilmShows"];
export type CinemaShows = S["CinemaShows"];
export type ShowSlot = S["ShowSlot"];
export type Version = S["Version"];
export type Home = S["Home"];
export type Fill = ShowSlot["fill"];
/** A CBFC certificate. Films not yet certified have `cert: null`. */
export type Cert = NonNullable<FilmCard["cert"]>;
export type CastMember = S["CastMember"];

// Seat map + booking
export type ShowDetail = S["ShowDetail"];
export type TierPrice = S["TierPrice"];
export type Layout = S["Layout"];
export type SeatSnapshot = S["SeatState"];
export type HoldGranted = S["HoldGranted"];
export type Order = S["Order"];
export type OrderSeat = S["OrderSeatOut"];
export type OrderShow = S["OrderShow"];
export type TicketBundle = S["TicketBundle"];
export type TicketOut = S["TicketOut"];
export type MyTickets = S["MyTickets"];
export type TicketGroup = S["TicketGroup"];

// Accounts
export type Me = S["Me"];
export type BusinessRef = S["BusinessRef"];
export type Door = S["CodeRequest"]["door"];

// Theatre owner
export type OwnerBusiness = S["OwnerBusiness"];
export type OwnerCinema = S["OwnerCinema"];
export type OwnerScreen = S["OwnerScreen"];
export type OwnerScreenDetail = S["OwnerScreenDetail"];
export type OwnerFilmRequest = S["OwnerFilmRequest"];
export type OwnerShow = S["OwnerShow"];
export type OwnerShows = S["OwnerShows"];
export type BulkResult = S["BulkResult"];
export type Bookings = S["Bookings"];
export type Booking = S["Booking"];
export type CheckInResult = S["CheckInResult"];
export type OwnerToday = S["OwnerToday"];
export type RecentOrder = S["RecentOrder"];

// Frontrow staff
export type StaffFilm = S["StaffFilm"];
export type StaffFilmRequest = S["StaffFilmRequest"];
export type StaffBusiness = S["StaffBusiness"];
export type StaffCounts = S["StaffCounts"];
