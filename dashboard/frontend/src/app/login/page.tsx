"use client";
import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { BarChart2 } from "lucide-react";
import Link from "next/link";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch {
      setError("AUTH_FAILED — Invalid credentials.");
    } finally { setLoading(false); }
  }

  return (
    <div className="login-shell">
      <div className="login-panel animate-in">

        {/* Logo mark */}
        <div className="login-logo-mark">
          <BarChart2 size={20} color="#000" strokeWidth={2.5} />
        </div>

        {/* Header */}
        <div className="login-headline">Competitive Intelligence Platform</div>
        <div className="login-title">
          Command Center<span className="cursor-blink" />
        </div>

        {/* Error */}
        {error && <div className="login-error">{error}</div>}

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <label className="form-label" htmlFor="login-email">Email address</label>
            <input
              id="login-email"
              className="input"
              type="email"
              autoComplete="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="operator@marketintel.com"
              required
            />
          </div>

          <div>
            <label className="form-label" htmlFor="login-password">Password</label>
            <input
              id="login-password"
              className="input"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••••"
              required
            />
            {/* Forgot password link */}
            <div style={{ marginTop: 6, textAlign: "right" }}>
              <Link
                href="/forgot-password"
                style={{
                  fontFamily: "var(--font-mono)", fontSize: 10,
                  color: "var(--text-muted)", textDecoration: "none",
                  letterSpacing: "0.06em", textTransform: "uppercase",
                  transition: "color 0.15s",
                }}
                onMouseEnter={e => (e.currentTarget.style.color = "var(--accent)")}
                onMouseLeave={e => (e.currentTarget.style.color = "var(--text-muted)")}
              >
                Forgot password?
              </Link>
            </div>
          </div>

          <button
            id="login-submit"
            className="btn btn-primary"
            type="submit"
            disabled={loading}
            style={{ width: "100%", justifyContent: "center", padding: "10px 0", marginTop: 8, fontSize: 13, letterSpacing: "0.06em" }}
          >
            {loading ? (
              <span style={{ fontFamily: "var(--font-mono)", letterSpacing: "0.08em" }}>AUTHENTICATING…</span>
            ) : (
              <span style={{ fontFamily: "var(--font-mono)", letterSpacing: "0.08em" }}>ACCESS SYSTEM</span>
            )}
          </button>
        </form>

        {/* Divider */}
        <div style={{
          display: "flex", alignItems: "center", gap: 12, margin: "20px 0 0",
        }}>
          <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)", letterSpacing: "0.08em" }}>
            OR
          </span>
          <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
        </div>

        {/* Create account link */}
        <Link
          href="/register"
          style={{ textDecoration: "none" }}
        >
          <button
            id="login-register-link"
            className="btn btn-ghost"
            type="button"
            style={{ width: "100%", justifyContent: "center", padding: "10px 0", marginTop: 12, fontSize: 13 }}
          >
            <span style={{ fontFamily: "var(--font-mono)", letterSpacing: "0.08em" }}>CREATE ACCOUNT</span>
          </button>
        </Link>

        <div className="login-footnote">PFE2 · Intelligence Platform · v2.0</div>
      </div>
    </div>
  );
}
