// The approver's JWT lives in sessionStorage: it's gone when the tab closes, and
// it expires server-side after JWT_EXPIRE_MINUTES regardless.

const TOKEN_KEY = "aaf.approverToken";

export function getToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  try {
    sessionStorage.setItem(TOKEN_KEY, token);
  } catch {
    // Storage unavailable (private mode etc.) — the user will just need to log in again.
  }
}

export function clearToken(): void {
  try {
    sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // Nothing to clear.
  }
}
