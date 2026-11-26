import { cache } from "react";
import { api } from "@/lib/api";
import { getMe } from "@/lib/session";

/** The signed-in user, read once per request (layout and page share it). */
export const staffMe = cache(getMe);

/** Queue sizes for the console nav. */
export const staffCounts = cache(() => api("/staff/counts", { auth: true }));
