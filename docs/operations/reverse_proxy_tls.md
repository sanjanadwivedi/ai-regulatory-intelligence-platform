# Reverse Proxy & TLS Architecture

This document outlines the recommended production architecture for routing and securing traffic to the AI-Powered Regulatory Intelligence Platform.

## Architecture Overview

```text
       Internet
          |
    [HTTPS / TLS 443]
          |
  +---------------+
  | Reverse Proxy |  (e.g., NGINX, HAProxy, AWS ALB)
  +---------------+
      /       \
  /api/*     /* (all other)
    /           \
[Backend]    [Frontend]
```

## Reverse Proxy Requirements

### 1. TLS / HTTPS Termination
- The reverse proxy must handle TLS termination.
- Obtain certificates via Let's Encrypt, AWS ACM, or an internal enterprise PKI.
- Force HTTP to HTTPS redirects (Status 301).
- **HSTS**: Enable HTTP Strict Transport Security (`Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`).

### 2. Security Headers
The reverse proxy should append the following headers to outgoing responses:
- `X-Frame-Options: DENY` (Prevent clickjacking)
- `X-Content-Type-Options: nosniff` (Prevent MIME sniffing)
- `X-XSS-Protection: 1; mode=block` (Legacy but useful XSS protection)

### 3. API Routing
- All requests starting with `/api/` must be routed to the **Backend** service on port `8000`.
- Strip the `/api/` prefix if required by the deployment (FastAPI natively expects `/api/v1` routes as configured in `config.py`).
- Pass standard proxy headers to the backend:
  ```nginx
  proxy_set_header Host $host;
  proxy_set_header X-Real-IP $remote_addr;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto $scheme;
  ```

### 4. Frontend Routing
- All other requests should route to the **Frontend** service on port `80`.
- The frontend is a React SPA, so the NGINX serving the frontend must fallback to `index.html` for 404s. This is already configured in `frontend/nginx.conf`.

### 5. Timeouts & Upload Limits
- **Timeouts**: AI generation tasks may take up to 60 seconds. Configure proxy read/write timeouts appropriately (e.g., `proxy_read_timeout 120s;`).
- **Upload Size**: Allow reasonable payload sizes for evidence uploads and Defense Pack artifacts (e.g., `client_max_body_size 50M;`).

### 6. WebSocket Support (Future Proofing)
- If WebSockets are ever introduced for live compliance alerts, the proxy must be configured to upgrade the connection:
  ```nginx
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection "upgrade";
  ```
