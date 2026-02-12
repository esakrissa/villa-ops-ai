import Link from "next/link";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-4">
        <span className="text-xl font-bold text-indigo-600">VillaOps AI</span>
        <div className="flex items-center gap-3">
          <Link
            href="/pricing"
            className="rounded-lg px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
          >
            Pricing
          </Link>
          <Link
            href="/login"
            className="rounded-lg px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
          >
            Sign in
          </Link>
          <Link
            href="/register"
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-500"
          >
            Get started
          </Link>
        </div>
      </header>

      {/* Hero */}
      <main className="flex flex-1 flex-col items-center justify-center px-6 text-center">
        <h1 className="max-w-2xl text-5xl font-bold tracking-tight text-gray-900">
          AI-powered operations for{" "}
          <span className="text-indigo-600">villa managers</span>
        </h1>
        <p className="mt-4 max-w-lg text-lg text-gray-500">
          Manage bookings, guests, and properties with an intelligent assistant
          that understands your business. Built for Bali property managers.
        </p>
        <div className="mt-8 flex gap-4">
          <Link
            href="/register"
            className="rounded-lg bg-indigo-600 px-6 py-3 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500"
          >
            Start for free
          </Link>
          <Link
            href="/pricing"
            className="rounded-lg border border-gray-300 px-6 py-3 text-sm font-semibold text-gray-700 shadow-sm hover:bg-gray-50"
          >
            View pricing
          </Link>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 py-6 text-center text-sm text-gray-400">
        VillaOps AI &mdash; Built with Next.js, FastAPI, and LangGraph
      </footer>
    </div>
  );
}
