# Production Deployment Guide — ClipMind v1.0

Follow this guide to deploy ClipMind on cloud servers or VMs (e.g. AWS, GCP, Azure, DigitalOcean) for production operations.

---

## 🔒 1. Production Security Hardening

Before deploying, ensure you configure the following settings in your production `.env` file:

1. **Set Production Mode**:
   ```ini
   APP_ENV=production
   ```
2. **Encryption Key**:
   Generate a unique 32-byte Fernet key. **Never leave this empty in production**.
   ```bash
   python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
   Set it in your environment:
   ```ini
   ENCRYPTION_KEY=your_generated_key_here
   ```
3. **CORS Origins**:
   Restrict `ALLOWED_ORIGINS` to your registered production domains only. Do not include development or testing urls:
   ```ini
   ALLOWED_ORIGINS=https://app.clipmind.com
   ```
4. **HTTPS Enforcement**:
   Ensure you terminate SSL/TLS at your load balancer/reverse proxy (e.g., Nginx, Caddy, Cloudflare) and set:
   ```ini
   ENFORCE_HTTPS=true
   ```

---

## 🐳 2. Deployment via Docker Compose (Recommended)

Docker Compose is the recommended deployment method because it containerizes all dependencies (including FFmpeg) and runs health checks.

1. **Clone and Navigate**:
   ```bash
   git clone https://github.com/AnilSami/AntiGravity.git
   cd AntiGravity
   ```
2. **Set Up Production Environment**:
   Copy `.env.example` to `backend/.env` and fill in all values.
3. **Boot the Container**:
   Run the production startup script:
   ```bash
   ./start_production.sh
   ```
   Alternatively:
   ```bash
   docker compose up -d --build
   ```
4. **Proxy configuration (Nginx Example)**:
   Add Nginx proxy forwarding for port 8000:
   ```nginx
   server {
       listen 80;
       server_name app.clipmind.com;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

---

## 🗄️ 3. Persistent Volumes & Database

ClipMind stores SQLite database files and downloaded video assets.
Ensure that the `output/` directory is mounted on a persistent volume so database tables, download caches, and finished clips survive container updates:
```yaml
    volumes:
      - /var/lib/clipmind/output:/app/backend/output
```
