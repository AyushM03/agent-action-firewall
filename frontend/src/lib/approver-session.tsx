"use client";

import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from "react";

import { getMe } from "@/services/api";

import { clearToken, getToken, setToken } from "./session";

export type ApproverSession =
  | { status: "checking" }
  | { status: "signed_out" }
  | { status: "signed_in"; token: string; username: string };

type ContextValue = {
  session: ApproverSession;
  signIn: (token: string) => Promise<void>;
  signOut: () => void;
};

const SessionContext = createContext<ContextValue | null>(null);

// One sign-in for the whole dashboard. The token is re-checked with GET /auth/me on load,
// and any page that gets a 401 calls signOut() so the user is sent back to the login form.
export function ApproverSessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<ApproverSession>({ status: "checking" });

  const signOut = useCallback(() => {
    clearToken();
    setSession({ status: "signed_out" });
  }, []);

  const signIn = useCallback(
    async (token: string) => {
      try {
        const me = await getMe(token);
        setToken(token);
        setSession({ status: "signed_in", token, username: me.username });
      } catch {
        signOut();
      }
    },
    [signOut],
  );

  // Restore a session from a previous page load, if its token is still valid.
  useEffect(() => {
    let cancelled = false;
    const token = getToken();
    const check = token ? getMe(token).then((me) => ({ token, username: me.username })) : Promise.resolve(null);
    check
      .catch(() => null)
      .then((user) => {
        if (cancelled) return;
        if (user) setSession({ status: "signed_in", ...user });
        else signOut();
      });
    return () => {
      cancelled = true;
    };
  }, [signOut]);

  return <SessionContext.Provider value={{ session, signIn, signOut }}>{children}</SessionContext.Provider>;
}

export function useApproverSession(): ContextValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useApproverSession must be used inside ApproverSessionProvider");
  return value;
}

/** The signed-in approver's token. Only call this below <AppShell>, which renders pages only when signed in. */
export function useApproverToken(): string {
  const { session } = useApproverSession();
  if (session.status !== "signed_in") throw new Error("useApproverToken called while signed out");
  return session.token;
}
