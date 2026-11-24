import Link from "next/link";

/** Frangipani-inspired dot mark — five petals around a centre. */
export function LogoMark({ className = "h-6 w-6" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <circle cx="12" cy="12" r="2.2" />
      {[0, 72, 144, 216, 288].map((deg) => (
        <ellipse
          key={deg}
          cx="12"
          cy="5.6"
          rx="2.6"
          ry="3.6"
          transform={`rotate(${deg} 12 12)`}
          opacity="0.9"
        />
      ))}
    </svg>
  );
}

export function Logo({
  href = "/",
  className = "",
  tone = "ink",
}: {
  href?: string;
  className?: string;
  tone?: "ink" | "cream";
}) {
  const color = tone === "ink" ? "text-ink" : "text-cream";
  return (
    <Link href={href} className={`inline-flex items-center gap-2 ${color} ${className}`}>
      <LogoMark className="h-6 w-6" />
      <span className="font-serif text-[26px] leading-none tracking-tight">VillaOps</span>
    </Link>
  );
}
