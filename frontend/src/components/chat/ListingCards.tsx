"use client";

/* eslint-disable @next/next/no-img-element -- remote listing photos from three CDNs; next/image would proxy every one */
import { useRef, useState } from "react";
import { ChevronIcon, ExternalIcon, MapPinIcon, StarIcon } from "@/components/ui/icons";

/** Shared listing shape returned by the booking.com / airbnb / tripadvisor MCP servers. */
export interface Listing {
  id: string;
  name: string;
  url?: string | null;
  photo?: string | null;
  photos?: string[];
  subtitle?: string | null;
  location?: string | null;
  rating?: number | null;
  rating_scale?: number;
  rating_label?: string | null;
  rating_icon_url?: string | null;
  review_count?: number;
  badge?: string | null;
  price_total?: number | null;
  price_per_night?: number | null;
  original_price_total?: number | null;
  currency?: string | null;
  distance_km?: number | null;
  description?: string | null;
  amenities?: string[];
  facilities?: string[];
  highlights?: string[];
  overview?: string[];
}

interface ListingsPayload {
  source: string;
  kind: "listings" | "places";
  query?: { destination?: string; area?: string; checkin?: string; checkout?: string; adults?: number; category?: string };
  price_summary?: { min_per_night: number; median_per_night: number; max_per_night: number } | null;
  results: Listing[];
}

interface DetailsPayload {
  source: string;
  kind: "listing_details";
  listing: Listing;
}

type Payload = ListingsPayload | DetailsPayload;

const SOURCE_LABELS: Record<string, string> = {
  "booking.com": "Booking.com",
  airbnb: "Airbnb",
  tripadvisor: "Tripadvisor",
};

/** Max cards per search — the row scrolls; more than this is noise in a chat. */
const MAX_CARDS = 5;

/** Pull renderable listing payloads out of raw tool result strings. */
export function parseListingResults(results?: { name: string; result: string }[]): Payload[] {
  const payloads: Payload[] = [];
  for (const r of results ?? []) {
    if (!r?.result || r.result[0] !== "{") continue;
    try {
      const data = JSON.parse(r.result);
      if (!data || data.error || !SOURCE_LABELS[data.source]) continue;
      if ((data.kind === "listings" || data.kind === "places") && data.results?.length) payloads.push(data);
      else if (data.kind === "listing_details" && data.listing?.name) payloads.push(data);
    } catch {
      // not JSON — not a listing result
    }
  }
  return payloads;
}

function money(value: number | null | undefined, currency?: string | null): string | null {
  if (value == null || !Number.isFinite(Number(value))) return null;
  try {
    return new Intl.NumberFormat("en-US", {
      style: currency ? "currency" : "decimal",
      currency: currency ?? undefined,
      maximumFractionDigits: 0,
    }).format(Number(value));
  } catch {
    return `${currency ?? ""} ${Math.round(Number(value)).toLocaleString("en-US")}`.trim();
  }
}

function shortDate(iso?: string): string | null {
  const m = iso?.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return null;
  const month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][Number(m[2]) - 1];
  return `${month} ${Number(m[3])}`;
}

function Photo({ src, alt, className = "" }: { src?: string | null; alt: string; className?: string }) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) {
    return (
      <div className={`flex items-center justify-center bg-sand text-gray-400 ${className}`}>
        <MapPinIcon className="h-6 w-6" />
      </div>
    );
  }
  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
      className={`bg-sand object-cover ${className}`}
    />
  );
}

function Rating({ listing }: { listing: Listing }) {
  const count = listing.review_count ?? 0;
  if (listing.rating_icon_url && listing.rating != null) {
    // Tripadvisor display rules: show their bubble rating image
    return (
      <span className="flex items-center gap-1.5 text-[12px] text-gray-500">
        <img src={listing.rating_icon_url} alt={`${listing.rating} of 5 bubbles`} className="h-3.5 w-auto" />
        {count > 0 && <span>{count.toLocaleString("en-US")}</span>}
      </span>
    );
  }
  if (listing.rating == null) {
    return listing.rating_label ? <span className="text-[12px] text-gray-500">{listing.rating_label}</span> : null;
  }
  if (listing.rating_scale === 10) {
    return (
      <span className="flex items-center gap-1.5 text-[12px] text-gray-500">
        <span className="rounded-[5px] bg-ink px-1.5 py-px font-mono text-[11px] font-medium text-cream">
          {listing.rating.toFixed(1)}
        </span>
        {listing.rating_label && <span className="text-ink">{listing.rating_label}</span>}
        {count > 0 && <span>· {count.toLocaleString("en-US")}</span>}
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1 text-[12px] text-gray-500">
      <StarIcon className="h-3 w-3 text-ink" />
      <span className="font-medium text-ink">{listing.rating.toFixed(2).replace(/0$/, "")}</span>
      {count > 0 && <span>({count.toLocaleString("en-US")})</span>}
    </span>
  );
}

function Price({ listing }: { listing: Listing }) {
  const nightly = money(listing.price_per_night, listing.currency);
  if (!nightly) {
    return listing.distance_km != null ? (
      <p className="text-[12px] text-gray-500">{listing.distance_km.toFixed(1)} km away</p>
    ) : null;
  }
  const total = money(listing.price_total, listing.currency);
  const original = money(listing.original_price_total, listing.currency);
  return (
    <p className="text-[12px] text-gray-500">
      <span className="text-[14px] font-semibold text-ink">{nightly}</span> night
      {total && (
        <span className="ml-1.5">
          · {original && <span className="mr-1 line-through decoration-gray-400">{original}</span>}
          {total} total
        </span>
      )}
    </p>
  );
}

function ListingCard({ listing }: { listing: Listing }) {
  const meta = [listing.location, listing.subtitle].filter(Boolean).join(" · ");
  return (
    <a
      href={listing.url ?? undefined}
      target="_blank"
      rel="noopener noreferrer"
      className="group/card flex w-[216px] shrink-0 snap-start flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white transition-[border-color,box-shadow] hover:border-gray-300 hover:shadow-[0_6px_20px_-12px_rgba(47,44,37,0.35)] sm:w-[228px]"
    >
      <div className="relative aspect-[4/3] overflow-hidden">
        <Photo
          src={listing.photo}
          alt={listing.name}
          className="h-full w-full transition-transform duration-500 group-hover/card:scale-[1.03]"
        />
        {listing.badge && (
          <span className="absolute left-2 top-2 rounded-full bg-white/95 px-2 py-0.5 text-[11px] font-medium text-ink shadow-sm">
            {listing.badge}
          </span>
        )}
        <span className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full bg-white/95 text-ink opacity-0 shadow-sm transition-opacity group-hover/card:opacity-100">
          <ExternalIcon className="h-3.5 w-3.5" />
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-1 p-3">
        <p className="line-clamp-2 text-[13.5px] font-medium leading-snug text-ink">{listing.name}</p>
        {meta && <p className="line-clamp-1 text-[12px] text-gray-500">{meta}</p>}
        <div className="mt-auto flex flex-col gap-1 pt-1">
          <Rating listing={listing} />
          <Price listing={listing} />
        </div>
      </div>
    </a>
  );
}

function ListingRow({ payload }: { payload: ListingsPayload }) {
  const scroller = useRef<HTMLDivElement>(null);
  const results = payload.results.slice(0, MAX_CARDS);
  const q = payload.query ?? {};
  const source = SOURCE_LABELS[payload.source];
  const noun =
    payload.kind === "places"
      ? `${(q.category ?? "place").toLowerCase()}s`
      : payload.source === "airbnb"
        ? "stays"
        : "hotels";
  const where = q.destination ?? q.area;
  const dates = shortDate(q.checkin) && shortDate(q.checkout) ? `${shortDate(q.checkin)} – ${shortDate(q.checkout)}` : null;
  const median = money(payload.price_summary?.median_per_night, results[0]?.currency);
  const scroll = (dir: 1 | -1) => scroller.current?.scrollBy({ left: dir * 240, behavior: "smooth" });

  return (
    <section className="group/row mb-4">
      <div className="mb-2 flex items-end justify-between gap-3">
        <p className="min-w-0 truncate text-[12.5px] text-gray-500">
          <span className="font-medium text-ink">{source}</span>
          {` · ${results.length} ${noun}`}
          {where && ` ${payload.kind === "places" ? "near" : "in"} ${where}`}
          {dates && ` · ${dates}`}
        </p>
        {median && (
          <span className="shrink-0 rounded-full bg-sand px-2.5 py-0.5 text-[11.5px] text-gray-600">
            Median <span className="font-medium text-ink">{median}</span>/night
          </span>
        )}
      </div>
      <div className="relative">
        <div
          ref={scroller}
          className="-mx-1 flex snap-x snap-mandatory gap-3 overflow-x-auto px-1 pb-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        >
          {results.map((listing) => (
            <ListingCard key={listing.id} listing={listing} />
          ))}
        </div>
        {results.length > 2 && (
          <>
            <button
              type="button"
              aria-label="Scroll left"
              onClick={() => scroll(-1)}
              className="absolute -left-3 top-[76px] hidden h-8 w-8 items-center justify-center rounded-full border border-gray-200 bg-white text-ink opacity-0 shadow-sm transition-opacity hover:border-gray-300 group-hover/row:opacity-100 sm:flex"
            >
              <ChevronIcon className="h-3.5 w-3.5 rotate-90" />
            </button>
            <button
              type="button"
              aria-label="Scroll right"
              onClick={() => scroll(1)}
              className="absolute -right-3 top-[76px] hidden h-8 w-8 items-center justify-center rounded-full border border-gray-200 bg-white text-ink opacity-0 shadow-sm transition-opacity hover:border-gray-300 group-hover/row:opacity-100 sm:flex"
            >
              <ChevronIcon className="h-3.5 w-3.5 -rotate-90" />
            </button>
          </>
        )}
      </div>
    </section>
  );
}

function DetailCard({ payload }: { payload: DetailsPayload }) {
  const listing = payload.listing;
  const photos = (listing.photos?.length ? listing.photos : [listing.photo]).filter(Boolean) as string[];
  const chips = [...(listing.overview ?? []), ...(listing.highlights ?? []), ...(listing.amenities ?? listing.facilities ?? [])];
  const uniqueChips = [...new Set(chips)].slice(0, 8);
  const meta = [listing.subtitle, listing.location].filter(Boolean).join(" · ");

  return (
    <section className="mb-4 overflow-hidden rounded-2xl border border-gray-200 bg-white">
      <div className="grid h-48 grid-cols-3 grid-rows-2 gap-0.5 sm:h-56">
        <Photo src={photos[0]} alt={listing.name} className="col-span-2 row-span-2 h-full w-full" />
        <Photo src={photos[1]} alt="" className="h-full w-full" />
        <Photo src={photos[2]} alt="" className="h-full w-full" />
      </div>
      <div className="flex flex-col gap-2 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="eyebrow !text-[10px] text-gray-400">{SOURCE_LABELS[payload.source]}</p>
            <p className="mt-0.5 text-[15px] font-medium leading-snug text-ink">{listing.name}</p>
            {meta && <p className="mt-0.5 text-[12.5px] text-gray-500">{meta}</p>}
          </div>
          {listing.url && (
            <a
              href={listing.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex shrink-0 items-center gap-1.5 rounded-full border border-gray-200 px-3 py-1 text-[12.5px] text-ink transition-colors hover:border-gray-300 hover:bg-gray-50"
            >
              Open <ExternalIcon className="h-3 w-3" />
            </a>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <Rating listing={listing} />
          {listing.badge && <span className="text-[12px] text-gray-500">{listing.badge}</span>}
          <Price listing={listing} />
        </div>
        {uniqueChips.length > 0 && (
          <ul className="mt-1 flex flex-wrap gap-1.5">
            {uniqueChips.map((chip) => (
              <li key={chip} className="rounded-full bg-sand px-2.5 py-0.5 text-[11.5px] text-gray-600">
                {chip}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

/** Photo cards for market-data tool results (Booking.com, Airbnb, Tripadvisor). */
export function ListingResults({ toolResults }: { toolResults?: { name: string; result: string }[] }) {
  const payloads = parseListingResults(toolResults);
  if (!payloads.length) return null;
  return (
    <div className="mb-1">
      {payloads.map((p, i) =>
        p.kind === "listing_details" ? <DetailCard key={i} payload={p} /> : <ListingRow key={i} payload={p} />,
      )}
    </div>
  );
}
