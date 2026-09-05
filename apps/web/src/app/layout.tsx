import type { Metadata, Viewport } from "next";
import { Shell } from "@/components/shell";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "CS2 Arbitrage Hub", template: "%s · CS2 Arbitrage Hub" },
  description: "Espace privé d’observation et d’analyse des marchés de skins CS2.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = { colorScheme: "dark", themeColor: "#0b0e0d" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="fr"><body><Shell>{children}</Shell></body></html>;
}
