import type { Metadata, Viewport } from "next";
import { Barlow, Barlow_Condensed, JetBrains_Mono } from "next/font/google";
import { SITE_URL } from "@/lib/site";
import "./globals.css";

const cond = Barlow_Condensed({ subsets: ["latin"], variable: "--font-barlow-cond", display: "swap", weight: ["500", "600", "700", "800"] });
const sans = Barlow({ subsets: ["latin"], variable: "--font-barlow", display: "swap", weight: ["400", "500", "600"] });
// The countdown is the only mono text (04-ui-mockups); not preloaded until the seat map needs it.
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jetbrains", display: "swap", weight: ["500"], preload: false });

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: "Frontrow — pick your seat, live", template: "%s · Frontrow" },
  description: "Movie and concert ticketing with a live seat map: seats are held for ten minutes the moment you tap them.",
  icons: { icon: "/favicon.svg" },
};

export const viewport: Viewport = { themeColor: "#2A0B1E" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`dark ${cond.variable} ${sans.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
