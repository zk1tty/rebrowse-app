import { Workflow } from "./workflow-types"; // Assuming Workflow is in this path

// Types for events sent via HTTP to the Python server

export interface HttpWorkflowUpdateEvent {
  type: "WORKFLOW_UPDATE";
  timestamp: number;
  payload: Workflow;
}

export interface HttpRecordingStartedEvent {
  type: "RECORDING_STARTED";
  timestamp: number;
  payload: {
    message: string;
  };
}

export interface HttpRecordingStoppedEvent {
  type: "RECORDING_STOPPED";
  timestamp: number;
  payload: {
    message: string;
  };
}

// If you plan to send other types of events, like TERMINATE_COMMAND, define them here too
// export interface HttpTerminateCommandEvent {
//   type: "TERMINATE_COMMAND";
//   timestamp: number;
//   payload: {
//     reason?: string; // Optional reason for termination
//   };
// }

export type HttpEvent =
  | HttpWorkflowUpdateEvent
  | HttpRecordingStartedEvent
  | HttpRecordingStoppedEvent;
// | HttpTerminateCommandEvent; // Add other event types to the union if defined

// ---------------- Cookie Sync Message Bus (UI <-> Background) ----------------

export type CookieSyncStatus = 'ready' | 'processing' | 'success' | 'failed';

export interface CookieSyncSiteProgress {
  siteId: string; // e.g., 'x' | 'linkedin' | 'tiktok' | 'other:<domain>'
  status: CookieSyncStatus;
  lastUpdated: number; // ms epoch
  message?: string; // optional human-readable hint
}

export interface StartCookieSyncMessage {
  type: 'START_COOKIE_SYNC';
  payload: {
    requestId: string;
    sites: string[]; // e.g., ['x','linkedin','tiktok']
    others?: string[]; // e.g., ['example.com']
  };
}

export interface CookieSyncProgressMessage {
  type: 'COOKIE_SYNC_PROGRESS';
  payload: {
    requestId: string;
    site: CookieSyncSiteProgress;
  };
}

export interface CookieSyncDoneMessage {
  type: 'COOKIE_SYNC_DONE';
  payload: {
    requestId: string;
    results: CookieSyncSiteProgress[]; // final per-site statuses
  };
}

export interface CookieSyncErrorMessage {
  type: 'COOKIE_SYNC_ERROR';
  payload: {
    requestId: string;
    error: string;
  };
}

export type CookieSyncMessage =
  | StartCookieSyncMessage
  | CookieSyncProgressMessage
  | CookieSyncDoneMessage
  | CookieSyncErrorMessage;

// ---------------- Cookie Fetch (UI -> Background) ----------------

export interface GetSiteCookiesMessage {
  type: 'GET_SITE_COOKIES';
  payload: {
    siteId?: string; // e.g., 'x' | 'linkedin' | 'tiktok'
    domain?: string; // e.g., 'example.com' for Others
    storeId?: string; // optional, default to regular profile
  };
}

export interface GetSiteCookiesResponse {
  ok: boolean;
  siteKey: string; // siteId or `other:domain`
  cookies?: chrome.cookies.Cookie[];
  error?: string;
}

