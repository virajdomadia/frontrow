import { Button as ButtonPrimitive } from "@base-ui/react/button";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

// shadcn button re-themed to direction B (04-ui-mockups): Barlow Condensed caps, 6 px radius.
// Links use `buttonVariants()` on a <Link> so they stay real anchors.
const variants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 rounded-btn border-2 border-transparent font-cond font-bold uppercase tracking-[.05em] whitespace-nowrap no-underline transition-colors select-none disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default: "bg-red text-white hover:bg-[#d12f3c]",
        outline: "border-screen/35 text-screen hover:border-screen",
        ink: "bg-ink text-paper hover:bg-plum-3",
        paper: "border-ink/30 bg-paper text-ink hover:border-ink",
        ghost: "text-muted-foreground hover:bg-plum-2 hover:text-screen",
        link: "px-0 font-sans font-medium normal-case tracking-normal text-muted-foreground underline-offset-4 hover:text-screen hover:underline",
      },
      size: {
        default: "px-5 py-3 text-xl",
        sm: "px-3.5 py-2 text-base",
        lg: "px-6 py-3.5 text-2xl",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

/** cva + tailwind-merge, so a variant's border/colour replaces the base's instead of racing it. */
const buttonVariants = ({ className, ...props }: VariantProps<typeof variants> & { className?: string } = {}) =>
  cn(variants(props), className);

function Button({
  className,
  variant = "default",
  size = "default",
  ...props
}: Omit<ButtonPrimitive.Props, "className"> & VariantProps<typeof variants> & { className?: string }) {
  return (
    <ButtonPrimitive
      data-slot="button"
      className={buttonVariants({ variant, size, className })}
      {...props}
    />
  );
}

export { Button, buttonVariants };
