export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-brown-700/60 bg-brown-900/60 p-5 shadow-sm ${className}`}>
      {children}
    </div>
  );
}
