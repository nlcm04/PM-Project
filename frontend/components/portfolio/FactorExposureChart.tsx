"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function FactorExposureChart({ exposures }: { exposures: Record<string, number> }) {
  const data = Object.entries(exposures).map(([factor, value]) => ({ factor, value }));

  if (data.length === 0) {
    return <p className="text-sm text-cream/50">No factor exposure snapshot available yet.</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(250, 247, 242, 0.08)" />
        <XAxis dataKey="factor" tick={{ fill: "#FAF7F2", fontSize: 12 }} />
        <YAxis tick={{ fill: "#FAF7F2", fontSize: 12 }} />
        <Tooltip
          contentStyle={{ background: "#3D2314", border: "1px solid #5C3A21", borderRadius: 8, color: "#FAF7F2" }}
        />
        <Bar dataKey="value" fill="#D97706" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
