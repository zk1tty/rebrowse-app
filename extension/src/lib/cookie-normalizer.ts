import type { CookieSiteId } from './cookie-sites';
import { COOKIE_SITES } from './cookie-sites';

export type PlaywrightCookie = {
  name: string;
  value: string;
  domain: string;
  path: string;
  expires: number; // seconds since epoch; 0 or omit for session
  httpOnly: boolean;
  secure: boolean;
  sameSite: 'None' | 'Lax' | 'Strict';
};

export type PlaywrightStorageState = {
  cookies: PlaywrightCookie[];
  origins: any[];
};

const sameSiteMap: Record<string, 'None' | 'Lax' | 'Strict'> = {
  no_restriction: 'None',
  lax: 'Lax',
  strict: 'Strict',
} as const;

const keyOf = (c: chrome.cookies.Cookie): string => `${c.domain}|${c.path}|${c.name}`;

export function mapChromeCookiesToPlaywright(cookies: chrome.cookies.Cookie[]): PlaywrightStorageState {
  const dedup = new Map<string, chrome.cookies.Cookie>();
  for (const c of cookies) {
    if (!c.name || c.value === undefined || c.value === null) continue;
    const k = keyOf(c);
    const prev = dedup.get(k);
    if (!prev || (c.expirationDate ?? 0) > (prev.expirationDate ?? 0)) dedup.set(k, c);
  }
  const out: PlaywrightCookie[] = Array.from(dedup.values()).map((c) => ({
    name: c.name,
    value: c.value,
    domain: c.domain,
    path: c.path,
    expires: Math.trunc(c.expirationDate ?? 0),
    httpOnly: !!c.httpOnly,
    secure: !!c.secure,
    sameSite: sameSiteMap[String(c.sameSite) as keyof typeof sameSiteMap] ?? 'Lax',
  }));
  return { cookies: out, origins: [] };
}

export function validateRequiredCookies(
  siteId: CookieSiteId,
  cookies: chrome.cookies.Cookie[]
): { ok: boolean; missing: string[]; message?: string } {
  const req = COOKIE_SITES[siteId]?.requiredCookies || [];
  const byName = cookies.reduce<Record<string, chrome.cookies.Cookie[]>>((acc, c) => {
    (acc[c.name] ||= []).push(c);
    return acc;
  }, {});
  const missing: string[] = [];
  for (const r of req) if (!byName[r]?.length) missing.push(r);

  let ok = missing.length === 0;
  let reason: string | undefined;
  if (ok) {
    if (siteId === 'facebook') {
      const xsGood = (byName['xs'] || []).some((c) => c.httpOnly === true && c.secure === true);
      const cUserGood = (byName['c_user'] || []).some((c) => (c.value ?? '').length > 0);
      if (!xsGood) { ok = false; reason = 'xs must be httpOnly & secure'; }
      if (!cUserGood) { ok = false; reason = reason ?? 'c_user missing or empty'; }
    } else if (siteId === 'linkedin') {
      const liAtGood = (byName['li_at'] || []).some((c) => c.httpOnly === true);
      const jsGood = (byName['JSESSIONID'] || []).length > 0 ? true : true; // optional but recommended
      if (!liAtGood) { ok = false; reason = 'li_at must be httpOnly'; }
      if (!jsGood) { /* keep ok but we could warn */ }
    } else if (siteId === 'instagram') {
      const sidGood = (byName['sessionid'] || []).some((c) => c.httpOnly === true);
      if (!sidGood) { ok = false; reason = 'sessionid must be httpOnly'; }
    } else if (siteId === 'x') {
      const atGood = (byName['auth_token'] || []).some((c) => c.httpOnly === true);
      if (!atGood) { ok = false; reason = 'auth_token must be httpOnly'; }
    } else if (siteId === 'tiktok') {
      const sessGood = (byName['sessionid'] || []).length > 0;
      if (!sessGood) { ok = false; reason = 'sessionid missing'; }
    }
  }

  return { ok, missing, message: ok ? undefined : (missing.length ? `Missing: ${missing.join(', ')}` : reason) };
}


