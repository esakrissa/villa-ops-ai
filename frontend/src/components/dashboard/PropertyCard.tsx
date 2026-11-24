"use client";

import type { Property } from "@/lib/hooks/useProperties";

const SCENES = ["scene-sunset", "scene-jungle", "scene-ocean", "scene-dusk", "scene-rice"];

const STATUS_DOT: Record<string, string> = {
  active: "bg-lime",
  maintenance: "bg-clay",
  inactive: "bg-gray-400",
};

/** Stable scene per property so cards keep their look between renders. */
function sceneFor(id: string): string {
  let hash = 0;
  for (const ch of id) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return SCENES[hash % SCENES.length];
}

function formatPrice(price: string | null): string | null {
  if (!price) return null;
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0 }).format(Number(price));
}

function formatAmenity(amenity: string): string {
  const text = amenity.replace(/_/g, " ");
  return text.length <= 3 ? text.toUpperCase() : text.charAt(0).toUpperCase() + text.slice(1);
}

interface PropertyCardProps {
  property: Property;
  onEdit: (property: Property) => void;
  onDelete: (property: Property) => void;
}

export function PropertyCard({ property, onEdit, onDelete }: PropertyCardProps) {
  const price = formatPrice(property.base_price_per_night);
  const dot = STATUS_DOT[property.status] || "bg-gray-400";

  return (
    <article className="group flex flex-col overflow-hidden rounded-[28px] border border-gray-200/80 bg-white transition-[box-shadow,transform] duration-200 hover:-translate-y-0.5 hover:shadow-[0_20px_40px_-24px_rgb(47_44_37/0.45)]">
      {/* Scene header */}
      <div className={`${sceneFor(property.id)} grain relative flex h-48 flex-col justify-between p-4`}>
        <div className="flex items-center justify-between">
          <span className="glass flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] font-medium capitalize text-coal">
            <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
            {property.status}
          </span>
          <span className="glass-dark rounded-full px-2.5 py-1 font-mono text-[10px] uppercase tracking-widest text-cream">
            {property.property_type}
          </span>
        </div>
        <div className="flex items-end justify-between gap-3">
          <h3 className="display text-[30px] leading-[1.02] text-cream drop-shadow-[0_1px_8px_rgb(0_0_0/0.25)]">
            {property.name}
          </h3>
          {price && (
            <span className="glass shrink-0 rounded-2xl px-3 py-1.5 text-right">
              <span className="block font-serif text-[22px] leading-none text-coal">{price}</span>
              <span className="block font-mono text-[9px] uppercase tracking-widest text-coal/60">per night</span>
            </span>
          )}
        </div>
      </div>

      {/* Details */}
      <div className="flex flex-1 flex-col p-5">
        <div className="flex items-center gap-2 text-[13px] text-gray-500">
          {property.location && <span className="truncate">{property.location}</span>}
          {property.location && property.max_guests && <span className="text-gray-300">·</span>}
          {property.max_guests && <span className="shrink-0">Sleeps {property.max_guests}</span>}
        </div>

        {property.amenities && property.amenities.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {property.amenities.slice(0, 5).map((amenity) => (
              <span key={amenity} className="rounded-full bg-sand px-2.5 py-1 text-[12px] text-gray-700">
                {formatAmenity(amenity)}
              </span>
            ))}
            {property.amenities.length > 5 && (
              <span className="rounded-full px-2 py-1 text-[12px] text-gray-400">+{property.amenities.length - 5}</span>
            )}
          </div>
        )}

        <div className="mt-auto flex gap-2 pt-5">
          <button type="button" onClick={() => onEdit(property)} className="btn-sand !px-4 !py-1.5 !text-[13px]">
            Edit
          </button>
          <button
            type="button"
            onClick={() => onDelete(property)}
            className="rounded-full px-4 py-1.5 text-[13px] font-medium text-gray-500 transition-colors hover:bg-red-50 hover:text-red-600"
          >
            Delete
          </button>
        </div>
      </div>
    </article>
  );
}
