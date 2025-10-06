export type CookieSiteId = 'x' | 'linkedin' | 'tiktok' | 'instagram' | 'facebook';

export type CookieSite = {
  id: CookieSiteId;
  label: string;
  // host permissions to request (origins), MV3-style patterns
  hostPermissions: string[];
  // cookie query filters (domains) to pass to chrome.cookies.getAll
  cookieDomains: string[];
  enabledByDefault: boolean;
  // must-have cookie names for auth success on this site
  requiredCookies?: string[];
  // login URL to prompt the user when required cookies are missing
  loginUrl?: string;
};

// 
// Must-have cookies for major SNS sites
//
export const COOKIE_SITES: Record<CookieSiteId, CookieSite> = {
  x: {
    id: 'x',
    label: 'X',
    hostPermissions: [
      'https://x.com/*',
      'https://*.x.com/*',
      'https://twitter.com/*',
      'https://*.twitter.com/*',
    ],
    cookieDomains: ['x.com', '.x.com', 'twitter.com', '.twitter.com'],
    enabledByDefault: true,
    requiredCookies: ['auth_token'],
    loginUrl: 'https://x.com/login',
  },
  linkedin: {
    id: 'linkedin',
    label: 'LinkedIn',
    hostPermissions: ['https://*.linkedin.com/*'],
    cookieDomains: [
      'linkedin.com', '.linkedin.com',
      'www.linkedin.com', '.www.linkedin.com',
      'login.linkedin.com', '.login.linkedin.com'
    ],
    enabledByDefault: true,
    requiredCookies: ['li_at'],
    loginUrl: 'https://www.linkedin.com/login',
  },
  tiktok: {
    id: 'tiktok',
    label: 'TikTok',
    hostPermissions: ['https://*.tiktok.com/*'],
    cookieDomains: ['tiktok.com', '.tiktok.com', 'www.tiktok.com', '.www.tiktok.com'],
    enabledByDefault: true,
    loginUrl: 'https://www.tiktok.com/login',
    requiredCookies: ['sessionid'],
  },
  instagram: {
    id: 'instagram',
    label: 'Instagram',
    hostPermissions: ['https://*.instagram.com/*'],
    cookieDomains: [
      'instagram.com', '.instagram.com',
      'www.instagram.com', '.www.instagram.com',
      'm.instagram.com', '.m.instagram.com'
    ],
    enabledByDefault: true,
    requiredCookies: ['sessionid'],
    loginUrl: 'https://www.instagram.com/accounts/login',
  },
  facebook: {
    id: 'facebook',
    label: 'Facebook',
    hostPermissions: ['https://*.facebook.com/*'],
    cookieDomains: ['facebook.com', '.facebook.com', 'www.facebook.com', '.www.facebook.com'],
    enabledByDefault: true,
    requiredCookies: ['c_user', 'xs'],
    loginUrl: 'https://www.facebook.com/login',
  },
};

export type SiteIconKey = CookieSiteId | 'other';

export const SITE_ICON_LABELS: Record<SiteIconKey, string> = {
  x: 'X',
  linkedin: 'LinkedIn',
  tiktok: 'TikTok',
  instagram: 'Instagram',
  facebook: 'Facebook',
  other: 'Other',
};


