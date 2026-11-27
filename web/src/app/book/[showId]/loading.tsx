import { Block, Loading } from "@/components/site/Skeleton";

export default function BookLoading() {
  return (
    <Loading label="Loading the seat map">
      <div aria-hidden="true" className="fr-header h-[60px]" />
      <div className="mx-auto w-[min(1440px,100%)] gap-2 px-4 pt-4 lg:grid lg:h-[calc(100dvh-69px)] lg:grid-cols-[1fr_380px] lg:px-10">
        <div className="grid content-start gap-3">
          <Block className="h-8 w-2/3 max-w-[420px]" />
          <Block className="h-[440px] lg:h-[calc(100dvh-200px)]" />
          <Block className="h-4 w-1/2" />
        </div>
        <Block className="mt-6 hidden h-[calc(100dvh-140px)] bg-paper/10 lg:block" />
      </div>
    </Loading>
  );
}
