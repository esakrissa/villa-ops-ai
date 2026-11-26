// In production Docker build, NEXT_PUBLIC_API_URL="" (empty string = relative paths via nginx).
// In local dev, NEXT_PUBLIC_API_URL is undefined → falls back to localhost:8000.
// Uses ?? (not ||) so empty string is preserved as a valid value.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    public data: Record<string, unknown>,
  ) {
    super(
      typeof data?.detail === "string" ? data.detail : `API error: ${status}`,
    );
  }
}

// One token refresh shared by every request that got a 401 at the same time. With a boolean flag
// only the first request waited for the refresh; the others failed (e.g. the voice config, which
// hid the Villa button until a reload after the access token expired).
let refreshing: Promise<void> | null = null;

function refreshOnce(): Promise<void> {
  if (!refreshing) {
    refreshing = (async () => {
      // Lazy import to avoid circular dependency (auth.ts imports api.ts)
      const { refreshTokens } = await import("./auth");
      await refreshTokens();
    })().finally(() => {
      refreshing = null;
    });
  }
  return refreshing;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  retried = false,
): Promise<T> {
  const token =
    typeof window !== "undefined"
      ? localStorage.getItem("access_token")
      : null;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    if (
      res.status === 401 &&
      !retried &&
      path !== "/api/v1/auth/login" &&
      path !== "/api/v1/auth/refresh"
    ) {
      try {
        await refreshOnce();
      } catch {
        const { clearTokens } = await import("./auth");
        clearTokens();
        if (typeof window !== "undefined") {
          window.location.href = "/login";
        }
        throw new ApiError(401, { detail: "Session expired" });
      }
      return apiFetch<T>(path, options, true);
    }

    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data);
  }

  // 204 No Content has no body to parse
  if (res.status === 204) {
    return undefined as T;
  }

  return res.json();
}

export { API_BASE_URL };
