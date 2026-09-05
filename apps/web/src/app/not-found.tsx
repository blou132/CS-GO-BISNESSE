import Link from "next/link";
export default function NotFound() { return <div className="empty-state"><h1>Page introuvable</h1><p>Cette vue n’existe pas dans le MVP.</p><Link className="button button-ghost" href="/">Revenir au dashboard</Link></div>; }
