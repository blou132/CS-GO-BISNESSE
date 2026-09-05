import type { Platform } from "./types";

export const marketNames: Record<Platform, string> = { csfloat: "CSFloat", skinport: "Skinport", dmarket: "DMarket" };

export function numeric(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

export function money(value: string | number | null | undefined, currency = "EUR"): string {
  const amount = numeric(value);
  if (amount === null) return "—";
  try {
    return new Intl.NumberFormat("fr-FR", { style: "currency", currency, maximumFractionDigits: 2 }).format(amount);
  } catch {
    return `${amount.toFixed(2)} ${currency}`;
  }
}

export function percent(value: string | number | null | undefined): string {
  const number = numeric(value);
  return number === null ? "—" : `${number > 0 ? "+" : ""}${number.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %`;
}

export function dateTime(value: string | null | undefined): string {
  if (!value) return "Jamais";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "—";
  return new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Paris" }).format(date);
}

export function observationLabel(type: string): string {
  if (type === "sale" || type === "realized_sale" || type === "sales") return "Vente réalisée";
  if (type === "listing") return "Annonce";
  if (type === "aggregate" || type === "listing_aggregate") return "Agrégat d’annonces";
  if (type === "sale_aggregate" || type === "sales_aggregate") return "Agrégat de ventes";
  return type;
}

export function safeExternalUrl(value: string | null, inspect = false): string | undefined {
  if (!value) return undefined;
  try {
    const url = new URL(value);
    if (url.protocol === "https:" || (inspect && url.protocol === "steam:")) return value;
  } catch { /* Une URL invalide ne devient pas un lien cliquable. */ }
  return undefined;
}
