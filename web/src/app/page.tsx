import { Header } from "@/components/landing/Header";
import { Hero } from "@/components/landing/Hero";
import { Shows } from "@/components/landing/Shows";
import { How } from "@/components/landing/How";
import { Organisers } from "@/components/landing/Organisers";
import { Cta } from "@/components/landing/Cta";
import { Footer } from "@/components/landing/Footer";

export default function Home() {
  return (
    <>
      <Header />
      <main>
        <Hero />
        <Shows />
        <How />
        <Organisers />
        <Cta />
      </main>
      <Footer />
    </>
  );
}
