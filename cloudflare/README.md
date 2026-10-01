# Cloudflare Worker deployment

The Worker exposes GMI video and image features at `/api/gmi-video` and `/api/gmi-image`, plus image-based prompt analysis at `/api/openai-prompt`. Visitors can provide their own GMI and OpenAI API keys in the video canvas; each key is sent to this Worker over HTTPS only for its provider request. Keys are kept in the current browser tab's session storage and are never written into the site source or repository. The optional server-held GMI key plus site access password remains available as a fallback.

## Deploy

1. In Cloudflare, open **Workers & Pages → Create application → Import a repository** and connect `wcbssg110-oss/fengye-image-site`.
2. Use the Worker name `fengye-image-api`. The repository root contains `wrangler.toml`, which points to `cloudflare/worker.js`.
3. Optional fallback: add these under the Worker’s **Settings → Variables and Secrets** as encrypted **Secrets**:
   - `GMI_API_KEY`: the GMI Cloud API key.
   - `SITE_ACCESS_PASSWORD`: a strong password of at least 16 characters for the fallback shared-key flow.
4. Deploy the Worker. Copy its `workers.dev` URL into `window.FENGYE_GMI_WORKER_URL` near the top of the main script in `index.html`, without a trailing slash.
5. Publish the updated `index.html` to GitHub Pages.

Each visitor pastes their own GMI Cloud key and OpenAI API key into the video canvas and saves them for the current tab. Video requests use GMI; ChatGPT prompt analysis uses OpenAI Responses with `gpt-5-mini` and the selected reference images. Charges go to the visitor's respective accounts. Never put provider keys in `index.html`, commit them, or send them in chat. If a visitor does not supply a personal GMI key, the Worker can use the optional server key after the shared access password is entered.

The Worker allows browser requests from `https://wcbssg110-oss.github.io` and the local origins `http://127.0.0.1:8791` / `http://localhost:8791`. CORS is a browser safeguard, not authentication; each provider validates its personal API key, while the fallback GMI key requires the site password.
