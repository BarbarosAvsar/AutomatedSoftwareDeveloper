import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "./utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-3 py-1 text-xs font-medium",
  {
    variants: {
      tone: {
        success: "bg-emerald-500/20 text-emerald-300",
        warning: "bg-amber-500/20 text-amber-300",
        danger: "bg-rose-500/20 text-rose-300",
        neutral: "bg-white/10 text-white/70"
      }
    },
    defaultVariants: {
      tone: "neutral"
    }
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ tone }), className)} {...props} />;
}
