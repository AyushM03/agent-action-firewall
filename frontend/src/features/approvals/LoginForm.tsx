"use client";

import { type FormEvent, useState } from "react";

import { Button } from "@/components/Button";
import { login } from "@/services/api";

export function LoginForm({ onLoggedIn }: { onLoggedIn: (token: string) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const { access_token } = await login(username, password);
      onLoggedIn(access_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed.");
      setSubmitting(false);
    }
  }

  const inputClass =
    "mt-1 block w-full rounded-md border border-slate-300 bg-surface px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary";

  return (
    <form
      onSubmit={handleSubmit}
      className="mx-auto w-full max-w-sm rounded-card border border-slate-200 bg-surface p-6 shadow-sm"
    >
      <h2 className="text-base font-semibold">Approver sign-in</h2>
      <p className="mt-1 text-sm text-muted">Only approvers can review queued agent actions.</p>

      <label className="mt-5 block text-sm font-medium">
        Username
        <input
          className={inputClass}
          autoComplete="username"
          required
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
      </label>
      <label className="mt-3 block text-sm font-medium">
        Password
        <input
          className={inputClass}
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </label>

      {error && (
        <p role="alert" className="mt-3 text-sm text-status-denied">
          {error}
        </p>
      )}

      <Button type="submit" className="mt-5 w-full" disabled={submitting}>
        {submitting ? "Signing in…" : "Sign in"}
      </Button>
    </form>
  );
}
