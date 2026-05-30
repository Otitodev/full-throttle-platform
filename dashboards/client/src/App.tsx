import { useEffect, useState } from "react";

import { NotAuthenticated } from "./components/NotAuthenticated";
import { Topbar } from "./components/Topbar";
import { Vignette } from "./components/Vignette";
import { bootAuth, getSlug, getToken } from "./lib/auth";
import { Dashboard } from "./pages/Dashboard";

export default function App() {
  // Promote any URL-fragment token to sessionStorage on first paint.
  const [authed, setAuthed] = useState<boolean>(false);
  const [slug, setSlug] = useState<string>("");

  useEffect(() => {
    bootAuth();
    setSlug(getSlug());
    setAuthed(getToken() !== null);
  }, []);

  return (
    <>
      <Vignette />
      <div className="relative z-10 mx-auto max-w-[1200px] px-4 py-6 sm:px-8">
        <Topbar slug={slug} />
        {authed ? <Dashboard /> : <NotAuthenticated />}
        <Footer />
      </div>
    </>
  );
}

function Footer() {
  return (
    <div className="mt-8 flex flex-wrap justify-between gap-2 border-t border-mid/8 pt-4 font-mono text-[0.55rem] tracking-wider opacity-30">
      <span>Full Throttle Platform · Client Dashboard</span>
      <span>v0.1.0</span>
    </div>
  );
}
