"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon, type IconName } from "./icons";
import { MarketProvider, useMarkets } from "./market-provider";
import { dateTime } from "@/lib/format";

const navigation: { href: string; title: string; icon: IconName; detail: string }[] = [
  { href: "/", title: "Dashboard", icon: "dashboard", detail: "Vue d’ensemble" },
  { href: "/scanner", title: "Scanner", icon: "scanner", detail: "Explorer les annonces" },
  { href: "/markets", title: "Marchés", icon: "markets", detail: "Sources et connexions" },
  { href: "/settings/integrations", title: "Intégrations", icon: "settings", detail: "Registre des sources" },
];

function ShellContent({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { mode, data, loading, error, refresh, switchMode } = useMarkets();
  const active = navigation.find((nav) => nav.href === pathname);
  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Aller au contenu</a>
    <aside className="sidebar">
      <Link className="brand" href="/" aria-label="CS2 Arbitrage Hub, accueil"><span className="brand-mark">a<span>↗</span></span><span className="brand-name">arbitrage<span>CS2 MARKET INTELLIGENCE</span></span></Link>
      <div className="workspace-label"><span className="workspace-dot" /> Espace personnel <span className="tiny-label">LOCAL</span></div>
      <div className="nav-heading">ANALYSE</div>
      <nav aria-label="Navigation principale">{navigation.map((nav) => <Link key={nav.href} href={nav.href} className={`nav-link ${pathname === nav.href ? "active" : ""}`} aria-label={nav.title} aria-current={pathname === nav.href ? "page" : undefined}><Icon name={nav.icon} /><span>{nav.title}</span>{pathname === nav.href ? <span className="active-pip" /> : null}</Link>)}</nav>
      <div className="sidebar-note"><Icon name="shield" size={20} /><strong>Observer. Comparer. Décider.</strong><p>Un espace d’analyse privé pour comprendre le marché CS2.</p><span>Lecture seule · Aucun achat automatisé</span></div>
      <div className="sidebar-bottom"><span className="avatar">ME</span><div>Espace local<small>CS2 Arbitrage Hub</small></div><span className="version">V0.14</span></div>
    </aside>
    <div className="main-shell">
      <header className="topbar"><div className="breadcrumb">Espace de travail <span>/</span> <strong>{active?.title ?? "Détail de l’objet"}</strong></div><div className="topbar-actions"><span className={`mode-badge ${mode}`}><i />{mode === "demo" ? "DEMO" : "LIVE"}</span><span className="currency-badge">EUR <span>devise de référence</span></span><button className="button button-small button-ghost" onClick={switchMode} disabled={loading}>{mode === "demo" ? "Passer en live" : "Charger la démo"}</button><form action="/logout" method="post"><button className="icon-button" type="submit" title="Se déconnecter" aria-label="Se déconnecter"><Icon name="logout" /></button></form></div></header>
      <main id="main-content" className="main-content">
        {mode === "demo" ? <div className="notice demo-notice" role="status"><Icon name="info" /><span><strong>Environnement de démonstration.</strong> Tous les prix et objets affichés sont des fixtures de test, sans valeur de marché réelle.</span></div> : null}
        {error ? <div className="notice error-notice" role="alert"><Icon name="warning" /><span><strong>Connexion interrompue.</strong> {error}{data ? " Les dernières observations restent affichées et peuvent être périmées." : ""}</span><button className="text-button" onClick={refresh} disabled={loading}>Réessayer</button></div> : null}
        {data?.warnings.length ? <details className="data-notice"><summary><Icon name="info" /> {data.warnings.length} information{data.warnings.length > 1 ? "s" : ""} sur la qualité des données</summary><ul>{data.warnings.map((warning, index) => <li key={`${index}-${warning}`}>{warning}</li>)}</ul></details> : null}
        {children}
      </main>
      <footer className="footer"><span><i className={`status-dot ${error ? "error" : "idle"}`} />{mode === "demo" ? "Données de test" : "Données observées · estimations non garanties"}</span><span>Dernière synchronisation : {dateTime(data?.last_sync_at)} <span className="footer-zone">· Paris</span></span></footer>
    </div>
  </div>;
}

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (pathname === "/login") return children;
  return <MarketProvider><ShellContent>{children}</ShellContent></MarketProvider>;
}
