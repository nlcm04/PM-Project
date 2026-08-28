"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutGrid, LineChart, Sparkles } from "lucide-react";

const NAV_ITEMS = [
  { href: "/discovery", label: "Daily Discovery", icon: Sparkles },
  { href: "/portfolio", label: "Portfolio Health", icon: LineChart },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-64 flex-col bg-brown-950 border-r border-brown-700/60 px-4 py-6">
      <div className="mb-8 flex items-center gap-2 px-2">
        <LayoutGrid className="h-6 w-6 text-amber-400" />
        <span className="text-lg font-bold tracking-tight text-cream">HOSE Quant</span>
      </div>
      <nav className="flex flex-col gap-1">
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
