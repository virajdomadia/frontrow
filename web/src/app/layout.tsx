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
  description: "Movie tickets for Bengaluru with a live seat map: a seat is held for you for ten minutes the moment you tap it.",
  icons: { icon: "/favicon.svg" },
};

export const viewport: Viewport = { themeColor: "#7E1A22" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${cond.variable} ${sans.variable} ${mono.variable}`}>
      <body>
        <a
          href="#main"
          className="sr-only z-50 rounded-btn bg-paper px-4 py-2 font-semibold text-ink focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
        >
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}
