import Link from "next/link";

export function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2.5 font-cond text-[26px] leading-none font-bold tracking-[.03em] no-underline">
      <svg viewBox="0 0 64 64" aria-hidden="true" className="size-[30px]">
        <rect width="64" height="64" rx="8" fill="#F5EFE6" />
        <rect x="10" y="30" width="12" height="16" rx="3" fill="#2A0B1E" />
        <rect x="41" y="30" width="12" height="16" rx="3" fill="#2A0B1E" />
        <rect x="26" y="26" width="12" height="20" rx="3" fill="#E63946" />
        <rect x="8" y="48" width="48" height="6" rx="2" fill="#2A0B1E" opacity=".4" />
      </svg>
      Frontrow
    </Link>
  );
}
