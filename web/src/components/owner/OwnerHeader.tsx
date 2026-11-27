"use client";

import { usePathname } from "next/navigation";
import { SiteHeader } from "@/components/site/SiteHeader";

const NAV = [
  { key: "overview", href: "/owner", label: "Overview" },
  { key: "today", href: "/owner/today", label: "Today" },
  { key: "cinemas", href: "/owner/cinemas", label: "Cinemas" },
  { key: "films", href: "/owner/films", label: "Films" },
  { key: "shows", href: "/owner/shows", label: "Shows" },
];

/** The oxblood header with the console's sections; the active one follows the path. */
export function OwnerHeader({ business }: { business: string }) {
  const path = usePathname();
  const active =
    path === "/owner"
      ? "overview"
      : path.startsWith("/owner/today")
        ? "today"
        : path.startsWith("/owner/cinemas") || path.startsWith("/owner/screens")
        ? "cinemas"
        : path.startsWith("/owner/films")
          ? "films"
          : "shows";
  return <SiteHeader nav={NAV} active={active} badge={business} wide />;
}
