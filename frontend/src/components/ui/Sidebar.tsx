"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/hooks/useAuth";
import { Logo, LogoMark } from "./Logo";
import {
  CalendarIcon,
  BookIcon,
  CardIcon,
  ChartIcon,
  ChatIcon,
  CloseIcon,
  GridIcon,
  HomeIcon,
  LogoutIcon,
  PanelLeftIcon,
} from "./icons";

const navItems = [
  { label: "Agent", href: "/chat", icon: ChatIcon },
  { label: "Overview", href: "/dashboard", icon: GridIcon },
  { label: "Bookings", href: "/dashboard/bookings", icon: CalendarIcon },
  { label: "Properties", href: "/dashboard/properties", icon: HomeIcon },
  { label: "Knowledge", href: "/dashboard/knowledge", icon: BookIcon },
  { label: "Analytics", href: "/dashboard/analytics", icon: ChartIcon },
  { label: "Billing", href: "/dashboard/billing", icon: CardIcon },
];

function NavLinks({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav className="flex flex-col gap-0.5">
      {!collapsed && <p className="eyebrow mb-2 px-3 text-gray-400">Workspace</p>}
      {navItems.map(({ label, href, icon: Icon }) => {
        const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            title={collapsed ? label : undefined}
            className={`group flex items-center gap-3 rounded-xl py-2 text-[14px] transition-colors ${
              collapsed ? "justify-center px-0" : "px-3"
            } ${active ? "bg-sand font-medium text-ink" : "text-gray-600 hover:bg-gray-100 hover:text-ink"}`}
          >
            <Icon className="h-[18px] w-[18px] shrink-0" />
            {!collapsed && <span className="truncate">{label}</span>}
          </Link>
        );
      })}
    </nav>
  );
}

function UserBlock({ collapsed }: { collapsed: boolean }) {
  const { user, logout } = useAuth();
  const initial = user?.name?.charAt(0)?.toUpperCase();
  return (
    <div className={`flex items-center gap-2.5 rounded-xl ${collapsed ? "flex-col" : "p-1.5"}`}>
      {user?.avatar_url ? (
        <img src={user.avatar_url} alt="" className="h-8 w-8 shrink-0 rounded-full" />
      ) : initial ? (
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-ink font-serif text-[15px] text-cream">
          {initial}
        </span>
      ) : (
        <span className="h-8 w-8 shrink-0 animate-pulse rounded-full bg-gray-200" aria-label="Loading account" />
      )}
      {!collapsed && (
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-medium text-ink">{user?.name || "Loading…"}</p>
          <p className="truncate text-[12px] text-gray-500">{user?.email}</p>
        </div>
      )}
      <button
        type="button"
        onClick={logout}
        title="Sign out"
        className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-ink"
      >
        <LogoutIcon className="h-4 w-4" />
      </button>
    </div>
  );
}

export function Sidebar({
  open,
  onClose,
  collapsed = false,
  onToggleCollapse,
}: {
  open?: boolean;
  onClose?: () => void;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}) {
  return (
    <>
      {/* Mobile drawer */}
      {open && <div className="fixed inset-0 z-40 bg-coal/30 backdrop-blur-[2px] lg:hidden" onClick={onClose} />}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-72 flex-col bg-cream p-3 shadow-xl transition-transform duration-200 lg:hidden ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-12 items-center justify-between px-2">
          <Logo href="/chat" />
          <button type="button" onClick={onClose} className="rounded-lg p-1.5 text-gray-500 hover:bg-gray-100">
            <CloseIcon className="h-4 w-4" />
          </button>
        </div>
        <div className="mt-4 flex-1">
          <NavLinks collapsed={false} onNavigate={onClose} />
        </div>
        <UserBlock collapsed={false} />
      </aside>

      {/* Desktop rail */}
      <aside
        className={`hidden shrink-0 flex-col border-r border-gray-200/70 bg-cream p-3 transition-[width] duration-200 ease-out lg:flex ${
          collapsed ? "w-[68px]" : "w-60"
        }`}
      >
        <div className={`flex h-12 items-center ${collapsed ? "justify-center" : "justify-between pl-2"}`}>
          {collapsed ? (
            <Link href="/chat" title="VillaOps" className="text-ink">
              <LogoMark className="h-6 w-6" />
            </Link>
          ) : (
            <Logo href="/chat" />
          )}
          {!collapsed && (
            <button
              type="button"
              onClick={onToggleCollapse}
              title="Collapse sidebar"
              aria-label="Collapse sidebar"
              className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-ink"
            >
              <PanelLeftIcon />
            </button>
          )}
        </div>

        {collapsed && (
          <button
            type="button"
            onClick={onToggleCollapse}
            title="Expand sidebar"
            aria-label="Expand sidebar"
            className="mx-auto mt-2 rounded-lg p-2 text-gray-400 transition-colors hover:bg-gray-100 hover:text-ink"
          >
            <PanelLeftIcon />
          </button>
        )}

        <div className="mt-5 flex-1">
          <NavLinks collapsed={collapsed} />
        </div>

        <UserBlock collapsed={collapsed} />
      </aside>
    </>
  );
}
