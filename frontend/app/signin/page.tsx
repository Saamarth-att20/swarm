import { AuthForm } from "@/components/auth/AuthForm";
import { AuthShell } from "@/components/auth/AuthShell";

export const metadata = { title: "Sign in · Swarm Dial" };

export default function SignInPage() {
  return (
    <AuthShell title="Welcome back" subtitle="Sign in to start a new search.">
      <AuthForm mode="signin" />
    </AuthShell>
  );
}