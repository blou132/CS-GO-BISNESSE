import type { Metadata } from "next";
import { LoginForm } from "@/components/login-form";
import { Icon } from "@/components/icons";
import { safeNextPath } from "@/lib/request-security";

export const metadata: Metadata = { title: "Connexion" };

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const { next } = await searchParams;
  return (
    <main className="login-shell">
      <section className="login-panel" aria-labelledby="login-title">
        <div className="login-brand" aria-hidden="true">
          <span className="brand-mark">a<span>↗</span></span>
          <span className="brand-name">arbitrage<span>CS2 MARKET INTELLIGENCE</span></span>
        </div>
        <div className="login-heading">
          <span className="login-icon"><Icon name="lock" size={20} /></span>
          <div>
            <p className="eyebrow">ESPACE PRIVÉ</p>
            <h1 id="login-title">Connexion administrateur</h1>
          </div>
        </div>
        <LoginForm nextPath={safeNextPath(next)} />
      </section>
    </main>
  );
}
