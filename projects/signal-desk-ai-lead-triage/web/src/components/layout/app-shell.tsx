"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const navigation = [
  { href: "/", label: "Lead inbox", icon: "▤" },
  { href: "/playground/react-practice", label: "Brief builder", icon: "⌁" },
  { href: "/health", label: "System health", icon: "◉" },
];

function currentSection(pathname: string) {
  if (pathname === "/") return "Lead inbox";
  if (pathname.startsWith("/leads/")) return "Lead workspace";
  if (pathname.startsWith("/playground/accessibility")) return "Accessible widgets";
  if (pathname.startsWith("/playground/motion")) return "Motion states";
  if (pathname.startsWith("/playground/3d")) return "3D study";
  if (pathname.startsWith("/playground/shader")) return "Shader study";
  if (pathname.startsWith("/playground/react-practice")) return "Brief builder";
  return "System health";
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const section = currentSection(pathname);

  return (
    <div className="app-shell">
      <aside className="side-rail">
        <Link className="brand" href="/" aria-label="Signal Desk home">
          <span className="brand-mark" aria-hidden="true">S</span>
          <span><span className="brand-name">Signal Desk</span><span className="brand-caption">STUDIO INTAKE</span></span>
        </Link>
        <p className="nav-caption">Workspace</p>
        <nav className="side-nav" aria-label="Main navigation">
          {navigation.map((item) => {
            const active = item.href === "/" ? pathname === "/" || pathname.startsWith("/leads/") : pathname.startsWith(item.href);
            return <Link href={item.href} key={item.href} aria-current={active ? "page" : undefined}><span className="nav-icon" aria-hidden="true">{item.icon}</span>{item.label}</Link>;
          })}
        </nav>
        <p className="nav-caption" style={{ marginTop: 25 }}>Practice</p>
        <nav className="side-nav" aria-label="Practice assignments">
          <Link href="/playground/accessibility" aria-current={pathname.startsWith("/playground/accessibility") ? "page" : undefined}><span className="nav-icon" aria-hidden="true">◫</span>Accessible widgets</Link>
          <Link href="/playground/motion" aria-current={pathname.startsWith("/playground/motion") ? "page" : undefined}><span className="nav-icon" aria-hidden="true">↝</span>Motion states</Link>
          <Link href="/playground/3d" aria-current={pathname.startsWith("/playground/3d") ? "page" : undefined}><span className="nav-icon" aria-hidden="true">◍</span>3D scene</Link>
          <Link href="/playground/shader" aria-current={pathname.startsWith("/playground/shader") ? "page" : undefined}><span className="nav-icon" aria-hidden="true">✳</span>Shader hero</Link>
        </nav>
        <div className="side-note"><strong>Person-led review</strong><br />Scores are signals to inspect, never an automated decision.</div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div className="breadcrumbs"><span>Signal Desk</span><span aria-hidden="true">/</span><span>{section}</span></div>
          <div className="top-actions"><span className="status-message">Local model</span><span className="avatar" aria-label="Sample operator">SD</span></div>
        </header>
        {children}
      </div>
    </div>
  );
}
