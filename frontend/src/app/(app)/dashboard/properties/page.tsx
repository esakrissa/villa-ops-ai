"use client";

import { useState } from "react";
import { useProperties } from "@/lib/hooks/useProperties";
import { useSubscription } from "@/lib/hooks/useSubscription";
import { PropertyCard } from "@/components/dashboard/PropertyCard";
import { PropertyFormModal } from "@/components/dashboard/PropertyFormModal";
import { apiFetch } from "@/lib/api";
import { toast } from "sonner";
import type { Property } from "@/lib/hooks/useProperties";

export default function PropertiesPage() {
  const { properties, loading, error, refetch } = useProperties();
  const { subscription, refetch: refetchSubscription } = useSubscription();
  const [formOpen, setFormOpen] = useState(false);
  const [editProperty, setEditProperty] = useState<Property | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<Property | null>(null);
  const [deleting, setDeleting] = useState(false);

  const propertiesLimit = subscription?.usage.properties_limit ?? null;
  const propertiesUsed = subscription?.usage.properties_used ?? 0;
  const atLimit = propertiesLimit !== null && propertiesUsed >= propertiesLimit;

  const handleAdd = () => {
    setEditProperty(null);
    setFormOpen(true);
  };

  const handleEdit = (property: Property) => {
    setEditProperty(property);
    setFormOpen(true);
  };

  const handleFormSuccess = (isNew: boolean) => {
    toast.success(isNew ? "Property created" : "Property updated");
    refetch();
    refetchSubscription();
  };

  const handleDelete = async () => {
    if (!deleteConfirm) return;
    setDeleting(true);
    try {
      await apiFetch(`/api/v1/properties/${deleteConfirm.id}`, {
        method: "DELETE",
      });
      setDeleteConfirm(null);
      toast.success("Property deleted");
      refetch();
      refetchSubscription();
    } catch {
      toast.error("Failed to delete property");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Properties</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage your vacation properties.
          </p>
        </div>
        <button
          onClick={handleAdd}
          disabled={atLimit}
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          + Add Property
        </button>
      </div>

      {/* Plan limit warning */}
      {atLimit && (
        <div className="mb-6 rounded-md border border-amber-200 bg-amber-50 p-4">
          <div className="flex">
            <svg
              className="h-5 w-5 flex-shrink-0 text-amber-400"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 6a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 6zm0 9a1 1 0 100-2 1 1 0 000 2z"
                clipRule="evenodd"
              />
            </svg>
            <div className="ml-3">
              <p className="text-sm font-medium text-amber-800">
                You&apos;ve reached your limit of {propertiesLimit}{" "}
                {propertiesLimit === 1 ? "property" : "properties"}.
              </p>
              <p className="mt-1 text-sm text-amber-700">
                Upgrade your plan to add more properties.{" "}
                <a
                  href="/pricing"
                  className="font-medium text-indigo-600 hover:text-indigo-500"
                >
                  View plans &rarr;
                </a>
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="mb-6 rounded-md border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-700">{error}</p>
          <button
            onClick={() => refetch()}
            className="mt-2 text-sm font-medium text-red-600 hover:text-red-500"
          >
            Try again
          </button>
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="animate-pulse rounded-lg border border-gray-200 bg-white p-6"
            >
              <div className="flex justify-between">
                <div className="h-5 w-32 rounded bg-gray-200" />
                <div className="h-5 w-16 rounded-full bg-gray-200" />
              </div>
              <div className="mt-2 h-4 w-24 rounded bg-gray-200" />
              <div className="mt-4 space-y-2">
                <div className="h-4 w-40 rounded bg-gray-200" />
                <div className="h-4 w-20 rounded bg-gray-200" />
              </div>
              <div className="mt-4 flex gap-2 border-t border-gray-100 pt-4">
                <div className="h-8 w-16 rounded bg-gray-200" />
                <div className="h-8 w-16 rounded bg-gray-200" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && properties.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-gray-300 bg-white py-16">
          <svg
            className="mb-4 h-12 w-12 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"
            />
          </svg>
          <p className="text-sm font-medium text-gray-900">
            No properties yet
          </p>
          <p className="mt-1 text-sm text-gray-500">
            Add your first property to get started.
          </p>
          <button
            onClick={handleAdd}
            disabled={atLimit}
            className="mt-4 rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            + Add Property
          </button>
        </div>
      )}

      {/* Property grid */}
      {!loading && properties.length > 0 && (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          {properties.map((property) => (
            <PropertyCard
              key={property.id}
              property={property}
              onEdit={handleEdit}
              onDelete={setDeleteConfirm}
            />
          ))}
        </div>
      )}

      {/* Add/Edit Modal */}
      <PropertyFormModal
        property={editProperty}
        isOpen={formOpen}
        onClose={() => setFormOpen(false)}
        onSuccess={handleFormSuccess}
      />

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="mx-4 w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <h3 className="text-lg font-semibold text-gray-900">
              Delete Property
            </h3>
            <p className="mt-2 text-sm text-gray-600">
              Are you sure you want to delete{" "}
              <span className="font-medium">{deleteConfirm.name}</span>? This
              will permanently delete the property and all its bookings.
            </p>
            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-50"
              >
                {deleting ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
