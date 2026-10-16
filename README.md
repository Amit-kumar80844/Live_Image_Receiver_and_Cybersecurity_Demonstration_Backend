# Authorized Live Image Receiver

Consent-based classroom demonstration backend for registered devices to upload existing JPEG, PNG, and WebP files, with validation, local storage, SQLite metadata, and a live dashboard. Use only with explicit participant authorization.

## Windows setup

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and replace `ADMIN_TOKEN`. Start with `python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000`.

Dashboard: http://127.0.0.1:8000/dashboard  |  API docs: http://127.0.0.1:8000/docs

## Demo flow

1. In Swagger, call `POST /api/demo/register` for each device and save its returned `device_token`.
2. Call `POST /api/images/upload` as multipart fields `device_id` and `image`, with `X-Device-Token` set to that device token.
3. Enter the admin token in the dashboard. New uploads arrive through WebSockets.
4. After class, use the dashboard cleanup button or `DELETE /api/demo/cleanup?confirm=DELETE-DEMO-DATA` with `X-Admin-Token`.

PowerShell example:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/images/upload -H "X-Device-Token: DEVICE_TOKEN" -F "device_id=phone-1" -F "image=@C:\path\photo.jpg"
```

The future Android client should register once, securely store its returned token, then send each explicitly authorized image as multipart `image` plus `device_id`. Never put the admin token in the Android app.

## Security and troubleshooting

The server rejects path traversal, unsupported formats, fake signatures, oversized files, invalid dimensions, unauthenticated devices, and unauthenticated admin actions. It applies a classroom-oriented in-memory rate limit. For access beyond a trusted LAN, put Uvicorn behind an HTTPS reverse proxy, use a strong secret, restrict firewall rules, and rotate device tokens. Set `LOCAL_NETWORK_ONLY=true` as a configuration marker and restrict the Windows firewall to the private classroom subnet.

Run `pytest -q`. For 415, send a matching MIME type. For 403, use the token from the latest registration for that exact device ID. For LAN access, bind to `0.0.0.0`, use the host's LAN IP, allow port 8000 through the private Windows firewall profile, and verify both devices share the network. Keep `uploads/` and `data/` writable.
