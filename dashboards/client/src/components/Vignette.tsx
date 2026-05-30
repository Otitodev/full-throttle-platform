export function Vignette() {
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 z-0 opacity-20 mix-blend-lighten"
      style={{
        background:
          "radial-gradient(ellipse at 0% 0%, rgba(255,189,56,0.30) 0%, transparent 55%), radial-gradient(ellipse at 100% 100%, rgba(255,189,56,0.12) 0%, transparent 45%)",
      }}
    />
  );
}
