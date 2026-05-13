
# Crypto Research Agent Frontend

Vite frontend for the Crypto Research Agent.

## Local Development

Start the Python FastAPI backend from the repository root first:

```bash
python -m backend.server
```

Then start the frontend:

```bash
npm install
npm run dev
```

The Vite dev server proxies `/api` to `http://127.0.0.1:8000`, so
`VITE_API_URL` may be left empty locally. To set it explicitly, copy
`.env.local.example` to `.env.local`.

## Production

Set `VITE_API_URL` to the public URL of the deployed FastAPI backend before
building:

```text
VITE_API_URL=https://andrew418-crypto-research-agent.hf.space
```

This variable is embedded at build time, so rebuild and redeploy the frontend
after changing it.
