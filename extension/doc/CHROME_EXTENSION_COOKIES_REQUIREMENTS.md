### Chrome Extension (MV3) — One‑Click Cookie Export

#### Objective
- Enable users to export authentication cookies for selected sites in one click and deliver a Playwright‑compatible `storage_state.json` (cookies only) to our backend securely.

#### In Scope
- Cookies only (includes httpOnly, secure, sameSite, expiry, domain/path).
- Initial sites: `x.com`, `linkedin.com`, `instagram.com`, `facebook.com`, `tiktok.com`.
- Extensible to N sites via configuration.

#### Out of Scope (for this MVP)
- localStorage, sessionStorage, IndexedDB export.
- Decrypting or touching OS cookie databases.

---

### User Experience
1) User clicks the extension action (toolbar).
2) First run only: extension requests per‑site optional host permissions (one prompt per domain). User approves.
3) Extension immediately collects cookies for each configured site in the background (no page navigation required).
4) Extension builds a `storage_state.json` payload (cookies only).
5) User chooses one of:
   - Upload securely to backend (default), or
   - Download JSON locally (optional feature).
6) Show verification result (server checks an authenticated endpoint and returns success/failure per site).

Time budget: ≤ 3 seconds for 5 sites on a warm browser.

---

### Permissions (MV3)
- `cookies` — read cookies (including httpOnly) for specified domains.
- `host_permissions` — optional origins per target site (request on demand):
  - `https://x.com/*`
  - `https://*.linkedin.com/*`
  - `https://*.instagram.com/*`
  - `https://*.facebook.com/*`
  - `https://*.tiktok.com/*`
- Optional:
  - `storage` — persist lightweight settings (e.g., which sites enabled).
  - `downloads` — enable “Download JSON” option.
  - `activeTab` — only if supporting “export current site” without prior host permission.

Notes:
- Do not request `<all_urls>`.
- Support Incognito only if the user enables “Allow in incognito” and we explicitly target the `storeId` for incognito sessions. Default scope is regular profile only.

---

### Data Collection
- For each origin group, call `chrome.cookies.getAll` with appropriate domain filters. Include subdomains and partitioned cookies when available.
- Do not open tabs; cookies API works headlessly with granted host permissions.

Domain handling:
- Normalize to effective top‑level domain plus one (eTLD+1) for configuration, but query with exact host rules to capture cookies on subdomains.

Partitioned/CHIPS cookies:
- If returned by the API, preserve partition information. For Playwright compatibility, if a partition key is unavailable, fall back to standard cookie fields.

---

### Output Schema (Playwright‑compatible, cookies only)
The extension produces a single JSON object with a `cookies` array and an empty `origins` array.

```json
{
  "cookies": [
    {
      "name": "sessionid",
      "value": "...",
      "domain": ".example.com",
      "path": "/",
      "expires": 1767225600,
      "httpOnly": true,
      "secure": true,
      "sameSite": "Lax"
    }
  ],
  "origins": []
}
```

Field mapping:
- `expirationDate` (Chrome) → `expires` (integer, seconds since epoch; use 0 or omit if session cookie).
- Chrome `sameSite` values ("no_restriction"/"lax"/"strict") → `None`/`Lax`/`Strict`.
- Preserve `domain` and `path` exactly as returned.

Validation:
- Deduplicate cookies by tuple `(domain, path, name)` keeping the newest expiry.
- Drop cookies with empty `name` or `value`.

---
### Must-have variables for major SNS(cookies-only)

- x.com
  - Required: auth_token (httpOnly, domain: .x.com)
  - Recommended for actions/POSTs: ct0 (CSRF, domain: .x.com)
  - Nice-to-have: twid (user id mapping). Guest cookies (guest_id, guest_id_ads, guest_id_marketing) are not required when authenticated.

- linkedin.com
  - Required: li_at (httpOnly, typically host-only on https://www.linkedin.com)
  - Recommended for stability/CSRF: JSESSIONID (often on .www.linkedin.com)
  - Nice-to-have: bcookie/bscookie (tracking/consistency), lidc (routing). They’re not strictly auth but often present.
  - Tip: Query both .linkedin.com and .www.linkedin.com to capture li_at + JSESSIONID.

- instagram.com
  - Required: sessionid (httpOnly, domain: .instagram.com)
  - Recommended for actions/POSTs: csrftoken (CSRF), ds_user_id (identifies account)
  - Nice-to-have: mid (device id). Not required for being considered logged in.

- web.whatsapp.com
  - Cookies-only is not sufficient. WhatsApp Web’s auth/session state is primarily in IndexedDB/localStorage (e.g., previously WABrowserId/WASecretBundle/WAToken1/WAToken2; modern MD sessions use different app-state keys). To “be logged in” you’d need to export/import those stores, which is out of scope for the cookies-only MVP.

- facebook.com
  - Required: `c_user` (user id), `xs` (session secret; httpOnly, secure, domain: .facebook.com)
  - Recommended (stability/routing): `spin` (version/routing), `wd` (viewport), `locale`
  - **Not required**: `datr`, `sb`, `fr`, `presence` (device, tracking, presence)
  - **Scope tips**:
    - Collect from `.facebook.com` and `www.facebook.com`
    - Keep session cookies (expires=0)
    - Verify by loading `https://www.facebook.com/` and checking that both `c_user` and `xs` are present in the exported set

Notes:
- Ensure the cookies are from the correct profile (storeId) and host scope (e.g., www.linkedin.com vs .linkedin.com).
- Session cookies (expires=0) are still essential—include them as-is.
- For LinkedIn in your test, missing li_at is the reason login didn’t stick. Adding li_at (and JSESSIONID) should fix it.
---

### Security & Privacy
- Least privilege: request host permissions only for sites the user selects.
- The extension must never persist raw cookie values beyond the immediate export operation (unless the user downloads JSON by choice).
- Upload flow uses a short‑lived, single‑use token the web app provides after user login.
- Client‑side encryption before upload:
  - Use WebCrypto (AES‑GCM with a random data key; wrap the data key using a backend‑provided public key like RSA‑OAEP or X25519). Send ciphertext + wrapped key + nonce + auth tag.
- Transport: HTTPS only.
- Include nonce, issued‑at, and one‑time token to prevent replay.
- Provide a clear consent screen listing domains and what will be exported.

---

### Backend Contract
- Endpoint: `POST /auth/storage-state`
  - Headers: `Authorization: Bearer <one-time-token>`
  - Body: `{ ciphertext, wrappedKey, nonce, tag, metadata }`
    - `metadata`: `{ sites: string[], createdAt: iso8601, version: "cookies-v1" }`
- Server decrypts, validates schema, normalizes cookies, and stores per user. Optionally verifies by launching headless Chromium and performing a lightweight authenticated call per site.
- Response: `200 OK` with `{ verified: { [site]: true|false }, id: "..." }`.

---

### Error Handling (User‑visible)
- Permission denied for a site → Show granular failure ("LinkedIn permission not granted"), allow retry.
- No cookies returned → Show hint to ensure the user is logged in and not in guest/incognito unless selected.
- Network/upload failure → Allow retry; never cache cookie payload unencrypted.
- Token expired → Ask the web app for a fresh one‑time token.

---

### Acceptance Criteria
- One click exports cookies for all selected sites without opening visible tabs.
- First run may show up to one permission prompt per site; subsequent runs show none.
- Output JSON matches Playwright cookie schema; loading it authenticates sessions for the 5 target sites in our headless environment.
- Total time for 5 sites ≤ 3 seconds on a typical machine.
- No cookie values are stored at rest by the extension; uploads are encrypted client‑side.

---

### QA Checklist
- Verify each site returns expected auth cookies when the user is logged in.
- Verify sameSite/secure/httpOnly flags map correctly.
- Verify session cookies (no expiry) import and function in Playwright.
- Test with subdomains (e.g., `www.facebook.com`, `m.facebook.com`).
- Test regular vs incognito profiles (incognito only when explicitly enabled and targeted via `storeId`).
- Verify denial/approval paths for host permissions per site.

---

### Implementation Notes
- Manifest V3, service worker background.
- Use `chrome.cookies.getAll` with domain filters; consider multiple calls to capture subdomain variants when necessary.
- Normalize domains to include leading dot for domain cookies where appropriate.
- Provide a lightweight popup UI with a single primary action, domain toggles, and progress feedback.