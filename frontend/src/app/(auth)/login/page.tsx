import { LoginForm } from "@/components/auth/LoginForm";
import { OAuthButtons } from "@/components/auth/OAuthButtons";
import Link from "next/link";

export default function LoginPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="display text-[52px] text-ink">Welcome <em>back</em>.</h1>
        <p className="mt-3 text-[15px] text-gray-500">Sign in to your VillaOps workspace.</p>
      </div>

      <OAuthButtons />

      <div className="relative my-6">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-gray-200" />
        </div>
        <div className="relative flex justify-center text-sm">
          <span className="eyebrow bg-cream px-3 text-gray-400">or</span>
        </div>
      </div>

      <LoginForm />

      <p className="mt-6 text-center text-sm text-gray-500">
        Don&apos;t have an account?{" "}
        <Link
          href="/register"
          className="font-medium text-ink underline underline-offset-2"
        >
          Sign up
        </Link>
      </p>
    </div>
  );
}
