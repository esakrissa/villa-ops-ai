"use client";

import type { Property } from "@/lib/hooks/useProperties";

const STATUS_STYLES: Record<string, string> = {
  active: "bg-green-100 text-green-700",
  maintenance: "bg-amber-100 text-amber-700",
  inactive: "bg-gray-100 text-gray-700",
};

const TYPE_ICONS: Record<string, string> = {
  villa: "\u{1F3E1}",
  hotel: "\u{1F3E8}",
  guesthouse: "\u{1F3E0}",
};

function formatStatus(status: string): string {
  return status.replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatPrice(price: string | null): string {
  if (!price) return "No price set";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
  }).format(Number(price)) + "/night";
}

interface PropertyCardProps {
  property: Property;
  onEdit: (property: Property) => void;
  onDelete: (property: Property) => void;
}

export function PropertyCard({ property, onEdit, onDelete }: PropertyCardProps) {
  const icon = TYPE_ICONS[property.property_type] || "\u{1F3E0}";
  const statusStyle = STATUS_STYLES[property.status] || "bg-gray-100 text-gray-700";

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xl">{icon}</span>
          <h3 className="text-lg font-semibold text-gray-900">
            {property.name}
          </h3>
        </div>
        <span
          className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${statusStyle}`}
        >
          {formatStatus(property.status)}
        </span>
      </div>

      {property.location && (
        <p className="mt-1 text-sm text-gray-500">{property.location}</p>
      )}

      <div className="mt-4 space-y-2 text-sm text-gray-600">
        <div className="flex items-center gap-4">
          <span className="capitalize">{property.property_type}</span>
          {property.max_guests && (
            <>
              <span className="text-gray-300">&middot;</span>
              <span>{property.max_guests} guests</span>
            </>
          )}
        </div>
        <p className="font-medium text-gray-900">
          {formatPrice(property.base_price_per_night)}
        </p>
      </div>

      {property.amenities && property.amenities.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {property.amenities.map((amenity) => (
            <span
              key={amenity}
              className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs text-indigo-700"
            >
              {amenity}
            </span>
          ))}
        </div>
      )}

      <div className="mt-4 flex gap-2 border-t border-gray-100 pt-4">
        <button
          onClick={() => onEdit(property)}
          className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
        >
          Edit
        </button>
        <button
          onClick={() => onDelete(property)}
          className="rounded-md border border-red-200 bg-white px-3 py-1.5 text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
        >
          Delete
        </button>
      </div>
    </div>
  );
}
