// Client-side envelope encryption utilities (WebCrypto)

type PublicKeyResponse = { kid: string; alg: string; pem: string };

const b64encode = (buf: ArrayBuffer): string => {
  const bytes = new Uint8Array(buf);
  let binary = "";
  for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
};

const utf8encode = (s: string): ArrayBuffer => new TextEncoder().encode(s);

export async function fetchPublicKey(): Promise<{ kid: string; key: CryptoKey }>{
  const url = `${import.meta.env.VITE_API_URL}/crypto/public-key`;
  const res = await fetch(url, { method: 'GET' });
  if (!res.ok) throw new Error(`Failed to fetch public key: ${res.status}`);
  const data: PublicKeyResponse = await res.json();
  const pem = data.pem.replace(/-----BEGIN PUBLIC KEY-----|-----END PUBLIC KEY-----|\s+/g, '');
  const der = Uint8Array.from(atob(pem), c => c.charCodeAt(0));
  const key = await crypto.subtle.importKey(
    'spki',
    der,
    { name: 'RSA-OAEP', hash: 'SHA-256' },
    false,
    ['wrapKey']
  );
  return { kid: data.kid, key };
}

export async function encryptEnvelope(plaintextJson: string, rsaPublicKey: CryptoKey): Promise<{ nonceB64: string; ciphertextB64: string; wrappedKeyB64: string }>{
  const dataKeyRaw = crypto.getRandomValues(new Uint8Array(32));
  const aesKey = await crypto.subtle.importKey('raw', dataKeyRaw, { name: 'AES-GCM' }, true, ['encrypt','decrypt']);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ciphertext = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, aesKey, utf8encode(plaintextJson));
  const wrapped = await crypto.subtle.wrapKey('raw', aesKey, rsaPublicKey, { name: 'RSA-OAEP' });
  return {
    nonceB64: b64encode(iv.buffer),
    ciphertextB64: b64encode(ciphertext),
    wrappedKeyB64: b64encode(wrapped),
  };
}


