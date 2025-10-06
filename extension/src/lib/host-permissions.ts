import { COOKIE_SITES, CookieSiteId } from './cookie-sites';

export type PermissionCheckResult = {
  required: string[];
  granted: string[];
  missing: string[];
};

export type PermissionRequestResult = {
  requested: string[];
  granted: string[];
  denied: string[];
  success: boolean; // true if all requested were granted
};

const toUniqueSorted = (arr: string[]): string[] => Array.from(new Set(arr)).sort();

export const getAllGrantedOrigins = async (): Promise<string[]> => {
  const all = await chrome.permissions.getAll();
  return toUniqueSorted(all.origins ?? []);
};

export const checkOrigins = async (origins: string[]): Promise<PermissionCheckResult> => {
  const required = toUniqueSorted(origins);
  const grantedOrigins = await getAllGrantedOrigins();
  const grantedSet = new Set(grantedOrigins);
  // IMPORTANT: Do NOT treat '<all_urls>' or protocol wildcards as sufficient for privileged APIs
  // like chrome.cookies. We require explicit host grants for each origin we plan to access.
  const isGranted = (origin: string) => grantedSet.has(origin);
  const granted = required.filter((o) => isGranted(o));
  const missing = required.filter((o) => !isGranted(o));
  return { required, granted, missing };
};

// Request optional host permissions at runtime (must be called from a user gesture)
export const requestOrigins = async (origins: string[]): Promise<PermissionRequestResult> => {
  const unique = toUniqueSorted(origins);
  if (unique.length === 0) {
    return { requested: [], granted: [], denied: [], success: true };
  }

  // chrome.permissions.request returns boolean: true if all requested permissions were granted
  const allGranted = await chrome.permissions.request({ origins: unique });

  // After request, re-check to compute granted/denied details
  const check = await checkOrigins(unique);
  const granted = check.granted;
  const denied = check.missing;

  return {
    requested: unique,
    granted,
    denied,
    success: allGranted && denied.length === 0,
  };
};

export const ensureOrigins = async (
  origins: string[],
  options: { interactive: boolean } = { interactive: true }
): Promise<PermissionRequestResult | PermissionCheckResult> => {
  const check = await checkOrigins(origins);
  if (check.missing.length === 0) return check;

  if (!options.interactive) {
    return check; // do not prompt; report missing
  }

  return requestOrigins(check.missing);
};

export const getSiteHostPermissions = (siteId: CookieSiteId): string[] => {
  const site = COOKIE_SITES[siteId];
  return toUniqueSorted(site.hostPermissions);
};

export const ensureSitePermissions = async (
  siteId: CookieSiteId,
  options: { interactive: boolean } = { interactive: true }
): Promise<PermissionRequestResult | PermissionCheckResult> => {
  const origins = getSiteHostPermissions(siteId);
  return ensureOrigins(origins, options);
};

// Helper for "Others" input: build reasonable host permission patterns for a domain
export const buildHostPermissionPatternsForDomain = (domain: string): string[] => {
  const normalized = domain.trim().toLowerCase().replace(/^https?:\/\//, '').replace(/\/$/, '');
  if (!normalized) return [];
  // Request both apex and wildcard subdomains
  return [`https://${normalized}/*`, `https://*.${normalized}/*`];
};


