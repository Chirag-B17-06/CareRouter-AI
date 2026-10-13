// Browser-side session handling.
//
// The access token lives in sessionStorage (cleared when the tab closes) and in memory.  It is
// never placed in a URL or written to the console.  The server enforces authorisation on every
// request; this module only decides what to *show*.
import { SessionUser } from '../types';

const TOKEN_KEY = 'carerouter.session.token';
const USER_KEY = 'carerouter.session.user';

let memoryToken: string | null = null;
let memoryUser: SessionUser | null = null;

function safeGet(key: string): string | null {
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null; // storage can be unavailable (private mode / blocked): fall back to memory only
  }
}

function safeSet(key: string, value: string | null) {
  try {
    if (value === null) window.sessionStorage.removeItem(key);
    else window.sessionStorage.setItem(key, value);
  } catch {
    /* memory copy still works for this page load */
  }
}

export function getToken(): string | null {
  return memoryToken ?? safeGet(TOKEN_KEY);
}

export function getStoredUser(): SessionUser | null {
  if (memoryUser) return memoryUser;
  const raw = safeGet(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as SessionUser;
  } catch {
    return null;
  }
}

export function saveSession(token: string, user: SessionUser) {
  memoryToken = token;
  memoryUser = user;
  safeSet(TOKEN_KEY, token);
  safeSet(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  memoryToken = null;
  memoryUser = null;
  safeSet(TOKEN_KEY, null);
  safeSet(USER_KEY, null);
}

export const SESSION_EXPIRED_EVENT = 'carerouter:session-expired';

export function hasPermission(user: SessionUser | null, permission: string): boolean {
  return !!user && user.permissions.includes(permission);
}
