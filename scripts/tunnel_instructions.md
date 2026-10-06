# Safe Hosting with Cloudflare Tunnel (`cloudflared`)

A **Cloudflare Tunnel** creates an outbound-only connection from your local machine to Cloudflare's edge network. This allows autonomous AI agents and web crawlers on the public web to access your Beacon without exposing your home IP address or opening any ports on your firewall/router.

---

## Prerequisites: Quick Installation

### Option A: Install via Winget (Windows)
Open PowerShell and run:
```powershell
winget install --id Cloudflare.cloudflared
```

### Option B: Direct Download
Download the latest `cloudflared-windows-amd64.exe` from the [Cloudflare GitHub Releases](https://github.com/cloudflare/cloudflared/releases) and place it on your system PATH.

---

## Method 1: Instant Quick-Tunnel (No Cloudflare Account Needed)

This is the fastest way to get a live, public HTTPS URL for testing in 10 seconds:

1. **Start the Beacon locally:**
   ```powershell
   .\.venv\Scripts\python.exe scripts\run_local.py
   ```
2. **In a separate PowerShell window, run:**
   ```powershell
   cloudflared tunnel --url http://localhost:8000
   ```
3. Cloudflare will output a public HTTPS URL like:
   `https://random-words-123.trycloudflare.com`
4. Visiting that URL from anywhere on the web connects directly to your local Beacon through Cloudflare's edge DDoS/WAF protection.

---

## Method 2: Permanent Custom Domain Tunnel (Recommended for Production)

If you own a domain on Cloudflare (e.g. `yourdomain.com`):

1. **Log in to Cloudflare:**
   ```powershell
   cloudflared tunnel login
   ```
2. **Create a named tunnel:**
   ```powershell
   cloudflared tunnel create beacon-tunnel
   ```
3. **Route DNS to your tunnel:**
   ```powershell
   cloudflared tunnel route dns beacon-tunnel beacon.yourdomain.com
   ```
4. **Create a config file (`config.yml`):**
   ```yaml
   tunnel: <TUNNEL_UUID>
   credentials-file: C:\Users\<YourUser>\.cloudflared\<TUNNEL_UUID>.json

   ingress:
     - hostname: beacon.yourdomain.com
       service: http://localhost:8000
     - service: http_status:404
   ```
5. **Run the tunnel as a persistent service:**
   ```powershell
   cloudflared tunnel run beacon-tunnel
   ```

Now `https://beacon.yourdomain.com/llms.txt` and `https://beacon.yourdomain.com/` will be globally live with automated SSL/TLS encryption.
