import type { Metadata } from "next";
import { Barlow_Condensed, Barlow } from "next/font/google";
const cond = Barlow_Condensed({ subsets: ["latin"], variable: "--font-cond", display: "swap", weight: ["500", "600", "700", "800"] });
const sans = Barlow({ subsets: ["latin"], variable: "--font-sans", display: "swap", weight: ["400", "500", "600"] });
import "./globals.css";

export const metadata: Metadata = {
  title: "Frontrow \u2014 pick your seat, live",
  description: "Movie and concert ticketing with a live seat map: seats are held for ten minutes the moment you tap them.",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${cond.variable} ${sans.variable}`}>
      <body>{children}</body>
    </html>
  );
}
