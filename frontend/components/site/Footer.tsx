import { Logo } from "@/components/site/Logo";

export function Footer() {
  return (
    <footer className="footer sd-container">
      <Logo />
      <p>Calls made clearly, respectfully, and only when you ask.</p>
      <div>
        <span>Built by Saamarth Attray and Jaswant Pelluru</span>
        <span>© {new Date().getFullYear()} Swarm Dial</span>
      </div>
    </footer>
  );
}