import type { CSSProperties } from "react";

const paths = {
  dashboard: "M3 3h7v7H3zM14 3h7v4h-7zM14 11h7v10h-7zM3 14h7v7H3z",
  scanner: "M4 8V4h4M16 4h4v4M20 16v4h-4M8 20H4v-4M8 12h8M12 8v8",
  markets: "M3 21h18M5 21V10h4v11M10 21V3h4v18M15 21V7h4v14",
  arrow: "M7 17 17 7M7 7h10v10",
  chevron: "m9 5 7 7-7 7",
  refresh: "M20 7v5h-5M4 17v-5h5M6 7a7 7 0 0 1 12-2l2 3M4 16l2 3a7 7 0 0 0 12-2",
  search: "M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0",
  filter: "M4 7h16M4 17h16M8 4v6M16 14v6",
  info: "M12 11v6M12 7h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
  clock: "M12 7v5l3 2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
  layers: "m12 3 10 6-10 6L2 9l10-6M2 14l10 6 10-6M2 19l10 6 10-6",
  target: "M12 8v8M8 12h8M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0",
  warning: "m12 3 10 18H2L12 3M12 9v5M12 17h.01",
  back: "M20 12H4m6-6-6 6 6 6",
  check: "m5 12 4 4L19 6",
  activity: "M2 12h4l3-8 6 16 3-8h4",
  shield: "m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3m-4 9 3 3 5-6",
  lock: "M7 11V8a5 5 0 0 1 10 0v3M6 11h12v10H6z",
  logout: "M10 17l5-5-5-5M15 12H3M15 5h4a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-4",
} as const;

export type IconName = keyof typeof paths;

export function Icon({ name, size = 18, className = "", style }: { name: IconName; size?: number; className?: string; style?: CSSProperties }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className={className} style={style} aria-hidden="true"><path d={paths[name]} /></svg>;
}
