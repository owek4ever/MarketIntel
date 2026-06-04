"use client";
import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api";
import { BarChart2, ArrowLeft, CheckCircle } from "lucide-react";
import Link from "next/link";

type Step = "form" | "success";

export default function RegisterPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("form");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("MISMATCH — Passwords do not match.");
      return;
    }
    if (password.length < 8) {
      setError("WEAK PASSWORD — Minimum 8 characters required.");
      return;
    }

    setLoading(true);
    try {
      await authApi.register(email, password);
      setStep("success");
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 409) {
        setError("CONFLICT — An account with this email already exists.");
      } else {
        setError("REGISTRATION FAILED — Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  // ── Success screen ─────────────────────────────────────────────────────────
  if (step === "success") {
    return (
      <div className="login-shell">
        <div className="login-panel animate-in" style={{ textAlign: "center" }}>
          <div style={{
            display: "inline-flex", alignItems: "center", justifyContent: "center",
            width: 56, height: 56, background: "rgba(34,197,94,.12)",
            border: "1px solid rgba(34,197,94,.25)", marginBottom: 24,
          }}>
            <CheckCircle size={24} color="#4ade80" />
          </div>

          <div className="login-headline">Account Created</div>
          <div className="login-title" style={{ marginBottom: 16 }}>
            Welcome aboard<span className="cursor-blink" />
          </div>

          <p style={{
            fontFamily: "var(--font-mono)", fontSize: 12,
            color: "var(--text-secondary)", lineHeight: 1.7, marginBottom: 32,
          }}>
            Your analyst account for{" "}
            <span style={{ color: "var(--accent)" }}>{email}</span>{" "}
            has been created.<br />
            A welcome email has been sent to your inbox.
          </p>

          <button
            className="btn btn-primary"
            style={{ width: "100%", justifyContent: "center", padding: "10px 0", fontSize: 13, letterSpacing: "0.06em" }}
            onClick={() => router.push("/login")}
          >
            <span style={{ fontFamily: "var(--font-mono)", letterSpacing: "0.08em" }}>
              PROCEED TO LOGIN
            </span>
          </button>

          <div className="login-footnote">PFE2 · Intelligence Platform · v2.0</div>
        </div>
      </div>
    );
  }

  // ── Registration form ──────────────────────────────────────────────────────
  return (
    <div className="login-shell">
      <div className="login-panel animate-in">

        {/* Logo */}
        <div className="login-logo-mark">
          <BarChart2 size={20} color="#000" strokeWidth={2.5} />
        </div>

        {/* Header */}
        <div className="login-headline">Competitive Intelligence Platform</div>
        <div className="login-title">
          Create Account<span className="cursor-blink" />
        </div>

        {/* Error */}
        {error && <div className="login-error">{error}</div>}

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <label className="form-label" htmlFor="reg-email">Email address</label>
            <input
              id="reg-email"
              className="input"
              type="email"
              autoComplete="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="operator@pfe2.local"
              required
            />
          </div>

          <div>
            <label className="form-label" htmlFor="reg-password">Password</label>
            <input
              id="reg-password"
              className="input"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="Min. 8 characters"
              required
            />
          </div>

          <div>
            <label className="form-label" htmlFor="reg-confirm">Confirm password</label>
            <input
              id="reg-confirm"
              className="input"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              placeholder="Repeat your password"
              required
            />
            {/* Password match indicator */}
            {confirmPassword.length > 0 && (
              <div style={{
                fontFamily: "var(--font-mono)", fontSize: 10,
                color: password === confirmPassword ? "#4ade80" : "#f87171",
                marginTop: 4, letterSpacing: "0.06em", textTransform: "uppercase",
              }}>
                {password === confirmPassword ? "✓ Passwords match" : "✗ Passwords do not match"}
              </div>
            )}
          </div>

          <button
            id="reg-submit"
            className="btn btn-primary"
            type="submit"
            disabled={loading}
            style={{ width: "100%", justifyContent: "center", padding: "10px 0", marginTop: 8, fontSize: 13, letterSpacing: "0.06em" }}
          >
            {loading ? (
              <span style={{ fontFamily: "var(--font-mono)", letterSpacing: "0.08em" }}>CREATING ACCOUNT…</span>
            ) : (
              <span style={{ fontFamily: "var(--font-mono)", letterSpacing: "0.08em" }}>CREATE ACCOUNT</span>
            )}
          </button>
        </form>

        {/* Back to login */}
        <div style={{ marginTop: 24, display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
          <Link
            href="/login"
            style={{
              display: "inline-flex", alignItems: "center", gap: 6,
              fontFamily: "var(--font-mono)", fontSize: 11,
              color: "var(--text-muted)", textDecoration: "none",
              letterSpacing: "0.06em", textTransform: "uppercase",
              transition: "color 0.15s",
            }}
            onMouseEnter={e => (e.currentTarget.style.color = "var(--text-secondary)")}
            onMouseLeave={e => (e.currentTarget.style.color = "var(--text-muted)")}
          >
            <ArrowLeft size={12} />
            Back to Login
          </Link>
        </div>

        <div className="login-footnote">PFE2 · Role: Analyst · v2.0</div>
      </div>
    </div>
  );
}
