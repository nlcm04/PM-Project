"use client";

import { useEffect, useRef } from "react";
import { createChart, ColorType, type IChartApi } from "lightweight-charts";

interface NavPoint {
  snapshot_date: string;
  nav: number;
}

export function HealthChart({ snapshots }: { snapshots: NavPoint[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#FAF7F2",
      },
      grid: {
        vertLines: { color: "rgba(250, 247, 242, 0.06)" },
        horzLines: { color: "rgba(250, 247, 242, 0.06)" },
      },
      width: containerRef.current.clientWidth,
      height: 320,
      timeScale: { borderColor: "#5C3A21" },
      rightPriceScale: { borderColor: "#5C3A21" },
    });
    chartRef.current = chart;

    const navSeries = chart.addAreaSeries({
      lineColor: "#F59E0B",
      topColor: "rgba(245, 158, 11, 0.35)",
      bottomColor: "rgba(245, 158, 11, 0.02)",
      lineWidth: 2,
    });

    navSeries.setData(snapshots.map((s) => ({ time: s.snapshot_date, value: s.nav })));
    chart.timeScale().fitContent();

    const handleResize = () => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth });
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [snapshots]);

  return <div ref={containerRef} className="w-full" />;
}
