import Link from "next/link";
import { LogoMark } from "@/components/ui/Logo";

const columns = [
  {
    title: "Product",
    links: ["Agent chat", "Bookings", "Guest CRM", "Analytics", "Notifications", "Pricing"],
  },
  {
    title: "Company",
    links: ["About", "Customers", "Careers", "Press kit", "Contact"],
  },
  {
    title: "Resources",
    links: ["Documentation", "MCP tools", "API reference", "Changelog", "Status"],
    badge: "Changelog",
  },
  {
    title: "Legal",
    links: ["Privacy", "Terms", "Data processing", "Security"],
  },
];

export function SiteFooter() {
  return (
    <footer className="scene-footer grain overflow-hidden text-cream">
      <div className="mx-auto max-w-7xl px-4 pt-20 sm:px-6">
        {/* Newsletter row */}
        <div className="flex flex-col gap-8 border-b border-white/15 pb-14 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-md">
            <p className="eyebrow text-cream/60">The monsoon memo</p>
            <h3 className="display mt-3 text-4xl sm:text-5xl">
              Field notes for <em>Bali</em> hosts, once a month.
            </h3>
          </div>
          <form className="glass-dark flex w-full max-w-md items-center rounded-full p-1.5 pl-5">
            <input
              type="email"
              placeholder="you@villa.com"
              aria-label="Email address"
              className="w-full bg-transparent text-sm text-cream outline-none placeholder:text-cream/50"
            />
            <button
              type="button"
              className="shrink-0 rounded-full bg-lime px-4 py-2 text-sm font-medium text-coal transition-colors hover:bg-lime-deep"
            >
              Subscribe
            </button>
          </form>
        </div>

        {/* Link columns */}
        <div className="grid grid-cols-2 gap-10 py-14 md:grid-cols-4">
          {columns.map((col) => (
            <div key={col.title}>
              <p className="eyebrow text-cream/55">{col.title}</p>
              <ul className="mt-5 space-y-3">
                {col.links.map((link) => (
                  <li key={link}>
                    <Link
                      href="#"
                      className="inline-flex items-center gap-2 text-[15px] text-cream/90 transition-colors hover:text-lime"
                    >
                      {link}
                      {col.badge === link && (
                        <span className="rounded-full bg-cream px-1.5 py-px text-[10px] font-medium text-coal">
                          New
                        </span>
                      )}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Oversized wordmark */}
        <div className="flex items-end justify-center gap-3 pb-[4vw] sm:gap-6 xl:pb-12">
          <LogoMark className="mb-[3%] h-[9vw] max-h-24 w-[9vw] max-w-24 shrink-0 text-cream/90" />
          <p className="display select-none text-[19vw] leading-[0.8] text-cream/95 xl:text-[240px]">
            VillaOps
          </p>
        </div>

        <div className="flex flex-col gap-3 border-t border-white/15 py-6 text-[13px] text-cream/60 sm:flex-row sm:items-center sm:justify-between">
          <p>© 2026 VillaOps AI. Made with care in Canggu, Bali.</p>
          <div className="flex items-center gap-2">
            <span className="live-dot" />
            <span className="font-mono text-[11px] uppercase tracking-widest">All systems normal</span>
            <span className="mx-2 text-cream/30">·</span>
            <Link href="#" className="hover:text-cream">
              Privacy
            </Link>
            <span className="text-cream/30">·</span>
            <Link href="#" className="hover:text-cream">
              Terms
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
