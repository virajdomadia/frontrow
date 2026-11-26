import { CinemaForm } from "@/components/owner/CinemaForm";
import { PageHead } from "@/components/owner/ui";

export const metadata = { title: "Add a cinema" };

export default function NewCinemaPage() {
  return (
    <>
      <PageHead title="Add a cinema" sub="Screens come next." back={{ href: "/owner/cinemas", label: "Cinemas" }} />
      <div className="max-w-[760px]">
        <CinemaForm />
      </div>
    </>
  );
}
