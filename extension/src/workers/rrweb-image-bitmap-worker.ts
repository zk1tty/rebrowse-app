// This worker is intentionally minimal to avoid large base64 blobs.
// If we later want to support snapshotting, implement conversion to dataURL safely.

self.onmessage = (e: MessageEvent) => {
  // Echo back only the id to satisfy rrweb's CanvasManager expectation of a response.
  // We do not perform bitmap->blob conversion here to keep bundle lean and avoid obfuscated code.
  const { id } = (e.data as any) || {};
  // @ts-ignore
  self.postMessage({ id });
};

export {};


