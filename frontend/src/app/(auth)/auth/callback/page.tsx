"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useEffect, Suspense } from "react";
import { saveTokens } from "@/lib/auth";
import { useAuth } from "@/lib/hooks/useAuth";

function CallbackHandler() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { refreshUser } = useAuth();

  useEffect(() => {
    const accessToken = searchParams.get("access_token");
    const refreshToken = searchParams.get("refresh_token");

    if (accessToken && refreshToken) {
      saveTokens(accessToken, refreshToken);
      refreshUser().then(() => router.replace("/chat"));
    } else {
      router.replace("/login?error=oauth_failed");
    }
  }, [searchParams, router, refreshUser]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="text-center">
        <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
        <p className="text-gray-600">Completing sign in...</p>
      </div>
    </div>
  );
}

export default function CallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <p className="text-gray-600">Loading...</p>
        </div>
      }
    >
      <CallbackHandler />
    </Suspense>
  );
}
