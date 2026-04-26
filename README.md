# VPS Relay for MasterHttpRelayVPN

<div dir="rtl">

## فارسی

یک relay سرور بهینه‌شده برای پروژه [MasterHttpRelayVPN](https://github.com/masterking32/MasterHttpRelayVPN) که ترافیک را از طریق یک VPS با IP ثابت هدایت می‌کند.

### معماری

```
کلاینت ایران
    ↓  HTTPS  (SNI: www.google.com)
Google Apps Script
    ↓  HTTP  (موازی)
VPS خارج  ←  IP ثابت
    ↓  HTTPS
اینترنت آزاد
```

### بهینه‌سازی‌ها

- **Connection Pooling** — اتصال‌های TCP را نگه می‌دارد، TCP handshake مکرر ندارد
- **Parallel Batch** — درخواست‌های batch به صورت کاملاً موازی پردازش می‌شوند
- **DNS Caching** — نتایج DNS را ۵ دقیقه کش می‌کند
- **Response Cache** — پاسخ‌های GET تکراری را ۳۰ ثانیه کش می‌کند
- **Accept-Encoding** — پاسخ‌های فشرده از مقصد دریافت می‌کند
- **Waitress WSGI** — سرور production-grade به جای Flask dev server

---

### پیش‌نیازها

- یک VPS خارج از ایران (Ubuntu/Debian)
- Python 3.8+
- یک حساب Google
- پروژه [MasterHttpRelayVPN](https://github.com/masterking32/MasterHttpRelayVPN) نصب‌شده روی سیستم کلاینت

---

### راه‌اندازی VPS

#### ۱. نصب وابستگی‌ها

```bash
sudo apt update
sudo apt install -y python3 python3-pip tmux git
pip3 install -r requirements.txt
```

#### ۲. کلون پروژه

```bash
git clone https://github.com/the0r4cle/VPS-Relay-for-MasterHttpRelayVPN
cd vps-relay
pip3 install -r requirements.txt
```

#### ۳. باز کردن پورت فایروال

```bash
sudo ufw allow 8080/tcp
sudo ufw reload
```

#### ۴. اجرا با tmux

```bash
# ساختن یک session جدید
tmux new -s relay

# داخل tmux — اجرای relay
VPS_KEY="password" python3 relay.py

# برای detach کردن (بیرون آمدن بدون بستن)
# کلیدهای Ctrl+B سپس D را بزن
```

#### مدیریت tmux

```bash
# برگشتن به session
tmux attach -t relay

# دیدن لیست session ها
tmux ls

# بستن کامل relay
tmux kill-session -t relay
```

#### متغیرهای محیطی (اختیاری)

| متغیر | پیش‌فرض | توضیح |
|-------|---------|-------|
| `VPS_KEY` | `CHANGE_ME` | **الزامی** — کلید امنیتی |
| `PORT` | `8080` | پورت سرور |
| `WORKERS` | `30` | تعداد thread های موازی |
| `TIMEOUT` | `25` | timeout درخواست‌ها (ثانیه) |
| `CACHE_MAX` | `500` | حداکثر تعداد آیتم در کش |
| `CACHE_TTL` | `30` | مدت اعتبار کش (ثانیه) |

مثال با همه متغیرها:
```bash
VPS_KEY="password" PORT=8080 WORKERS=50 CACHE_TTL=60 python3 relay.py
```

#### تست سلامت

```bash
curl http://IP_VPS:8080/health
```

باید چیزی شبیه این برگردد:
```json
{"status": "ok", "cache": 0, "dns_cache": 0, "workers": 30}
```

---

### راه‌اندازی Google Apps Script

#### ۱. ساختن پروژه

۱. به [script.google.com](https://script.google.com) برو
۲. روی **New project** کلیک کن
۳. کد پیش‌فرض را کاملاً پاک کن
۴. محتوای فایل `apps_script/Code.gs` را paste کن

#### ۲. تنظیم مقادیر

این سه مقدار را در بالای فایل عوض کن:

```javascript
const AUTH_KEY = "password1";
const VPS_URL  = "http://IP_VPS:8080/relay";
const VPS_KEY  = "password2";
```

> **توجه:** `AUTH_KEY` و `VPS_KEY` را متفاوت انتخاب کن.

#### ۳. Deploy کردن

۱. روی **Deploy** → **New deployment** کلیک کن
۲. روی آیکون ⚙️ کلیک کن → **Web app** را انتخاب کن
۳. تنظیمات:
   - **Execute as:** Me
   - **Who has access:** Anyone
۴. روی **Deploy** کلیک کن
۵. **Deployment ID** را کپی کن

#### ۴. تنظیم MasterHttpRelayVPN

فایل `config.json` پروژه MasterHttpRelayVPN را باز کن:

```json
{
  "mode": "apps_script",
  "script_ids": ["DEPLOYMENT_ID_اینجا"],
  "auth_key": "همان_AUTH_KEY",
  "listen_host": "127.0.0.1",
  "listen_port": 8085
}
```

برای سرعت بیشتر، چند Deployment ID اضافه کن:

```json
{
  "script_ids": [
    "DEPLOYMENT_ID_1",
    "DEPLOYMENT_ID_2",
    "DEPLOYMENT_ID_3"
  ]
}
```

---

### عیب‌یابی

**خطای `unauthorized`:**
مطمئن شو `VPS_KEY` در `relay.py` و `Code.gs` یکسان است.

**relay.py اجرا نمی‌شود:**
```bash
pip3 install -r requirements.txt
```

**از ایران وصل نمی‌شود:**
مطمئن شو پورت `8080` روی VPS باز است:
```bash
sudo ufw status
```

**کند است:**
چند `script_id` مختلف در `config.json` اضافه کن.

</div>

---

## English

An optimized relay server for [MasterHttpRelayVPN](https://github.com/masterking32/MasterHttpRelayVPN) that routes traffic through a VPS with a fixed outbound IP.

### Architecture

```
Client (Iran)
    ↓  HTTPS  (SNI: www.google.com)
Google Apps Script
    ↓  HTTP  (parallel)
VPS  ←  Fixed IP
    ↓  HTTPS
Open Internet
```

### Optimizations

- **Connection Pooling** — Reuses TCP connections, no repeated handshakes
- **Parallel Batch** — Batch requests processed fully concurrently
- **DNS Caching** — Caches DNS results for 5 minutes
- **Response Cache** — Caches repeated GET responses for 30 seconds
- **Accept-Encoding** — Requests compressed responses from destinations
- **Waitress WSGI** — Production-grade server instead of Flask dev server

---

### Prerequisites

- A VPS outside Iran (Ubuntu/Debian)
- Python 3.8+
- A Google account
- [MasterHttpRelayVPN](https://github.com/masterking32/MasterHttpRelayVPN) installed on the client machine

---

### VPS Setup

#### 1. Install dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-pip tmux git
```

#### 2. Clone and install

```bash
git clone https://github.com/the0r4cle/VPS-Relay-for-MasterHttpRelayVPN.git
cd vps-relay
pip3 install -r requirements.txt
```

#### 3. Open firewall port

```bash
sudo ufw allow 8080/tcp
sudo ufw reload
```

#### 4. Run with tmux

```bash
# Create a new session
tmux new -s relay

# Inside tmux — run relay
VPS_KEY="your_strong_password" python3 relay.py

# Detach (leave running in background)
# Press Ctrl+B then D
```

#### tmux cheatsheet

```bash
# Reattach to session
tmux attach -t relay

# List sessions
tmux ls

# Kill relay
tmux kill-session -t relay
```

#### Environment variables (optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `VPS_KEY` | `CHANGE_ME` | **Required** — Security key |
| `PORT` | `8080` | Server port |
| `WORKERS` | `30` | Parallel thread count |
| `TIMEOUT` | `25` | Request timeout (seconds) |
| `CACHE_MAX` | `500` | Max cache items |
| `CACHE_TTL` | `30` | Cache TTL (seconds) |

Example with all variables:
```bash
VPS_KEY="password" PORT=8080 WORKERS=50 CACHE_TTL=60 python3 relay.py
```

#### Health check

```bash
curl http://VPS_IP:8080/health
```

Expected response:
```json
{"status": "ok", "cache": 0, "dns_cache": 0, "workers": 30}
```

---

### Google Apps Script Setup

#### 1. Create a project

1. Go to [script.google.com](https://script.google.com)
2. Click **New project**
3. Delete the default code completely
4. Paste the content of `apps_script/Code.gs`

#### 2. Configure values

Change these three constants at the top of the file:

```javascript
const AUTH_KEY = "strong_password";           // Key between client and Apps Script
const VPS_URL  = "http://VPS_IP:8080/relay";  // Your VPS address
const VPS_KEY  = "another_strong_password";   // Must match VPS_KEY in relay.py
```

> **Note:** Use different values for `AUTH_KEY` and `VPS_KEY`.

#### 3. Deploy

1. Click **Deploy** → **New deployment**
2. Click the ⚙️ gear → select **Web app**
3. Settings:
   - **Execute as:** Me
   - **Who has access:** Anyone
4. Click **Deploy**
5. Copy the **Deployment ID**

#### 4. Configure MasterHttpRelayVPN

Edit `config.json` in your MasterHttpRelayVPN installation:

```json
{
  "mode": "apps_script",
  "script_ids": ["YOUR_DEPLOYMENT_ID"],
  "auth_key": "same_as_AUTH_KEY",
  "listen_host": "127.0.0.1",
  "listen_port": 8085
}
```

For better speed, add multiple Deployment IDs:

```json
{
  "script_ids": [
    "DEPLOYMENT_ID_1",
    "DEPLOYMENT_ID_2",
    "DEPLOYMENT_ID_3"
  ]
}
```

---

### Troubleshooting

**`unauthorized` error:**
Make sure `VPS_KEY` in `relay.py` and `Code.gs` are identical.

**relay.py won't start:**
```bash
pip3 install -r requirements.txt
```

**Can't connect from Iran:**
Make sure port `8080` is open on your VPS:
```bash
sudo ufw status
```

**Slow speed:**
Add multiple `script_id` entries in `config.json`.

---

### Security Notes

- Never share `VPS_KEY` or `AUTH_KEY` publicly
- Never commit `config.json` with real keys to GitHub
- Use a strong random password — at least 32 characters

---

### License

MIT
