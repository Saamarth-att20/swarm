// Small line icons used by the new design. Author: Saamarth Attray
import type { ReactNode } from "react";

const icons = {
  arrow: <path d="M5 12h14M14 7l5 5-5 5" />,
  pin: (
    <>
      <path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z" />
      <circle cx="12" cy="10" r="2.5" />
    </>
  ),
  check: <path d="m5 12 4 4L19 6" />,
  phone: <path d="M7 3h3l1.5 4-2 1.5a15 15 0 0 0 6 6L17 12l4 2v3a4 4 0 0 1-4 4C9.3 20.2 3.8 14.7 3 7a4 4 0 0 1 4-4Z" />,
  route: (
    <>
      <circle cx="6" cy="19" r="2" />
      <circle cx="18" cy="5" r="2" />
      <path d="M8 19h2a3 3 0 0 0 3-3V8a3 3 0 0 1 3-3" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  menu: <path d="M4 8h16M4 16h16" />,
  close: <path d="m6 6 12 12M18 6 6 18" />,
  spark: (
    <>
      <path d="m12 3 1.4 4.1L17 9l-3.6 2.1L12 15l-1.4-3.9L7 9l3.6-1.9L12 3Z" />
      <path d="m18.5 15 .7 2.1 1.8.9-1.8 1-.7 2-.7-2-1.8-1 1.8-.9.7-2.1Z" />
    </>
  ),
} satisfies Record<string, ReactNode>;

export type IconName = keyof typeof icons;

export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return (
    <svg
      className="icon"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {icons[name]}
    </svg>
  );
}