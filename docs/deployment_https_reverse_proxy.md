# HTTPS Reverse Proxy Templates

Phase 43 adds optional reverse proxy examples only. These templates do not change `Dockerfile`, `docker-compose.yml`, CI, provider configuration, data sources, or runtime defaults.

Recommended topology:

```text
client browser
-> HTTPS reverse proxy (Nginx or Caddy)
-> HTTP uvicorn app on 127.0.0.1:8000
```

Templates:

- `deploy/nginx-https.example.conf`
- `deploy/Caddyfile.example`

Operational notes:

- Replace `rfc-rag.example.com` and certificate paths before use.
- Keep real API keys only in local `.env` or deployment secret storage.
- Forward `X-Request-ID` so Phase 43 request tracing can correlate proxy and app logs.
- Disable proxy buffering for `/agent/query/stream` if using Nginx, otherwise SSE token streaming may be delayed.
- These examples do not add Sentry, Datadog, Prometheus, Grafana, or any external monitoring SaaS.
