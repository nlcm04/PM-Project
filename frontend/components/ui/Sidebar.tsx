"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutGrid, LineChart, Sparkles } from "lucide-react";

const NAV_ITEMS = [
  { href: "/discovery", label: "Daily Discovery", icon: Sparkles },
  { href: "/portfolio", label: "Portfolio Health", icon: LineChart },
];

const IS_DEMO = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-64 flex-col bg-brown-950 border-r border-brown-700/60 px-4 py-6">
      <div className="mb-2 flex items-center gap-2 px-2">
        <LayoutGrid className="h-6 w-6 text-amber-400" />
        <span className="text-lg font-bold tracking-tight text-cream">HOSE Quant</span>
      </div>
      {IS_DEMO && (
        <div className="mb-6 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1.5 text-center text-[11px] font-medium text-amber-300">
          Demo mode &mdash; sample data, no live backend
        </div>
      )}
      <nav className={`flex flex-col gap-1 ${IS_DEMO ? "" : "mt-6"}`}>
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = pathname?.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                active
                  ? "bg-amber-500/15 text-amber-300"
                  : "text-cream/70 hover:bg-brown-900 hover:text-cream"
              }`}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto rounded-lg bg-brown-900 px-3 py-3 text-xs text-cream/50">
        Human-in-the-loop only. Nothing here executes trades automatically.
      </div>
    </aside>
  );
}
