"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Logo } from "@/components/ui/Logo";

const links = [
  { label: "Product", href: "/#product" },
  { label: "Agent", href: "/#agent" },
  { label: "Customers", href: "/#customers" },
  { label: "Pricing", href: "/pricing" },
  { label: "Changelog", href: "/#changelog" },
];

export function AnnouncementBar() {
  return (
    <div className="bg-linen px-4 py-2 text-center text-[13px] text-ink">
      <span className="mr-2 inline-flex translate-y-[-1px] items-center rounded-full bg-lime px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-widest text-coal">
        New
      </span>
      The VillaOps agent now runs on MCP 2 with automatic model failover.{" "}
      <Link href="/#changelog" className="font-medium underline underline-offset-2">
        Read
      </Link>
    </div>
  );
}

export function SiteNav({ appHref }: { appHref?: string } = {}) {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={`sticky top-0 z-50 transition-[background,box-shadow] duration-200 ${
        scrolled ? "bg-cream/85 shadow-[0_1px_0_rgb(47_44_37/0.08)] backdrop-blur-md" : "bg-cream"
      }`}
    >
      <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
        <Logo />

        <div className="hidden items-center gap-1 lg:flex">
          {links.map((l) => (
            <Link
              key={l.label}
              href={l.href}
              className="rounded-full px-3.5 py-2 text-[14px] text-gray-700 transition-colors hover:bg-sand hover:text-ink"
            >
              {l.label}
            </Link>
          ))}
        </div>

        <div className="flex items-center gap-2">
          {appHref ? (
            <Link href={appHref} className="btn-ink !py-2">
              Open app
            </Link>
          ) : (
            <>
              <Link href="/login" className="btn-sand hidden !py-2 sm:inline-flex">
                Sign in
              </Link>
              <Link href="/register" className="btn-ink !py-2">
                Get started
              </Link>
            </>
          )}
          <button
            type="button"
            onClick={() => setOpen(!open)}
            aria-label="Toggle menu"
            aria-expanded={open}
            className="ml-1 flex h-9 w-9 items-center justify-center rounded-full bg-sand lg:hidden"
          >
            <span className="relative block h-3 w-4">
              <span
                className={`absolute left-0 h-[1.5px] w-4 bg-ink transition-transform duration-200 ${open ? "top-1.5 rotate-45" : "top-0"}`}
              />
              <span
                className={`absolute left-0 top-1.5 h-[1.5px] w-4 bg-ink transition-opacity ${open ? "opacity-0" : ""}`}
              />
              <span
                className={`absolute left-0 h-[1.5px] w-4 bg-ink transition-transform duration-200 ${open ? "top-1.5 -rotate-45" : "top-3"}`}
              />
            </span>
          </button>
        </div>
      </nav>

      {open && (
        <div className="border-t border-gray-200 bg-cream px-4 pb-6 pt-2 lg:hidden">
          {links.map((l) => (
            <Link
              key={l.label}
              href={l.href}
              onClick={() => setOpen(false)}
              className="flex items-center justify-between border-b border-gray-200 py-4 font-serif text-2xl text-ink"
            >
              {l.label}
              <span className="font-mono text-xs text-gray-400">→</span>
            </Link>
          ))}
          <Link href="/login" className="btn-sand mt-5 w-full">
            Sign in
          </Link>
        </div>
      )}
    </header>
  );
}
