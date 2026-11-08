// Buttons in the new design. Named SdButton so they never clash with components/ui/button.tsx. Author: Saamarth Attray
import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Icon, type IconName } from "@/components/design/Icon";

type Variant = "primary" | "secondary" | "dark" | "ghost";

function Inner({ children, icon, loading }: { children: ReactNode; icon?: IconName; loading?: boolean }) {
  return (
    <>
      {loading && <span className="spinner" />}
      <span>{children}</span>
      {icon && !loading && <Icon name={icon} size={18} />}
    </>
  );
}

export function SdButton({
  variant = "primary",
  icon,
  loading = false,
  disabled,
  type = "button",
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; icon?: IconName; loading?: boolean }) {
  return (
    <button type={type} className={`btn ${variant}`} disabled={disabled || loading} {...rest}>
      <Inner icon={icon} loading={loading}>{children}</Inner>
    </button>
  );
}

/** Navigation should be a link, so this looks like a button but is an anchor. */
export function SdButtonLink({
  href,
  variant = "primary",
  icon,
  children,
}: {
  href: string;
  variant?: Variant;
  icon?: IconName;
  children: ReactNode;
}) {
  return (
    <Link href={href} className={`btn ${variant}`}>
      <Inner icon={icon}>{children}</Inner>
    </Link>
  );
}