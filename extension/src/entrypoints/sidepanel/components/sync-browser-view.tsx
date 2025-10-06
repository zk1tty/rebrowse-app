import React from 'react';
import { useWorkflow } from '../context/workflow-provider';
import { Button } from '@/components/ui/button';
import { COOKIE_SITES, CookieSiteId, SITE_ICON_LABELS } from '@/lib/cookie-sites';
import { ensureSitePermissions, ensureOrigins, getSiteHostPermissions } from '@/lib/host-permissions';
import { normalizeDomain } from '@/lib/domain-normalizer';
import { ensureAuth } from '@/lib/auth';
import type { CookieSyncStatus } from '@/lib/message-bus-types';
import { CheckCircle2, XCircle, Clock, CircleDot, Cookie, Cloud, CloudUpload, Download, FileKey, RefreshCcw } from 'lucide-react';

type SiteProgress = {
  status: CookieSyncStatus;
  lastUpdated: number;
  message?: string;
  verified?: boolean; // server-side verification result
};

const defaultSelected: CookieSiteId[] = (Object.keys(COOKIE_SITES) as CookieSiteId[])
  .filter((id) => COOKIE_SITES[id].enabledByDefault);

const SyncBrowserView: React.FC = () => {
  const { goHomeView } = useWorkflow();

  const [selectedSites] = React.useState<CookieSiteId[]>(defaultSelected);
  const [othersInput, setOthersInput] = React.useState<string>('');
  const [requestId, setRequestId] = React.useState<string | null>(null);
  const [statuses, setStatuses] = React.useState<Record<string, SiteProgress>>({});
  const [toast, setToast] = React.useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [uploading, setUploading] = React.useState<boolean>(false);
  // removed granting state; we now grant at the start of startSync

  const formatTime = (ms?: number) => (ms ? new Date(ms).toLocaleTimeString() : '-');

  const StatusIcon: React.FC<{ status?: CookieSyncStatus }> = ({ status }) => {
    switch (status) {
      case 'success':
        return <CheckCircle2 className="w-4 h-4 text-green-600" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-600" />;
      case 'processing':
        return <Clock className="w-4 h-4 text-blue-600" />;
      default:
        return <CircleDot className="w-4 h-4 text-gray-400" />; // ready
    }
  };
  const VerifyIcon: React.FC<{ verified?: boolean }> = ({ verified }) => {
    if (verified === undefined) return null;
    return verified ? (
      <CheckCircle2 className="w-4 h-4 text-green-600" />
    ) : (
      <CheckCircle2 className="w-4 h-4 text-red-600" />
    );
  };

  React.useEffect(() => {
    const handler = (message: any) => {
      if (!requestId) return;
      if (message?.type === 'COOKIE_SYNC_PROGRESS' && message.payload?.requestId === requestId) {
        const site = message.payload.site as { siteId: string; status: CookieSyncStatus; lastUpdated: number; message?: string };
        setStatuses((prev) => ({ ...prev, [site.siteId]: { status: site.status, lastUpdated: site.lastUpdated, message: site.message } }));
      }
      if (message?.type === 'COOKIE_SYNC_DONE' && message.payload?.requestId === requestId) {
        const results = message.payload.results as Array<{ siteId: string; status: CookieSyncStatus; lastUpdated: number; message?: string }>;
        setStatuses((prev) => {
          const merged = { ...prev } as Record<string, SiteProgress>;
          results.forEach((r) => {
            const prior = merged[r.siteId];
            merged[r.siteId] = {
              status: r.status,
              lastUpdated: r.lastUpdated,
              // prefer DONE message if present; otherwise keep prior message (from PROGRESS/persist)
              message: r.message !== undefined ? r.message : prior?.message,
            } as SiteProgress;
          });
          return merged;
        });
      }
    };
    chrome.runtime.onMessage.addListener(handler);
    return () => chrome.runtime.onMessage.removeListener(handler);
  }, [requestId]);

  // Load persisted status on mount and subscribe to changes
  React.useEffect(() => {
    const key = 'cookieSyncStatusMap';
    chrome.storage.local.get([key]).then((res) => {
      const map = (res?.[key] ?? {}) as Record<string, { status: CookieSyncStatus; lastUpdated: number; message?: string }>;
      setStatuses(map);
    }).catch(() => {});

    const onChanged = (changes: { [key: string]: chrome.storage.StorageChange }, areaName: string) => {
      if (areaName !== 'local') return;
      const change = changes['cookieSyncStatusMap'];
      if (!change) return;
      const newMap = change.newValue as Record<string, { status: CookieSyncStatus; lastUpdated: number; message?: string }>;
      if (newMap) setStatuses(newMap);
    };
    chrome.storage.onChanged.addListener(onChanged);
    return () => chrome.storage.onChanged.removeListener(onChanged);
  }, []);

  const parseOthers = React.useCallback((): string[] => {
    return othersInput
      .split(/[\,\s]+/)
      .map((s) => s.trim())
      .filter(Boolean);
  }, [othersInput]);

  const startSync = async () => {
    // 0) Grant all site access upfront (previously separate button)
    try {
      const allOrigins = Array.from(new Set(selectedSites.flatMap((id) => getSiteHostPermissions(id))));
      const res = await ensureOrigins(allOrigins, { interactive: true });
      const denied = 'denied' in res ? res.denied : res.missing;
      if (denied && denied.length) {
        setToast({ type: 'error', message: `Permission denied for: ${denied.slice(0, 3).join(', ')}${denied.length > 3 ? '…' : ''}` });
        setTimeout(() => setToast(null), 2500);
      }
    } catch {}
    const rid = (crypto?.randomUUID && crypto.randomUUID()) || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    setRequestId(rid);

    // Initialize statuses to ready (not persisted until processing starts)
    const initial: Record<string, SiteProgress> = {};
    selectedSites.forEach((id) => { initial[id] = { status: 'ready', lastUpdated: Date.now() }; });
    parseOthers().forEach((d) => { initial[`other:${d}`] = { status: 'ready', lastUpdated: Date.now() }; });
    setStatuses((prev) => ({ ...prev, ...initial }));

    // Pre-check/request permissions for all selected items
    const grantedSites: CookieSiteId[] = [];
    for (const id of selectedSites) {
      try {
        const perm = await ensureSitePermissions(id, { interactive: false });
        const denied = 'denied' in perm ? perm.denied : perm.missing;
        if (denied && denied.length) {
          setStatuses((prev) => ({ ...prev, [id]: { status: 'failed', lastUpdated: Date.now(), message: 'Permission denied' } }));
        } else {
          grantedSites.push(id);
        }
      } catch (e) {
        setStatuses((prev) => ({ ...prev, [id]: { status: 'failed', lastUpdated: Date.now(), message: 'Permission error' } }));
      }
    }

    const others = parseOthers();
    const grantedOthers: string[] = [];
    for (const d of others) {
      const key = `other:${d}`;
      try {
        const norm = normalizeDomain(d);
        const origins = norm.permissionPatterns;
        const perm = await ensureOrigins(origins, { interactive: true });
        const denied = 'denied' in perm ? perm.denied : perm.missing;
        if (denied && denied.length) {
          setStatuses((prev) => ({ ...prev, [key]: { status: 'failed', lastUpdated: Date.now(), message: 'Permission denied' } }));
        } else {
          grantedOthers.push(norm.apex);
        }
      } catch (e) {
        setStatuses((prev) => ({ ...prev, [key]: { status: 'failed', lastUpdated: Date.now(), message: 'Permission error' } }));
      }
    }

    // If nothing granted, stop here
    if (grantedSites.length === 0 && grantedOthers.length === 0) {
      console.warn('[SyncBrowserView] No permissions granted; aborting sync');
      return;
    }

    chrome.runtime.sendMessage({
      type: 'START_COOKIE_SYNC',
      payload: { requestId: rid, sites: grantedSites, others: grantedOthers },
    }, (resp: any) => {
      if (chrome.runtime.lastError) {
        console.error('[SyncBrowserView] START_COOKIE_SYNC failed:', chrome.runtime.lastError.message);
      }
    });
  };

  // removed separate grantAllSiteAccess function; logic now runs at start of startSync

  const uploadToCloud = async () => {
    try {
      setUploading(true);
      const rid = (crypto?.randomUUID && crypto.randomUUID()) || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
      // 1) Build JSON for selected sites/others
      const others = parseOthers();
      const resp = await new Promise<any>((resolve) => {
        chrome.runtime.sendMessage({
          type: 'BUILD_COOKIES_JSON',
          payload: { sites: selectedSites, others }
        }, (r: any) => resolve(r));
      });
      if (!resp?.ok) {
        console.error('[SyncBrowserView] BUILD_COOKIES_JSON failed:', resp?.error);
        setToast({ type: 'error', message: 'Build cookies JSON failed' });
        setTimeout(() => setToast(null), 2500);
        setUploading(false);
        return;
      }
      const payloadJson = resp.json as string;

      // 2) Get one-time token from backend using Supabase access token
      const accessToken = await ensureAuth();
      let ott = '';
      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 15000);
        const res = await fetch(`${import.meta.env.VITE_API_URL}/auth/ott`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${accessToken}` },
          signal: controller.signal as any,
        });
        clearTimeout(timer);
        if (!res.ok) throw new Error(`OTT mint failed: ${res.status}`);
        const data = await res.json();
        ott = data?.ott;
        if (!ott) throw new Error('OTT not returned');
      } catch (e) {
        console.error('[SyncBrowserView] mint OTT failed:', e);
        setToast({ type: 'error', message: 'OTT request failed' });
        setTimeout(() => setToast(null), 2500);
        setUploading(false);
        return;
      }

      // 3) Upload encrypted
      let timedOut = false;
      const timeoutId = setTimeout(() => {
        timedOut = true;
        console.error('[SyncBrowserView] UPLOAD_COOKIES_ENCRYPTED timed out');
        setToast({ type: 'error', message: 'Upload timed out' });
        setTimeout(() => setToast(null), 2500);
        setUploading(false);
      }, 25000);

      chrome.runtime.sendMessage({
        type: 'UPLOAD_COOKIES_ENCRYPTED',
        payload: { payloadJson, ott, sites: selectedSites }
      }, (uploadResp: any) => {
        if (timedOut) return;
        clearTimeout(timeoutId);
        if (chrome.runtime.lastError) {
          console.error('[SyncBrowserView] UPLOAD_COOKIES_ENCRYPTED lastError:', chrome.runtime.lastError.message);
          setToast({ type: 'error', message: 'Upload failed' });
          setTimeout(() => setToast(null), 2500);
          setUploading(false);
          return;
        }
        console.log('[SyncBrowserView] UPLOAD_COOKIES_ENCRYPTED:', uploadResp);
        if (uploadResp?.ok) {
          setToast({ type: 'success', message: 'Succesfully uploaded to cloud' });
          // If backend returned verification results, reflect them in the UI statuses
          const verified: Record<string, boolean> | undefined = uploadResp?.result?.verified;
          if (verified) {
            setStatuses((prev) => {
              const copy = { ...prev } as Record<string, SiteProgress>;
              const now = Date.now();
              Object.entries(verified).forEach(([siteId, ok]) => {
                copy[siteId] = {
                  status: ok ? 'success' as const : 'failed' as const,
                  lastUpdated: now,
                  message: ok ? undefined : 'Server verification failed',
                  verified: ok,
                };
              });
              return copy;
            });
          }
        } else {
          setToast({ type: 'error', message: 'Upload failed' });
        }
        setTimeout(() => setToast(null), 2500);
        setUploading(false);
      });
    } catch (e) {
      console.error('[SyncBrowserView] uploadToCloud failed:', e);
      setToast({ type: 'error', message: 'Upload failed' });
      setTimeout(() => setToast(null), 2500);
      setUploading(false);
    }
  };

  return (
    <div className="p-4 space-y-4 relative">
      {toast && (
        <div className={`fixed right-4 top-4 z-50 rounded shadow px-4 py-2 text-sm ${toast.type === 'success' ? 'bg-green-600 text-white' : 'bg-red-600 text-white'}`}>
          {toast.message}
        </div>
      )}
      {uploading && (
        <div className="absolute inset-0 bg-black/30 backdrop-blur-sm z-40 flex items-center justify-center">
          <div className="bg-white rounded-lg shadow p-4 flex items-center gap-3">
            <div className="animate-spin rounded-full h-5 w-5 border-2 border-black border-t-transparent"></div>
            <div className="text-sm text-black">Uploading and verifying…</div>
          </div>
        </div>
      )}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Sync Cookies with Cloud Browsers</h2>
        <button
          className="text-sm text-gray-600 hover:text-black"
          onClick={goHomeView}
        >
          Back
        </button>
      </div>

      <div className="flex justify-end pr-1 text-xs text-gray-500 gap-6">
        <span className="flex items-center gap-1"><Cookie className="w-3 h-3" /> Local</span>
        <span className="flex items-center gap-1"><Cloud className="w-3 h-3" /> Cloud</span>
      </div>
      <div className="space-y-2">
        {(Object.keys(COOKIE_SITES) as CookieSiteId[]).map((id) => {
          const label = SITE_ICON_LABELS[id];
          const s = statuses[id];
          const onClick = async () => {
            try {
              const perm = await ensureSitePermissions(id, { interactive: true });
              const denied = 'denied' in perm ? perm.denied : perm.missing;
              if (denied && denied.length) {
                console.warn('[SyncBrowserView] Permission denied for', id, denied);
                setStatuses((prev) => ({ ...prev, [id]: { status: 'failed', lastUpdated: Date.now(), message: 'Permission denied' } }));
                return;
              }
            } catch (e) {
              console.error('[SyncBrowserView] Permission request failed:', e);
              setStatuses((prev) => ({ ...prev, [id]: { status: 'failed', lastUpdated: Date.now(), message: 'Permission error' } }));
              return;
            }

            chrome.runtime.sendMessage({
              type: 'GET_SITE_COOKIES',
              payload: { siteId: id },
            }, (resp: any) => {
              if (chrome.runtime.lastError) {
                console.error('[SyncBrowserView] GET_SITE_COOKIES failed:', chrome.runtime.lastError.message);
                return;
              }
              console.log('[SyncBrowserView] Cookies fetched:', resp);
            });
          };
          const onLogin = () => {
            const url = COOKIE_SITES[id].loginUrl;
            if (url) chrome.tabs.create({ url }).catch(() => {});
          };
          const showLogin = (s?.status === 'failed') || (s?.message && s.message.toLowerCase().includes('missing'));
          return (
            <div key={id} className="w-full flex items-center justify-between border rounded px-3 py-2 text-left">
              <div className="font-medium">{label}</div>
              <div className="text-sm text-gray-600 flex items-center gap-6">
                {showLogin ? (
                  <button onClick={onLogin} className="underline text-black hover:text-gray-800">Login</button>
                ) : null}
                <span className="flex items-center gap-2">
                  <Cookie className="w-4 h-4 text-gray-600" />
                  <StatusIcon status={s?.status} />
                </span>
                <span className="flex items-center gap-2">
                  <Cloud className="w-4 h-4 text-gray-600" />
                  <VerifyIcon verified={s?.verified} />
                </span>
                {s?.message && s.message.toLowerCase().includes('missing') ? (
                  <span className="text-orange-600">Login required</span>
                ) : null}
                {s?.message && !s.message.toLowerCase().includes('server verified') ? (
                  <span className="text-red-500">{s.message}</span>
                ) : null}
                <span className="text-gray-400">{formatTime(s?.lastUpdated)}</span>
              </div>
            </div>
          );
        })}
      </div>

      <div>
        <div className="text-sm text-gray-600 mb-1">Others:</div>
        <div className="flex items-center gap-3">
          <input
            className="flex-1 border rounded px-3 py-2"
            placeholder="example.com or list (comma/space separated)"
            value={othersInput}
            onChange={(e) => setOthersInput(e.target.value)}
          />
          {parseOthers().map((d) => {
            const key = `other:${d}`;
            const s = statuses[key];
            const onClick = async () => {
            try {
              const norm = normalizeDomain(d);
              const origins = norm.permissionPatterns;
                const perm = await ensureOrigins(origins, { interactive: true });
                const denied = 'denied' in perm ? perm.denied : perm.missing;
                if (denied && denied.length) {
                  console.warn('[SyncBrowserView] Permission denied for domain', d, denied);
                  setStatuses((prev) => ({ ...prev, [key]: { status: 'failed', lastUpdated: Date.now(), message: 'Permission denied' } }));
                  return;
                }
              } catch (e) {
                console.error('[SyncBrowserView] Permission request failed (others):', e);
                setStatuses((prev) => ({ ...prev, [key]: { status: 'failed', lastUpdated: Date.now(), message: 'Permission error' } }));
                return;
              }

              chrome.runtime.sendMessage({
                type: 'GET_SITE_COOKIES',
                payload: { domain: normalizeDomain(d).apex },
              }, (resp: any) => {
                if (chrome.runtime.lastError) {
                  console.error('[SyncBrowserView] GET_SITE_COOKIES(others) failed:', chrome.runtime.lastError.message);
                  return;
                }
                console.log('[SyncBrowserView] Cookies fetched (others):', resp);
              });
            };
            const onLogin = () => chrome.tabs.create({ url: `https://${d}/` }).catch(() => {});
            const showLogin = s?.status === 'failed';
            return (
              <div key={key} className="text-xs text-gray-600 border rounded px-2 py-1">
                <span className="mr-2">{d}</span>
                {showLogin ? (
                  <button onClick={onLogin} className="underline text-black hover:text-gray-800 mr-2">Login</button>
                ) : null}
                <StatusIcon status={s?.status} />
                {s?.message && s.message.toLowerCase().includes('missing') ? (
                  <span className="text-orange-600 mr-2">Login required</span>
                ) : null}
                {s?.message ? <span className="text-red-500 mr-2">{s.message}</span> : null}
                <span className="text-gray-400">{formatTime(s?.lastUpdated)}</span>
              </div>
            );
          })}
        </div>
      </div>

      <div className="pt-2 flex items-center gap-3">
        <Button onClick={startSync} className="bg-black hover:bg-gray-800 text-white px-6 py-2 rounded-lg font-medium">
          <span className="inline-flex items-center gap-2">
            <RefreshCcw className="w-4 h-4" />
            <span>Start sync</span>
          </span>
        </Button>
      </div>

      <div className="pt-2 flex items-center gap-3">
        <Button onClick={uploadToCloud} className="bg-black hover:bg-gray-800 text-white px-6 py-2 rounded-lg font-medium">
          <span className="inline-flex items-center gap-2">
            <CloudUpload className="w-4 h-4" />
            <span>Upload to cloud</span>
          </span>
        </Button>
        <Button
          onClick={() => {
            chrome.runtime.sendMessage({
              type: 'DOWNLOAD_COOKIES_JSON',
              payload: { sites: selectedSites, others: parseOthers() },
            }, (resp: any) => {
              if (chrome.runtime.lastError) {
                console.error('[SyncBrowserView] DOWNLOAD_COOKIES_JSON failed:', chrome.runtime.lastError.message);
                return;
              }
              console.log('[SyncBrowserView] DOWNLOAD_COOKIES_JSON:', resp);
            });
          }}
          className="bg-white text-black border border-gray-300 hover:bg-gray-50 px-6 py-2 rounded-lg font-medium"
        >
          <span className="inline-flex items-center gap-2">
            <Download className="w-4 h-4" />
            <span>Download JSON</span>
          </span>
        </Button>
      </div>
    </div>
  );
};

export default SyncBrowserView;


