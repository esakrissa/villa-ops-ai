import { RegisterForm } from "@/components/auth/RegisterForm";
import { OAuthButtons } from "@/components/auth/OAuthButtons";
import Link from "next/link";

export default function RegisterPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="display text-[52px] text-ink">Start in <em>minutes</em>.</h1>
        <p className="mt-3 text-[15px] text-gray-500">Create your VillaOps workspace. Free forever for one villa.</p>
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

      <RegisterForm />

      <p className="mt-6 text-center text-sm text-gray-500">
        Already have an account?{" "}
        <Link
          href="/login"
          className="font-medium text-ink underline underline-offset-2"
        >
          Sign in
        </Link>
      </p>
    </div>
  );
}
