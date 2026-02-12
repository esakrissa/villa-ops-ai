const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

let isRefreshing = false;

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
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
      !isRefreshing &&
      path !== "/api/v1/auth/refresh"
    ) {
      isRefreshing = true;
      try {
        // Lazy import to avoid circular dependency (auth.ts imports api.ts)
        const { refreshTokens } = await import("./auth");
        await refreshTokens();
        isRefreshing = false;
        return apiFetch<T>(path, options);
      } catch {
        isRefreshing = false;
        const { clearTokens } = await import("./auth");
        clearTokens();
        if (typeof window !== "undefined") {
          window.location.href = "/login";
        }
        throw new ApiError(401, { detail: "Session expired" });
      }
    }

    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data);
  }

  return res.json();
}

export { API_BASE_URL };
