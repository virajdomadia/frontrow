import { Block, Loading } from "@/components/site/Skeleton";

export default function PageLoading() {
  return (
    <Loading label="Loading">
      <div className="h-[69px] border-b border-border" />
      <div className="mx-auto grid w-[min(1100px,100%-32px)] gap-6 py-10 lg:grid-cols-[1fr_420px]">
        <div className="grid content-start gap-4">
          <Block className="h-5 w-32" />
          <Block className="h-16 w-4/5" />
          <Block className="h-5 w-3/5" />
        </div>
        <Block className="h-[420px] bg-paper/10" />
      </div>
    </Loading>
  );
}
