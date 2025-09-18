// Minimal domain normalizer for Others input
// - trims, lowercases, strips protocol/port/path
// - converts unicode to punycode using URL API (via toASCII when available)
// - returns apex (heuristic if PSL not present), patterns for permissions, and cookieDomains

export type NormalizedDomain = {
  input: string;
  hostname: string; // punycode, no port
  apex: string; // heuristic eTLD+1
  permissionPatterns: string[]; // [https://apex/*, https://*.apex/*]
  cookieDomains: string[]; // [apex, .apex]
};

const toAscii = (h: string): string => {
  try {
    // Use URL to force punycode conversion
    const u = new URL(`http://${h}`);
    return u.hostname;
  } catch {
    return h;
  }
};

const strip = (s: string): string => s.trim().toLowerCase().replace(/^https?:\/\//, '').replace(/\/.*/, '').replace(/:\d+$/, '');

const heuristicApex = (host: string): string => {
  const parts = host.split('.').filter(Boolean);
  if (parts.length <= 2) return host;
  // naive PSL approximation for common two-part TLDs
  const twoPartTlds = new Set(['co.uk', 'com.au', 'co.jp']);
  const last2 = parts.slice(-2).join('.');
  const last3 = parts.slice(-3).join('.');
  if (twoPartTlds.has(last2)) return parts.slice(-3).join('.');
  return last2;
};

export function normalizeDomain(input: string): NormalizedDomain {
  const stripped = strip(input);
  const hostname = toAscii(stripped);
  if (!hostname || hostname.includes('*') || !hostname.includes('.')) {
    throw new Error('Invalid domain');
  }
  const apex = heuristicApex(hostname);
  return {
    input,
    hostname,
    apex,
    permissionPatterns: [`https://${apex}/*`, `https://*.${apex}/*`],
    cookieDomains: [apex, `.${apex}`],
  };
}


