// Minimal replacement for rrweb's inline base64 worker factory.
// We provide a no-op factory that avoids bundling the large base64 blob.

export default function WorkerFactory(): Worker {
  // Return a dummy worker-like object using a minimal inline blob that echoes back a structure
  const workerCode = `
    self.onmessage = (e) => {
      // Echo back only the id; skip any base64/image processing to keep bundle clean
      const { id } = e.data || {};
      self.postMessage({ id });
    };
  `;
  const blob = new Blob([workerCode], { type: 'application/javascript' });
  const url = URL.createObjectURL(blob);
  // @ts-expect-error: Worker constructor available in browser content scripts
  return new Worker(url);
}


