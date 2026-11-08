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
        <main className="app-shell route-view">
          <AppHeading />
          <QueryForm />
          <RecentSwarms />
        </main>
      </RequireAuth>
    </>
  );
}