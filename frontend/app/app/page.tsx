import { AppHeading } from "@/components/site/AppHeading";
import { RequireAuth } from "@/components/site/RequireAuth";
import { SiteNav } from "@/components/site/SiteNav";
import { QueryForm } from "@/components/QueryForm";
import { RecentSwarms } from "@/components/RecentSwarms";

export const metadata = { title: "New search · Swarm Dial" };

export default function AppHome() {
  return (
    <>
      <SiteNav current="app" />
      <RequireAuth>
        <main className="mx-auto max-w-2xl px-4 pb-16 pt-8 sm:px-6 sm:pt-14">
          <AppHeading />
          <p className="mt-4 max-w-[52ch] text-lg leading-relaxed text-ink-soft">
            Describe it and AI callers will phone local businesses at the same time, ask what is in stock right now, and tell you who actually has it.
          </p>
          <div className="mt-8">
            <QueryForm />
          </div>
          <RecentSwarms />
        </main>
      </RequireAuth>
    </>
  );
}