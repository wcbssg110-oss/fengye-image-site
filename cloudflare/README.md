# Cloudflare Worker deployment

The Worker exposes the existing GMI video and image features at `/api/gmi-video` and `/api/gmi-image`. Visitors can provide their own GMI API key in the video canvas; the browser sends it directly to this Worker over HTTPS, which forwards it to GMI. The key is kept in the current browser tab's session storage and is never written into the site source or repository. The optional server-held key plus site access password remains available as a fallback.

## Deploy

1. In Cloudflare, open **Workers & Pages → Create application → Import a repository** and connect `wcbssg110-oss/fengye-image-site`.
2. Use the Worker name `fengye-image-api`. The repository root contains `wrangler.toml`, which points to `cloudflare/worker.js`.
3. Optional fallback: add these under the Worker’s **Settings → Variables and Secrets** as encrypted **Secrets**:
   - `GMI_API_KEY`: the GMI Cloud API key.
   - `SITE_ACCESS_PASSWORD`: a strong password of at least 16 characters for the fallback shared-key flow.
4. Deploy the Worker. Copy its `workers.dev` URL into `window.FENGYE_GMI_WORKER_URL` near the top of the main script in `index.html`, without a trailing slash.
5. Publish the updated `index.html` to GitHub Pages.

With per-user keys, each visitor pastes their own GMI Cloud key into the video canvas and saves it for the current tab. Requests using that key are billed to that visitor's GMI account. Never put provider keys in `index.html`, commit them, or send them in chat. If a visitor does not supply a personal key, the Worker can use the optional server key after the shared access password is entered.

The Worker allows browser requests only from `https://wcbssg110-oss.github.io`. CORS is a browser safeguard, not authentication; GMI validates personal API keys, while the fallback shared key requires the site password.
