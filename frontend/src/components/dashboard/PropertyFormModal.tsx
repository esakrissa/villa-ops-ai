"use client";

import { useState, useEffect } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import type { Property } from "@/lib/hooks/useProperties";

interface PropertyFormModalProps {
  property?: Property | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (isNew: boolean) => void;
}

interface FormData {
  name: string;
  property_type: string;
  location: string;
  description: string;
  max_guests: string;
  base_price_per_night: string;
  amenities: string;
  status: string;
}

const INITIAL_FORM: FormData = {
  name: "",
  property_type: "villa",
  location: "",
  description: "",
  max_guests: "",
  base_price_per_night: "",
  amenities: "",
  status: "active",
};

export function PropertyFormModal({
  property,
  isOpen,
  onClose,
  onSuccess,
}: PropertyFormModalProps) {
  const isEdit = !!property;
  const [form, setForm] = useState<FormData>(INITIAL_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [planLimitError, setPlanLimitError] = useState(false);

  useEffect(() => {
    if (isOpen && property) {
      setForm({
        name: property.name,
        property_type: property.property_type,
        location: property.location || "",
        description: property.description || "",
        max_guests: property.max_guests?.toString() || "",
        base_price_per_night: property.base_price_per_night
          ? Number(property.base_price_per_night).toString()
          : "",
        amenities: property.amenities?.join(", ") || "",
        status: property.status,
      });
    } else if (isOpen) {
      setForm(INITIAL_FORM);
    }
    setError(null);
    setPlanLimitError(false);
  }, [isOpen, property]);

  if (!isOpen) return null;

  const handleChange = (
    e: React.ChangeEvent<
      HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
    >,
  ) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setPlanLimitError(false);

    const body: Record<string, unknown> = {
      name: form.name,
      property_type: form.property_type,
      status: form.status,
    };

    if (form.location) body.location = form.location;
    if (form.description) body.description = form.description;
    if (form.max_guests) body.max_guests = parseInt(form.max_guests, 10);
    if (form.base_price_per_night)
      body.base_price_per_night = parseFloat(form.base_price_per_night);
    if (form.amenities) {
      body.amenities = form.amenities
        .split(",")
        .map((a) => a.trim())
        .filter(Boolean);
    }

    try {
      if (isEdit) {
        await apiFetch(`/api/v1/properties/${property!.id}`, {
          method: "PUT",
          body: JSON.stringify(body),
        });
      } else {
        await apiFetch("/api/v1/properties", {
          method: "POST",
          body: JSON.stringify(body),
        });
      }
      onSuccess(!isEdit);
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.status === 402) {
        setPlanLimitError(true);
      } else {
        setError(
          err instanceof Error ? err.message : "Failed to save property",
        );
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="mx-4 w-full max-w-lg rounded-lg bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900">
            {isEdit ? "Edit Property" : "Add Property"}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 transition-colors hover:text-gray-600"
          >
            <svg
              className="h-5 w-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-4">
          {planLimitError && (
            <div className="mb-4 rounded-md bg-amber-50 border border-amber-200 p-4">
              <p className="text-sm font-medium text-amber-800">
                Plan limit reached
              </p>
              <p className="mt-1 text-sm text-amber-700">
                You&apos;ve reached your plan&apos;s property limit. Upgrade to
                add more properties.
              </p>
              <a
                href="/pricing"
                className="mt-2 inline-block text-sm font-medium text-indigo-600 hover:text-indigo-500"
              >
                View upgrade options &rarr;
              </a>
            </div>
          )}

          {error && (
            <div className="mb-4 rounded-md bg-red-50 border border-red-200 p-3">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label
                htmlFor="name"
                className="block text-sm font-medium text-gray-700"
              >
                Name <span className="text-red-500">*</span>
              </label>
              <input
                id="name"
                name="name"
                type="text"
                required
                maxLength={255}
                value={form.name}
                onChange={handleChange}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 focus:outline-none"
                placeholder="e.g. Villa Sunset"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label
                  htmlFor="property_type"
                  className="block text-sm font-medium text-gray-700"
                >
                  Type <span className="text-red-500">*</span>
                </label>
                <select
                  id="property_type"
                  name="property_type"
                  value={form.property_type}
                  onChange={handleChange}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 focus:outline-none"
                >
                  <option value="villa">Villa</option>
                  <option value="hotel">Hotel</option>
                  <option value="guesthouse">Guesthouse</option>
                </select>
              </div>
              <div>
                <label
                  htmlFor="status"
                  className="block text-sm font-medium text-gray-700"
                >
                  Status
                </label>
                <select
                  id="status"
                  name="status"
                  value={form.status}
                  onChange={handleChange}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 focus:outline-none"
                >
                  <option value="active">Active</option>
                  <option value="maintenance">Maintenance</option>
                  <option value="inactive">Inactive</option>
                </select>
              </div>
            </div>

            <div>
              <label
                htmlFor="location"
                className="block text-sm font-medium text-gray-700"
              >
                Location
              </label>
              <input
                id="location"
                name="location"
                type="text"
                maxLength={255}
                value={form.location}
                onChange={handleChange}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 focus:outline-none"
                placeholder="e.g. Seminyak, Bali"
              />
            </div>

            <div>
              <label
                htmlFor="description"
                className="block text-sm font-medium text-gray-700"
              >
                Description
              </label>
              <textarea
                id="description"
                name="description"
                rows={3}
                value={form.description}
                onChange={handleChange}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 focus:outline-none"
                placeholder="Describe the property..."
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label
                  htmlFor="max_guests"
                  className="block text-sm font-medium text-gray-700"
                >
                  Max Guests
                </label>
                <input
                  id="max_guests"
                  name="max_guests"
                  type="number"
                  min={1}
                  value={form.max_guests}
                  onChange={handleChange}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 focus:outline-none"
                  placeholder="e.g. 8"
                />
              </div>
              <div>
                <label
                  htmlFor="base_price_per_night"
                  className="block text-sm font-medium text-gray-700"
                >
                  Price / Night ($)
                </label>
                <input
                  id="base_price_per_night"
                  name="base_price_per_night"
                  type="number"
                  min={0}
                  step="0.01"
                  value={form.base_price_per_night}
                  onChange={handleChange}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 focus:outline-none"
                  placeholder="e.g. 150"
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="amenities"
                className="block text-sm font-medium text-gray-700"
              >
                Amenities
              </label>
              <input
                id="amenities"
                name="amenities"
                type="text"
                value={form.amenities}
                onChange={handleChange}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 focus:outline-none"
                placeholder="Pool, WiFi, AC (comma-separated)"
              />
              <p className="mt-1 text-xs text-gray-500">
                Separate amenities with commas
              </p>
            </div>
          </div>

          <div className="mt-6 flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving || planLimitError}
              className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving
                ? "Saving..."
                : isEdit
                  ? "Update Property"
                  : "Add Property"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
