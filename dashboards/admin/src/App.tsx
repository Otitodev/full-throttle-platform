import { Route, Routes } from "react-router-dom";

import { Topbar } from "./components/Topbar";
import { Vignette } from "./components/Vignette";
import { Overview } from "./pages/Overview";

export default function App() {
  return (
    <>
      <Vignette />
      <div className="relative z-10 mx-auto max-w-[1300px] px-8 py-6">
        <Topbar />
        <Routes>
          <Route path="/" element={<Overview />} />
          {/* /clients/:slug — Task 1.7 */}
        </Routes>
        <Footer />
      </div>
    </>
  );
}

function Footer() {
  return (
    <div className="mt-8 flex justify-between border-t border-mid/8 pt-4 font-mono text-[0.55rem] tracking-wider opacity-30">
      <span>Full Throttle Platform · Operator Dashboard</span>
      <span>v0.1.0</span>
    </div>
  );
}
