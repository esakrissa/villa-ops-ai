"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "100vh",
          backgroundColor: "#f9fafb",
        }}
      >
        <div
          style={{
            maxWidth: 400,
            width: "100%",
            margin: "0 1rem",
            padding: "2rem",
            backgroundColor: "#fff",
            borderRadius: 8,
            border: "1px solid #e5e7eb",
            textAlign: "center",
          }}
        >
          <div
            style={{
              width: 48,
              height: 48,
              margin: "0 auto 1rem",
              borderRadius: "50%",
              backgroundColor: "#fee2e2",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 24,
            }}
          >
            !
          </div>
          <h2
            style={{
              margin: "0 0 0.5rem",
              fontSize: 18,
              fontWeight: 600,
              color: "#111827",
            }}
          >
            Something went wrong
          </h2>
          <p
            style={{
              margin: "0 0 1.5rem",
              fontSize: 14,
              color: "#6b7280",
            }}
          >
            {error.message || "An unexpected error occurred."}
          </p>
          <button
            onClick={reset}
            style={{
              padding: "0.5rem 1.5rem",
              fontSize: 14,
              fontWeight: 500,
              color: "#fff",
              backgroundColor: "#4f46e5",
              border: "none",
              borderRadius: 6,
              cursor: "pointer",
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
