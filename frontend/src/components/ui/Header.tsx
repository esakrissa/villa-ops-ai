"use client";

import { usePathname } from "next/navigation";
import { Logo } from "./Logo";
import { MenuIcon } from "./icons";

const titles: Record<string, string> = {
  "/dashboard": "Overview",
  "/dashboard/bookings": "Bookings",
  "/dashboard/properties": "Properties",
  "/dashboard/analytics": "Analytics",
  "/dashboard/billing": "Billing",
};

/** Slim top bar for dashboard pages (and the mobile menu on every page). */
export function Header({ onMenuToggle, mobileOnly = false }: { onMenuToggle?: () => void; mobileOnly?: boolean }) {
  const pathname = usePathname();
  const title = titles[pathname] ?? "Workspace";

  return (
    <header
      className={`flex h-14 shrink-0 items-center justify-between border-b border-gray-200/70 bg-cream/80 px-4 backdrop-blur lg:px-8 ${
        mobileOnly ? "lg:hidden" : ""
      }`}
    >
      <div className="flex items-center gap-3">
        {onMenuToggle && (
          <button
            type="button"
            onClick={onMenuToggle}
            aria-label="Open menu"
            className="rounded-lg p-1.5 text-gray-600 hover:bg-gray-100 lg:hidden"
          >
            <MenuIcon />
          </button>
        )}
        <span className="lg:hidden">
          <Logo href="/chat" />
        </span>
        {!mobileOnly && (
          <p className="eyebrow hidden text-gray-500 lg:block">
            Workspace <span className="mx-1.5 text-gray-300">/</span>
            <span className="text-ink">{title}</span>
          </p>
        )}
      </div>
    </header>
  );
}
