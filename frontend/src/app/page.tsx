import Link from "next/link";
import { AnnouncementBar, SiteNav } from "@/components/marketing/SiteNav";
import { SiteFooter } from "@/components/marketing/SiteFooter";
import { LogoMark } from "@/components/ui/Logo";

const tickerRows = [
  ["Searching bookings", "Checking availability", "Drafting welcome note"],
  ["Looking up guest", "Crunching occupancy", "Syncing calendar"],
  ["Confirming check-in", "Flagging late arrival", "Summarising revenue"],
];

const tools = [
  "booking_search",
  "booking_create",
  "booking_update",
  "booking_analytics",
  "guest_lookup",
  "guest_create",
  "guest_update",
  "guest_delete",
  "property_list",
  "property_create",
  "property_update",
  "property_manage",
  "property_delete",
  "send_notification",
  "web_search_exa",
];

const villas = ["Le Ayu Canggu", "Pitu Village", "Da Vinci Villa", "Umah Anyar", "Capung Asri", "Rumah Kayu", "Sawah Indah"];

const avatars = ["#c4703f", "#8c5a3f", "#6f8450", "#2f2c25"];

function Avatars() {
  return (
    <div className="flex -space-x-2.5">
      {avatars.map((c, i) => (
        <span
          key={c}
          className="flex h-9 w-9 items-center justify-center rounded-full border-2 border-cream font-serif text-sm text-cream"
          style={{ background: c }}
        >
          {"KWAD"[i]}
        </span>
      ))}
    </div>
  );
}

function SendIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 19V5m0 0-6 6m6-6 6 6" />
    </svg>
  );
}

/* ---------- Hero showcase cards (Bailey Hart style) ---------- */

function ChatSceneCard() {
  return (
    <div className="scene-sunset grain relative flex h-[440px] flex-col justify-end overflow-hidden rounded-[28px] p-5 sm:p-6">
      <div className="space-y-3">
        <div className="flex flex-col items-start gap-1.5">
          <span className="eyebrow pl-1 text-white/80">You</span>
          <span className="glass rounded-[20px] px-4 py-2 text-[14px] text-coal">Who&apos;s checking in tomorrow?</span>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <span className="eyebrow pr-1 text-white/80">VillaOps</span>
          <span className="rounded-[20px] bg-white px-4 py-2.5 text-[14px] text-coal shadow-sm">
            Two arrivals. Yuki at Capung Asri at 2pm, plus a spa request. Shall I book it?
          </span>
        </div>
        <div className="glass flex items-center justify-between rounded-full py-1.5 pl-4 pr-1.5">
          <span className="truncate text-[14px] text-coal/60">Yes, book the spa for 4pm</span>
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-lime text-coal">
            <SendIcon />
          </span>
        </div>
      </div>
    </div>
  );
}

function QuoteSceneCard() {
  return (
    <div className="scene-jungle grain relative flex h-[440px] flex-col justify-between overflow-hidden rounded-[28px] p-6">
      <div className="flex items-center justify-between">
        <span className="glass-dark flex h-10 w-10 items-center justify-center rounded-full text-cream">
          <svg className="ml-0.5 h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor">
            <path d="M8 5v14l11-7z" />
          </svg>
        </span>
        <span className="font-mono text-sm font-semibold uppercase tracking-[0.25em] text-cream/90">Umah Anyar</span>
      </div>
      <div>
        <p className="display text-[30px] leading-[1.05] text-cream">
          &ldquo;Occupancy is up 18% and I haven&apos;t opened a spreadsheet since June.&rdquo;
        </p>
        <p className="mt-4 text-sm font-medium text-cream">Komang Wirawan</p>
        <p className="text-[13px] text-cream/65">Owner, Umah Anyar Villas Ubud</p>
      </div>
    </div>
  );
}

function StatSceneCard() {
  return (
    <div className="scene-dusk grain relative flex h-[440px] flex-col justify-between overflow-hidden rounded-[28px] p-6">
      <div className="glass rounded-2xl p-4">
        <div className="flex items-center justify-between">
          <span className="eyebrow text-coal/60">Occupancy · November</span>
        </div>
        <p className="display mt-2 text-5xl text-coal">40.0%</p>
        <div className="mt-3 flex h-14 items-end gap-1.5">
          {[38, 52, 44, 61, 48, 72, 58, 80, 66, 54].map((h, i) => (
            <span
              key={i}
              className={`flex-1 rounded-t-[4px] ${i === 7 ? "bg-coal" : "bg-coal/20"}`}
              style={{ height: `${h}%` }}
            />
          ))}
        </div>
      </div>
      <div className="glass-dark space-y-2 overflow-hidden rounded-2xl p-4">
        {["Crunching occupancy", "Comparing properties", "Writing summary"].map((t, i) => (
          <div key={t} className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.14em] text-cream/90">
            <span className={`h-1.5 w-1.5 rounded-full ${i === 2 ? "bg-lime" : "bg-cream/40"}`} />
            {t}
            {i < 2 && <span className="ml-auto text-cream/50">Done</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ---------- Feature mini-UIs (Prospect style) ---------- */

function FeatureTicker() {
  return (
    <div className="space-y-2 overflow-hidden">
      {tickerRows.map((row, r) => (
        <div key={r} className="flex w-max animate-marquee gap-2" style={{ animationDuration: `${22 + r * 6}s`, animationDirection: r % 2 ? "reverse" : "normal" }}>
          {[...row, ...row, ...row, ...row].map((t, i) => (
            <span key={i} className="eyebrow whitespace-nowrap rounded-full bg-cream px-3 py-1.5 text-gray-600">
              {t}
            </span>
          ))}
        </div>
      ))}
    </div>
  );
}

function FeatureApproval() {
  return (
    <div className="rounded-2xl bg-cream p-4 shadow-[0_1px_0_rgb(47_44_37/0.06)]">
      <p className="eyebrow text-gray-500">Approval needed</p>
      <p className="mt-2 text-sm font-medium text-ink">Cancel booking #2930 · Rumah Kayu</p>
      <p className="text-[13px] text-gray-500">Nov 21 – 24 · 1 guest · $366.00</p>
      <div className="mt-4 flex gap-2">
        <span className="btn-ink !px-4 !py-1.5 !text-[13px]">Confirm</span>
        <span className="btn-sand !bg-white !px-4 !py-1.5 !text-[13px]">Keep booking</span>
      </div>
    </div>
  );
}

function FeatureChart() {
  return (
    <div className="rounded-2xl bg-cream p-4">
      <div className="flex items-baseline justify-between">
        <p className="eyebrow text-gray-500">Revenue summary</p>
        <p className="text-xs text-gray-400">Aug – Nov</p>
      </div>
      <p className="display mt-1 text-4xl">$18,420</p>
      <svg viewBox="0 0 200 60" className="mt-3 h-16 w-full" preserveAspectRatio="none">
        <defs>
          <linearGradient id="rev" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="#2f2c25" stopOpacity="0.18" />
            <stop offset="1" stopColor="#2f2c25" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d="M0 48 C 30 44, 45 30, 70 34 S 110 18, 135 22 S 175 6, 200 8 L200 60 L0 60 Z" fill="url(#rev)" />
        <path d="M0 48 C 30 44, 45 30, 70 34 S 110 18, 135 22 S 175 6, 200 8" fill="none" stroke="#2f2c25" strokeWidth="1.6" />
        <circle cx="200" cy="8" r="3.5" fill="#d5f500" stroke="#2f2c25" strokeWidth="1.2" />
      </svg>
      <div className="mt-1 flex justify-between font-mono text-[10px] uppercase tracking-widest text-gray-400">
        <span>Aug</span>
        <span>Sep</span>
        <span>Oct</span>
        <span>Nov</span>
      </div>
    </div>
  );
}

const features = [
  {
    eyebrow: "01 · Agent chat",
    title: "Ask in plain words. Get it done.",
    body: "Search bookings, look up guests, or draft a booking just by asking. The agent picks the right tool and shows its work as it goes.",
    visual: <FeatureTicker />,
  },
  {
    eyebrow: "02 · Human in the loop",
    title: "Nothing destructive without a yes.",
    body: "Deletes, cancellations and edits pause for your approval with a clear summary, so the agent never surprises a guest.",
    visual: <FeatureApproval />,
  },
  {
    eyebrow: "03 · Live analytics",
    title: "Occupancy and revenue, on tap.",
    body: "See how every villa is performing this month, and ask follow-up questions in the same conversation.",
    visual: <FeatureChart />,
  },
];

const testimonials = [
  {
    quote:
      "VillaOps replaced three tools and a WhatsApp group. Check-in days used to be chaos; now the agent has everything lined up before breakfast.",
    name: "Kadek Ayu",
    role: "Operations Lead, Le Ayu Villa Canggu",
  },
  {
    quote:
      "Setup took ten minutes. The approval step is what sold me. It drafts everything, but nothing goes out until I say so.",
    name: "Wayan Dharma",
    role: "Owner, Pitu Village Escape",
  },
  {
    quote:
      "I ask it for the month's occupancy every Monday. It answers in seconds and catches the gaps I'd have missed.",
    name: "Sofia Marchetti",
    role: "GM, Da Vinci Villa by Nagisa",
  },
];

const stats = [
  { value: "15", label: "Tools the agent can use" },
  { value: "<3s", label: "Typical answer time" },
  { value: "24/7", label: "Always on, even in Nyepi" },
  { value: "0", label: "Unapproved destructive actions" },
];

export default function Home() {
  return (
    <div className="min-h-screen bg-cream">
      <AnnouncementBar />
      <SiteNav />

      {/* ---------------- Hero ---------------- */}
      <section className="mx-auto max-w-7xl px-4 pb-16 pt-16 text-center sm:px-6 sm:pt-24">
        <p className="eyebrow animate-fade-up text-gray-600">Welcome to VillaOps</p>
        <h1 className="display mx-auto mt-6 max-w-4xl animate-fade-up text-[56px] text-ink [animation-delay:80ms] sm:text-[84px] lg:text-[104px]">
          Run your villas on <em>autopilot</em>, not on spreadsheets.
        </h1>
        <p className="mx-auto mt-7 max-w-xl animate-fade-up text-lg leading-relaxed text-gray-600 [animation-delay:160ms]">
          VillaOps is an AI operations agent for Bali property managers. It finds what matters in your bookings, handles the
          routine work, and asks before it changes anything.
        </p>
        <div className="mt-9 flex animate-fade-up flex-wrap items-center justify-center gap-3 [animation-delay:240ms]">
          <Link href="/register" className="btn-ink !px-6 !py-3">
            Get started free
          </Link>
          <Link href="/login" className="btn-sand !px-6 !py-3">
            Try the demo
          </Link>
        </div>
        <div className="mt-8 flex animate-fade-up items-center justify-center gap-3 [animation-delay:320ms]">
          <Avatars />
          <p className="text-left text-[13px] leading-tight text-gray-600">
            <span className="font-medium text-ink">Rated 4.9/5</span>
            <br />
            by 120+ hosts across Bali
          </p>
        </div>
      </section>

      {/* ---------------- Showcase cards ---------------- */}
      <section id="agent" className="mx-auto max-w-7xl px-4 sm:px-6">
        <div className="grid gap-4 md:grid-cols-3">
          <ChatSceneCard />
          <QuoteSceneCard />
          <StatSceneCard />
        </div>
      </section>

      {/* ---------------- Logo strip ---------------- */}
      <section id="customers" className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
        <p className="text-center text-[13px] text-gray-500">Trusted by independent villas from Uluwatu to Ubud</p>
        <div className="relative mt-8 overflow-hidden [mask-image:linear-gradient(90deg,transparent,#000_12%,#000_88%,transparent)]">
          <div className="flex w-max animate-marquee gap-14">
            {[...villas, ...villas].map((v, i) => (
              <span key={i} className="flex items-center gap-2 whitespace-nowrap font-serif text-2xl text-gray-500">
                <LogoMark className="h-4 w-4 text-gray-400" />
                {v}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------- Statement (Decart style) ---------------- */}
      <section className="mx-auto max-w-5xl px-4 py-16 sm:px-6 sm:py-24">
        <p className="text-[28px] leading-[1.25] tracking-tight text-gray-400 sm:text-[40px]">
          VillaOps <span className="text-ink">reads your bookings</span>, remembers your guests, and{" "}
          <span className="text-ink">acts on your behalf</span>. It searches, schedules and summarises, then waits for{" "}
          <span className="font-serif italic text-ink">your yes</span> before anything changes.
        </p>
      </section>

      {/* ---------------- Features (Prospect style) ---------------- */}
      <section id="product" className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <p className="eyebrow text-gray-600">AI features</p>
          <h2 className="display mt-4 text-5xl sm:text-6xl">
            Intelligence that knows <em>your</em> villas.
          </h2>
          <p className="mt-5 text-gray-600">
            Built on LangGraph and the Model Context Protocol, so every answer is grounded in your real data.
          </p>
        </div>

        <div className="mt-14 grid gap-4 lg:grid-cols-3">
          {features.map((f) => (
            <article key={f.title} className="flex min-w-0 flex-col overflow-hidden rounded-[28px] bg-sand p-6 sm:p-7">
              <div className="min-h-[190px]">{f.visual}</div>
              <p className="eyebrow mt-8 text-gray-500">{f.eyebrow}</p>
              <h3 className="mt-3 text-[22px] font-medium tracking-tight text-ink">{f.title}</h3>
              <p className="mt-2 text-[15px] leading-relaxed text-gray-600">{f.body}</p>
              <Link href="/register" className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-ink">
                Continue reading <span aria-hidden="true">→</span>
              </Link>
            </article>
          ))}
        </div>
      </section>

      {/* ---------------- Toolbelt ---------------- */}
      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
        <div className="grid items-center gap-10 rounded-[32px] bg-coal p-8 text-cream sm:p-12 lg:grid-cols-[1fr_1.2fr]">
          <div>
            <p className="eyebrow text-cream/50">The toolbelt</p>
            <h2 className="display mt-4 text-5xl">
              Fifteen tools.
              <br />
              <em className="text-lime">One</em> conversation.
            </h2>
            <p className="mt-5 max-w-sm text-cream/70">
              Each capability is an MCP tool the agent can call, scoped to your account, with timeouts, retries and
              model failover built in.
            </p>
            <Link href="/register" className="mt-8 inline-flex items-center gap-2 rounded-full bg-lime px-5 py-2.5 text-sm font-medium text-coal">
              Explore the agent
            </Link>
          </div>
          <div className="flex flex-wrap gap-2">
            {tools.map((t) => (
              <span
                key={t}
                className="rounded-full border border-white/12 bg-white/[0.04] px-3.5 py-2 font-mono text-[12px] text-cream/85"
              >
                {t}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------- Stats (Bailey Hart style) ---------------- */}
      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
        <div className="grid grid-cols-2 gap-y-10 border-y border-gray-200 py-12 lg:grid-cols-4">
          {stats.map((s) => (
            <div key={s.label} className="px-2 text-center lg:border-r lg:border-gray-200 lg:last:border-r-0">
              <p className="display text-6xl sm:text-7xl">{s.value}</p>
              <p className="eyebrow mt-3 text-gray-500">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ---------------- Testimonials ---------------- */}
      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
        <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
          <div>
            <p className="eyebrow text-gray-600">Why hosts choose VillaOps</p>
            <h2 className="display mt-4 max-w-xl text-5xl sm:text-6xl">Less admin. More time with <em>your guests</em>.</h2>
          </div>
          <Link href="/register" className="btn-sand self-start sm:self-auto">
            Meet our customers
          </Link>
        </div>
        <div className="mt-12 grid gap-4 md:grid-cols-3">
          {testimonials.map((t) => (
            <figure key={t.name} className="flex flex-col justify-between rounded-[28px] border border-gray-200 bg-white p-7">
              <blockquote className="text-[17px] leading-relaxed text-ink">&ldquo;{t.quote}&rdquo;</blockquote>
              <figcaption className="mt-8 flex items-center gap-3">
                <span className="flex h-10 w-10 items-center justify-center rounded-full bg-sand font-serif text-lg">
                  {t.name.charAt(0)}
                </span>
                <span>
                  <span className="block text-sm font-medium text-ink">{t.name}</span>
                  <span className="block text-[13px] text-gray-500">{t.role}</span>
                </span>
              </figcaption>
            </figure>
          ))}
        </div>
      </section>

      {/* ---------------- Changelog + CTA ---------------- */}
      <section id="changelog" className="mx-auto max-w-7xl px-4 pb-24 pt-8 sm:px-6">
        <div className="scene-sunset grain relative overflow-hidden rounded-[32px] px-6 py-16 text-center sm:px-12 sm:py-24">
          <p className="eyebrow text-coal/70">Changelog · November 2026</p>
          <h2 className="display mx-auto mt-4 max-w-3xl text-5xl text-coal sm:text-7xl">
            Hand off the busywork. <em>Keep</em> the hospitality.
          </h2>
          <p className="mx-auto mt-5 max-w-lg text-coal/75">
            New: MCP 2 transport, automatic Gemini failover, and a redesigned agent workspace.
          </p>
          <div className="mt-9 flex flex-wrap justify-center gap-3">
            <Link href="/register" className="btn-ink !px-6 !py-3">
              Start for free
            </Link>
            <Link href="/pricing" className="glass rounded-full px-6 py-3 text-sm font-medium text-coal">
              View pricing
            </Link>
          </div>
        </div>
      </section>

      <SiteFooter />
    </div>
  );
}
