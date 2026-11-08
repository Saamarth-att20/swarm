import { AuthForm } from "@/components/auth/AuthForm";
import { AuthShell } from "@/components/auth/AuthShell";

export const metadata = { title: "Create your account · Swarm Dial" };

export default function SignUpPage() {
  return (
    <AuthShell title="Create your account" subtitle="Save your searches and pick up where you left off.">
      <AuthForm mode="signup" />
    </AuthShell>
  );
}