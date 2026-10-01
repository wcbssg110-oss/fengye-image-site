# Cloudflare Worker deployment

The Worker exposes the existing GMI video and image features at `/api/gmi-video` and `/api/gmi-image`. The GMI API key stays in Cloudflare and is never sent to the browser. Requests also require a shared site access password.

## Deploy

1. In Cloudflare, open **Workers & Pages → Create application → Import a repository** and connect `wcbssg110-oss/fengye-image-site`.
2. Use the Worker name `fengye-image-api`. The repository root contains `wrangler.toml`, which points to `cloudflare/worker.js`.
3. Add these under the Worker’s **Settings → Variables and Secrets** as encrypted **Secrets**:
   - `GMI_API_KEY`: the GMI Cloud API key.
   - `SITE_ACCESS_PASSWORD`: a strong password of at least 16 characters to share only with intended users.
4. Deploy the Worker. Copy its `workers.dev` URL into `window.FENGYE_GMI_WORKER_URL` near the top of the main script in `index.html`, without a trailing slash.
5. Publish the updated `index.html` to GitHub Pages.

The visitor enters the shared access password on the first generation request in each browser tab. It is kept in that tab’s session storage. Do not put either secret in `index.html`, commit them, or send them in chat. Every successful generation spends from the GMI account attached to `GMI_API_KEY`.

The Worker allows browser requests only from `https://wcbssg110-oss.github.io`. CORS is a browser safeguard, not authentication; the shared password is required independently.
