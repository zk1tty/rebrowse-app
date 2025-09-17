import React from 'react';
import { useWorkflow } from '../context/workflow-provider';
import { Button } from '@/components/ui/button';
import { COOKIE_SITES, CookieSiteId, SITE_ICON_LABELS } from '@/lib/cookie-sites';
import { ensureSitePermissions, ensureOrigins, buildHostPermissionPatternsForDomain } from '@/lib/host-permissions';
import type { CookieSyncStatus } from '@/lib/message-bus-types';
import { CheckCircle2, XCircle, Clock, CircleDot } from 'lucide-react';

type SiteProgress = {
  status: CookieSyncStatus;
  lastUpdated: number;
  message?: string;
};

const defaultSelected: CookieSiteId[] = (Object.keys(COOKIE_SITES) as CookieSiteId[])
  .filter((id) => COOKIE_SITES[id].enabledByDefault);

const SyncBrowserView: React.FC = () => {
  const { goHomeView } = useWorkflow();

  const [selectedSites] = React.useState<CookieSiteId[]>(defaultSelected);
  const [othersInput, setOthersInput] = React.useState<string>('');
  const [requestId, setRequestId] = React.useState<string | null>(null);
  const [statuses, setStatuses] = React.useState<Record<string, SiteProgress>>({});

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
          results.forEach((r) => { merged[r.siteId] = { status: r.status, lastUpdated: r.lastUpdated, message: r.message } as SiteProgress; });
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
        const perm = await ensureSitePermissions(id, { interactive: true });
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
        const origins = buildHostPermissionPatternsForDomain(d);
        const perm = await ensureOrigins(origins, { interactive: true });
        const denied = 'denied' in perm ? perm.denied : perm.missing;
        if (denied && denied.length) {
          setStatuses((prev) => ({ ...prev, [key]: { status: 'failed', lastUpdated: Date.now(), message: 'Permission denied' } }));
        } else {
          grantedOthers.push(d);
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

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Website list to sync with cloud browser</h2>
        <button
          className="text-sm text-gray-600 hover:text-black"
          onClick={goHomeView}
        >
          Back
        </button>
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
              <div className="text-sm text-gray-600 flex items-center gap-3">
                {showLogin ? (
                  <button onClick={onLogin} className="underline text-black hover:text-gray-800">Login</button>
                ) : null}
                <StatusIcon status={s?.status} />
                {s?.message && s.message.toLowerCase().includes('missing') ? (
                  <span className="text-orange-600">Login required</span>
                ) : null}
                {s?.message ? <span className="text-red-500">{s.message}</span> : null}
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
                const origins = buildHostPermissionPatternsForDomain(d);
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
                payload: { domain: d },
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
          Start sync
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
          Download JSON
        </Button>
      </div>
    </div>
  );
};

export default SyncBrowserView;


