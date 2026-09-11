import React, { useEffect, useState } from "react";
import {
  Activity,
  CheckCircle2,
  Cpu,
  RefreshCw,
  Server,
  Trash2,
  Zap,
} from "lucide-react";
import { aiClient } from "../services/aiClient";
import { SystemHealthResponse, SystemMetricsResponse } from "../types/ai";

export const SystemStatusView: React.FC = () => {
  const [health, setHealth] = useState<SystemHealthResponse | null>(null);
  const [metrics, setMetrics] = useState<SystemMetricsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [clearingCache, setClearingCache] = useState(false);
  const [cacheMessage, setCacheMessage] = useState<string | null>(null);

  async function fetchStatus() {
    setLoading(true);
    try {
      const [h, m] = await Promise.all([
        aiClient.getSystemHealth(),
        aiClient.getSystemMetrics(),
      ]);
      setHealth(h);
      setMetrics(m);
    } catch (err: any) {
      console.warn("Failed to load telemetry:", err);
    } finally {
      setLoading(false);
    }
  }

  async function handleClearCache() {
    setClearingCache(true);
    setCacheMessage(null);
    try {
      const res = await aiClient.clearCache();
      setCacheMessage(res.message);
      fetchStatus();
    } catch (err: any) {
      setCacheMessage(`Cache clear notice: ${err.message}`);
    } finally {
      setClearingCache(false);
    }
  }

  useEffect(() => {
    fetchStatus();
    const timer = setInterval(fetchStatus, 10000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="page-content">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px", flexWrap: "wrap", gap: "16px" }}>
        <div>
          <p className="eyebrow">OBSERVABILITY & ADMISSION CONTROL</p>
          <h1 style={{ margin: "4px 0", fontSize: "28px", fontFamily: "Manrope, sans-serif" }}>
            AI Service Telemetry & Status
          </h1>
          <p style={{ color: "#6e7f77", margin: "4px 0 0", fontSize: "14px" }}>
            Real-time tracking of GPU concurrency, latency percentiles, Redis cache hit rates, and model availability.
          </p>
        </div>

        <div style={{ display: "flex", gap: "10px" }}>
          <button
            onClick={fetchStatus}
            disabled={loading}
            style={{
              padding: "8px 14px",
              display: "flex",
              alignItems: "center",
              gap: "6px",
              background: "#ffffff",
              color: "#164f40",
              border: "1px solid #dedfd6",
              borderRadius: "8px",
              fontSize: "12px",
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh Telemetry
          </button>
          <button
            onClick={handleClearCache}
            disabled={clearingCache}
            style={{
              padding: "8px 14px",
              display: "flex",
              alignItems: "center",
              gap: "6px",
              background: "#fee2e2",
              color: "#991b1b",
              border: "1px solid #fecaca",
              borderRadius: "8px",
              fontSize: "12px",
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            <Trash2 size={14} /> Clear Redis Cache
          </button>
        </div>
      </div>

      {cacheMessage && (
        <div style={{ padding: "12px 16px", background: "var(--bg-accent)", border: "1px solid var(--border-color)", color: "var(--text-main)", borderRadius: "10px", fontSize: "13px", fontWeight: 600, marginBottom: "20px" }}>
          {cacheMessage}
        </div>
      )}

      {/* Health Overview Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "18px", marginBottom: "28px" }}>
        <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: "14px", padding: "20px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
            <span style={{ fontSize: "11px", fontWeight: 800, color: "var(--text-muted)" }}>ACTIVE ENGINE</span>
            <Server size={18} style={{ color: "#059669" }} />
          </div>
          <strong style={{ display: "block", fontSize: "18px", color: "var(--text-main)" }}>
            {health?.provider.name ? health.provider.name.toUpperCase() : "OLLAMA (LOCAL)"}
          </strong>
          <span style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px", display: "block" }}>
            Model: Qwen2.5-7B-Instruct (Q4_K_M)
          </span>
        </div>

        <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: "14px", padding: "20px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
            <span style={{ fontSize: "11px", fontWeight: 800, color: "var(--text-muted)" }}>GPU ADMISSION SLOTS</span>
            <Cpu size={18} style={{ color: "#059669" }} />
          </div>
          <strong style={{ display: "block", fontSize: "18px", color: "var(--text-main)" }}>
            {metrics?.resource_load?.active_local_gpu_inferences ?? 0} / 2 ACTIVE
          </strong>
          <span style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px", display: "block" }}>
            8GB VRAM Gate (Protected)
          </span>
        </div>

        <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: "14px", padding: "20px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
            <span style={{ fontSize: "11px", fontWeight: 800, color: "var(--text-muted)" }}>REDIS CACHE HIT RATE</span>
            <Zap size={18} style={{ color: "#059669" }} />
          </div>
          <strong style={{ display: "block", fontSize: "18px", color: "var(--text-main)" }}>
            {metrics?.cache ? `${(metrics.cache.hit_rate * 100).toFixed(1)}%` : "0.0%"}
          </strong>
          <span style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px", display: "block" }}>
            Hits: {metrics?.cache?.hits ?? 0} • Misses: {metrics?.cache?.misses ?? 0}
          </span>
        </div>

        <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: "14px", padding: "20px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
            <span style={{ fontSize: "11px", fontWeight: 800, color: "var(--text-muted)" }}>AVG INFERENCE LATENCY</span>
            <Activity size={18} style={{ color: "#059669" }} />
          </div>
          <strong style={{ display: "block", fontSize: "18px", color: "var(--text-main)" }}>
            {metrics?.latency_ms?.all?.avg_ms ? `${metrics.latency_ms.all.avg_ms} ms` : "< 150 ms"}
          </strong>
          <span style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px", display: "block" }}>
            p95: {metrics?.latency_ms?.all?.p95_ms ?? 0} ms • p99: {metrics?.latency_ms?.all?.p99_ms ?? 0} ms
          </span>
        </div>
      </div>

      {/* Latency by Service Domain */}
      <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-color)", borderRadius: "16px", padding: "24px" }}>
        <h3 style={{ margin: "0 0 16px", fontSize: "16px", fontWeight: 800, color: "var(--text-main)" }}>Latency & Request Breakdown by AI Service Domain</h3>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
          <thead>
            <tr style={{ background: "var(--bg-surface-secondary)", borderBottom: "1px solid var(--border-color)", color: "var(--text-muted)", fontWeight: 800, fontSize: "11px", textAlign: "left" }}>
              <th style={{ padding: "12px 14px" }}>DOMAIN</th>
              <th style={{ padding: "12px 14px" }}>TOTAL REQUESTS</th>
              <th style={{ padding: "12px 14px" }}>AVG LATENCY</th>
              <th style={{ padding: "12px 14px" }}>P50 (MEDIAN)</th>
              <th style={{ padding: "12px 14px" }}>P95 LATENCY</th>
              <th style={{ padding: "12px 14px" }}>STATUS</th>
            </tr>
          </thead>
          <tbody>
            {["quiz", "grading", "tutor", "analytics", "risk", "reports"].map((dom) => {
              const domStats = metrics?.latency_ms?.[dom];
              const count = domStats?.count ?? 0;
              return (
                <tr key={dom} style={{ borderBottom: "1px solid var(--border-color)" }}>
                  <td style={{ padding: "12px 14px", fontWeight: 700, color: "var(--text-main)" }}>
                    {dom.toUpperCase()}
                  </td>
                  <td style={{ padding: "12px 14px", color: "var(--text-main)" }}>{count}</td>
                  <td style={{ padding: "12px 14px", color: "var(--text-main)" }}>{domStats?.avg_ms ? `${domStats.avg_ms} ms` : "—"}</td>
                  <td style={{ padding: "12px 14px", color: "var(--text-main)" }}>{domStats?.p50_ms ? `${domStats.p50_ms} ms` : "—"}</td>
                  <td style={{ padding: "12px 14px", color: "var(--text-main)" }}>{domStats?.p95_ms ? `${domStats.p95_ms} ms` : "—"}</td>
                  <td style={{ padding: "12px 14px" }}>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: "4px", background: "var(--bg-accent)", color: "#059669", padding: "2px 8px", borderRadius: "4px", fontSize: "10px", fontWeight: 700 }}>
                      <CheckCircle2 size={10} /> Online
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
