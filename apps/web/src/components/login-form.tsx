"use client";

import { FormEvent, useState } from "react";
import { Icon } from "./icons";

export function LoginForm({ nextPath }: { nextPath: string }) {
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setSubmitting(true);
    setError(null);
    try {
      const response = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: data.get("username"),
          password: data.get("password"),
        }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        setError(payload?.detail ?? "Connexion impossible.");
        return;
      }
      window.location.assign(nextPath);
    } catch {
      setError("Connexion impossible.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="login-form" onSubmit={submit}>
      <label>
        <span>Identifiant</span>
        <input name="username" type="text" autoComplete="username" required autoFocus maxLength={64} />
      </label>
      <label>
        <span>Mot de passe</span>
        <input name="password" type="password" autoComplete="current-password" required maxLength={1024} />
      </label>
      {error ? <p className="login-error" role="alert">{error}</p> : null}
      <button className="button button-primary login-submit" type="submit" disabled={submitting}>
        <Icon name="lock" size={16} />
        {submitting ? "Connexion…" : "Se connecter"}
      </button>
    </form>
  );
}
