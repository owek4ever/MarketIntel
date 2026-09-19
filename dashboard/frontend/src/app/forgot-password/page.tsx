"use client";
import { useState, FormEvent, useRef, KeyboardEvent } from "react";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api";
import { BarChart2, ArrowLeft, Mail, KeyRound, CheckCircle } from "lucide-react";
import Link from "next/link";

type Step = "email" | "code" | "success";

export default function ForgotPasswordPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("email");

  // Step 1
  const [email, setEmail] = useState("");
  // Step 2
  const [codeDigits, setCodeDigits] = useState(["", "", "", "", "", ""]);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const codeRefs = useRef<(HTMLInputElement | null)[]>([]);

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // ── Step 1: send OTP ───────────────────────────────────────────────────────
  async function handleSendCode(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await authApi.forgotPassword(email);
      setStep("code");
    } catch {
      setError("REQUEST FAILED — Please try again.");
    } finally {
      setLoading(false);
    }
  }

  // ── OTP digit input helpers ────────────────────────────────────────────────
  function handleDigitChange(index: number, value: string) {
    // Accept only digits
    const digit = value.replace(/\D/g, "").slice(-1);
    const next = [...codeDigits];
    next[index] = digit;
    setCodeDigits(next);
    if (digit && index < 5) {
      codeRefs.current[index + 1]?.focus();
    }
  }

  function handleDigitKeyDown(index: number, e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Backspace" && !codeDigits[index] && index > 0) {
      codeRefs.current[index - 1]?.focus();
    }
    if (e.key === "ArrowLeft" && index > 0) codeRefs.current[index - 1]?.focus();
    if (e.key === "ArrowRight" && index < 5) codeRefs.current[index + 1]?.focus();
  }

  function handleDigitPaste(e: React.ClipboardEvent) {
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (pasted.length === 6) {
      setCodeDigits(pasted.split(""));
      codeRefs.current[5]?.focus();
      e.preventDefault();
    }
  }

  // ── Step 2: verify OTP + reset password ───────────────────────────────────
  async function handleReset(e: FormEvent) {
    e.preventDefault();
    setError("");

    const code = codeDigits.join("");
    if (code.length !== 6) {
      setError("INCOMPLETE CODE — Enter all 6 digits.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("MISMATCH — Passwords do not match.");
      return;
    }
    if (newPassword.length < 8) {
      setError("WEAK PASSWORD — Minimum 8 characters required.");
      return;
    }

    setLoading(true);
    try {
      await authApi.resetPassword(email, code, newPassword);
      setStep("success");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ? `ERROR — ${msg}` : "RESET FAILED — Invalid or expired code.");
    } finally {
      setLoading(false);
    }
  }

  // ── Success ────────────────────────────────────────────────────────────────
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

          <div className="login-headline">Password Reset Complete</div>
          <div className="login-title" style={{ marginBottom: 16 }}>
            All sessions revoked<span className="cursor-blink" />
          </div>

          <p style={{
            fontFamily: "var(--font-mono)", fontSize: 12,
            color: "var(--text-secondary)", lineHeight: 1.7, marginBottom: 32,
          }}>
            Your password has been updated successfully.<br />
            All active sessions have been invalidated for security.<br />
            Please log in with your new password.
          </p>

          <button
            className="btn btn-primary"
            style={{ width: "100%", justifyContent: "center", padding: "10px 0", fontSize: 13 }}
            onClick={() => router.push("/login")}
          >
            <span style={{ fontFamily: "var(--font-mono)", letterSpacing: "0.08em" }}>
              PROCEED TO LOGIN
            </span>
          </button>

          <div className="login-footnote">MarketIntel · Security Event · v2.0</div>
        </div>
      </div>
    );
  }

  // ── Step 2: OTP + new password ─────────────────────────────────────────────
  if (step === "code") {
    return (
      <div className="login-shell">
        <div className="login-panel animate-in">

          <div className="login-logo-mark">
            <KeyRound size={18} color="#000" strokeWidth={2.5} />
          </div>

          <div className="login-headline">Step 2 of 2 — Enter Code</div>
          <div className="login-title">
            Reset Password<span className="cursor-blink" />
          </div>

          {/* Info banner */}
          <div style={{
            fontFamily: "var(--font-mono)", fontSize: 11,
            color: "var(--text-secondary)", background: "var(--bg-raised)",
            border: "1px solid var(--border-bright)", padding: "10px 12px",
            marginBottom: 24, lineHeight: 1.6, letterSpacing: "0.02em",
          }}>
            A 6-digit code was sent to{" "}
            <span style={{ color: "var(--accent)" }}>{email}</span>.
            Check your inbox (and spam folder).
          </div>

          {error && <div className="login-error">{error}</div>}

          <form onSubmit={handleReset} style={{ display: "flex", flexDirection: "column", gap: 20 }}>

            {/* OTP digit boxes */}
            <div>
              <label className="form-label">Confirmation code</label>
              <div style={{ display: "flex", gap: 8, justifyContent: "space-between" }} onPaste={handleDigitPaste}>
                {codeDigits.map((digit, i) => (
                  <input
                    key={i}
                    ref={el => { codeRefs.current[i] = el; }}
                    id={`otp-digit-${i}`}
                    className="input"
                    type="text"
                    inputMode="numeric"
                    maxLength={1}
                    value={digit}
                    onChange={e => handleDigitChange(i, e.target.value)}
                    onKeyDown={e => handleDigitKeyDown(i, e)}
                    style={{
                      width: 48, textAlign: "center", fontSize: 22,
                      fontFamily: "var(--font-mono)", fontWeight: 600,
                      letterSpacing: 0, padding: "12px 0",
                      color: digit ? "var(--accent)" : "var(--text-muted)",
                      borderColor: digit ? "var(--accent)" : undefined,
                    }}
                    autoFocus={i === 0}
                    required
                  />
                ))}
              </div>
              <div style={{
                fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text-muted)",
                marginTop: 6, letterSpacing: "0.04em",
              }}>
                Tip: paste the 6-digit code directly
              </div>
            </div>

            <div>
              <label className="form-label" htmlFor="reset-new-password">New password</label>
              <input
                id="reset-new-password"
                className="input"
                type="password"
                autoComplete="new-password"
                value={newPassword}
                onChange={e => setNewPassword(e.target.value)}
                placeholder="Min. 8 characters"
                required
              />
            </div>

            <div>
              <label className="form-label" htmlFor="reset-confirm-password">Confirm new password</label>
              <input
                id="reset-confirm-password"
                className="input"
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                placeholder="Repeat your new password"
                required
              />
              {confirmPassword.length > 0 && (
                <div style={{
                  fontFamily: "var(--font-mono)", fontSize: 10, marginTop: 4,
                  color: newPassword === confirmPassword ? "#4ade80" : "#f87171",
                  letterSpacing: "0.06em", textTransform: "uppercase",
                }}>
                  {newPassword === confirmPassword ? "✓ Passwords match" : "✗ Passwords do not match"}
                </div>
              )}
            </div>

            <button
              id="reset-submit"
              className="btn btn-primary"
              type="submit"
              disabled={loading || codeDigits.some(d => !d)}
              style={{ width: "100%", justifyContent: "center", padding: "10px 0", fontSize: 13 }}
            >
              {loading ? (
                <span style={{ fontFamily: "var(--font-mono)", letterSpacing: "0.08em" }}>UPDATING PASSWORD…</span>
              ) : (
                <span style={{ fontFamily: "var(--font-mono)", letterSpacing: "0.08em" }}>RESET PASSWORD</span>
              )}
            </button>
          </form>

          {/* Resend link */}
          <div style={{ marginTop: 20, textAlign: "center" }}>
            <button
              style={{
                background: "none", border: "none", cursor: "pointer",
                fontFamily: "var(--font-mono)", fontSize: 10,
                color: "var(--text-muted)", letterSpacing: "0.06em",
                textTransform: "uppercase", textDecoration: "underline",
                transition: "color 0.15s",
              }}
              onClick={() => { setStep("email"); setCodeDigits(["","","","","",""]); setError(""); }}
            >
              Resend code / use a different email
            </button>
          </div>

          <div className="login-footnote">MarketIntel · Code expires in 10 min · v2.0</div>
        </div>
      </div>
    );
  }

  // ── Step 1: enter email ────────────────────────────────────────────────────
  return (
    <div className="login-shell">
      <div className="login-panel animate-in">

        <div className="login-logo-mark">
          <Mail size={18} color="#000" strokeWidth={2.5} />
        </div>

        <div className="login-headline">Step 1 of 2 — Enter Email</div>
        <div className="login-title">
          Forgot Password<span className="cursor-blink" />
        </div>

        <p style={{
          fontFamily: "var(--font-mono)", fontSize: 11,
          color: "var(--text-secondary)", lineHeight: 1.7,
          marginBottom: 24, letterSpacing: "0.02em",
        }}>
          Enter the email address linked to your account. If it exists, we&apos;ll
          send a 6-digit reset code to your inbox.
        </p>

        {error && <div className="login-error">{error}</div>}

        <form onSubmit={handleSendCode} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <label className="form-label" htmlFor="forgot-email">Email address</label>
            <input
              id="forgot-email"
              className="input"
              type="email"
              autoComplete="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="operator@marketintel.com"
              required
              autoFocus
            />
          </div>

          <button
            id="forgot-submit"
            className="btn btn-primary"
            type="submit"
            disabled={loading}
            style={{ width: "100%", justifyContent: "center", padding: "10px 0", marginTop: 8, fontSize: 13 }}
          >
            {loading ? (
              <span style={{ fontFamily: "var(--font-mono)", letterSpacing: "0.08em" }}>SENDING CODE…</span>
            ) : (
              <span style={{ fontFamily: "var(--font-mono)", letterSpacing: "0.08em" }}>SEND RESET CODE</span>
            )}
          </button>
        </form>

        <div style={{ marginTop: 24, display: "flex", alignItems: "center", justifyContent: "center" }}>
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

        <div className="login-footnote">MarketIntel · Intelligence Platform · v2.0</div>
      </div>
    </div>
  );
}
