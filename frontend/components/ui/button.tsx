import Link from "next/link";
import { forwardRef, type AnchorHTMLAttributes, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const styles: Record<Variant, string> = {
  primary: "bg-ink text-paper hover:bg-[#1d3159] disabled:bg-ink-faint",
  secondary: "bg-card text-ink border border-line hover:border-ink-soft disabled:text-ink-faint",
  ghost: "text-ink-soft hover:bg-ink/5 disabled:text-ink-faint",
  danger: "bg-card text-failed border border-failed/40 hover:bg-failed/5",
};

type Size = "sm" | "md" | "lg";

export const buttonClass = (variant: Variant = "primary", size: Size = "md", className?: string) =>
  cn(
    "inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors disabled:cursor-not-allowed",
    size === "lg" ? "h-12 px-6 text-base" : size === "md" ? "h-11 px-5 text-[15px]" : "h-8 px-3 text-sm",
    styles[variant],
    className,
  );

export const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }>(
  ({ className, variant = "primary", size = "md", ...props }, ref) => (
    <button ref={ref} className={buttonClass(variant, size, className)} {...props} />
  ),
);
Button.displayName = "Button";

/** A link that looks like a button (navigation should be a link, not a button). */
export function ButtonLink({
  className,
  variant = "primary",
  size = "md",
  href,
  ...props
}: Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & { href: string; variant?: Variant; size?: Size }) {
  return <Link href={href} className={buttonClass(variant, size, className)} {...props} />;
}