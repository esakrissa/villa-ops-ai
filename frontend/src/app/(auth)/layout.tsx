import { Logo } from "@/components/ui/Logo";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="grid min-h-screen bg-cream lg:grid-cols-[1fr_1.05fr]">
      {/* Form column */}
      <div className="flex flex-col px-6 py-6 sm:px-10">
        <Logo />
        <div className="flex flex-1 items-center justify-center py-10">
          <div className="w-full max-w-[400px]">{children}</div>
        </div>
        <p className="text-[12px] text-gray-400">© 2026 VillaOps AI · Made in Bali</p>
      </div>

      {/* Scene column */}
      <div className="hidden p-3 lg:block">
        <div className="scene-sunset grain relative flex h-full flex-col justify-between overflow-hidden rounded-[32px] p-10">
          <p className="eyebrow text-coal/70">The VillaOps agent</p>

          <div className="max-w-md space-y-3">
            <div className="flex flex-col items-start gap-1.5">
              <span className="eyebrow pl-1 text-white/85">You</span>
              <span className="glass rounded-[20px] px-4 py-2.5 text-[14px] text-coal">
                Any late check-outs I should know about this week?
              </span>
            </div>
            <div className="flex flex-col items-end gap-1.5">
              <span className="eyebrow pr-1 text-white/85">VillaOps</span>
              <span className="rounded-[20px] bg-white px-4 py-3 text-[14px] leading-relaxed text-coal shadow-sm">
                One. James at Le Ayu Canggu asked for a 2pm check-out on Thursday. Your next guest arrives at 3pm, so it
                fits. Want me to confirm it with him?
              </span>
            </div>
            <div className="glass-dark flex items-center gap-2 rounded-full px-4 py-2 font-mono text-[11px] uppercase tracking-[0.14em] text-cream/90">
              Searched bookings · Checked availability
            </div>
          </div>

          <div>
            <p className="display max-w-lg text-[44px] text-coal">
              &ldquo;It&apos;s like having an operations manager who never sleeps.&rdquo;
            </p>
            <p className="mt-4 text-sm font-medium text-coal">Kadek Ayu</p>
            <p className="text-[13px] text-coal/65">Operations Lead, Le Ayu Villa Canggu</p>
          </div>
        </div>
      </div>
    </div>
  );
}
