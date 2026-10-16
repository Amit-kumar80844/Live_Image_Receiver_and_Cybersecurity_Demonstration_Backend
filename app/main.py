import ipaddress
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.config import settings
from app.database import Base, engine, get_db
from app.models import Device, ImageRecord
from app.schemas import DeviceRegister, ImageOut
from app.security import hash_token, new_token, require_admin, require_device
from app.storage import read_and_validate, remove_image, save_image

Base.metadata.create_all(bind=engine)
app = FastAPI(title=settings.app_name, version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_methods=["*"], allow_headers=["*"])
events: set[WebSocket] = set(); rate_log: dict[str, deque] = defaultdict(deque)
ALLOWED_MIME = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}

@app.middleware("http")
async def local_network_guard(request: Request, call_next):
    if settings.local_network_only and request.client:
        try: allowed = ipaddress.ip_address(request.client.host).is_private or ipaddress.ip_address(request.client.host).is_loopback
        except ValueError: allowed = False
        if not allowed: raise HTTPException(403, "This server is restricted to the local network")
    return await call_next(request)

def rate_limit(key):
    now = datetime.now(timezone.utc).timestamp(); q = rate_log[key]
    while q and now - q[0] > 60: q.popleft()
    if len(q) >= 60: raise HTTPException(429, "Too many requests; try again shortly")
    q.append(now)

async def broadcast(event):
    stale = []
    for ws in events:
        try: await ws.send_json(event)
        except Exception: stale.append(ws)
    for ws in stale: events.discard(ws)

@app.get("/", response_class=HTMLResponse)
def root(): return HTMLResponse('<a href="/dashboard">Open the image management dashboard</a>')
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(): return HTMLResponse((Path(__file__).parent / "templates" / "dashboard.html").read_text(encoding="utf-8"))
@app.get("/static/dashboard.css")
def css(): return FileResponse(Path(__file__).parent / "static" / "dashboard.css", media_type="text/css")
@app.get("/static/dashboard.js")
def js(): return FileResponse(Path(__file__).parent / "static" / "dashboard.js", media_type="text/javascript")
@app.get("/api/health")
def health(): return {"status": "ok", "time": datetime.now(timezone.utc)}

@app.post("/api/demo/register")
def register(payload: DeviceRegister, db: Session = Depends(get_db)):
    token = new_token(); device = db.query(Device).filter(Device.device_id == payload.device_id).first()
    if device: device.name, device.token_hash = payload.name, hash_token(token)
    else: db.add(Device(device_id=payload.device_id, name=payload.name, token_hash=hash_token(token)))
    db.commit(); return {"status": "registered", "device_id": payload.device_id, "device_token": token, "warning": "Store this token securely; it is shown only now."}

@app.post("/api/images/upload", status_code=201)
async def upload_image(device_id: str = Form(...), image: UploadFile = File(...), x_device_token: str | None = Header(default=None), db: Session = Depends(get_db)):
    rate_limit(device_id); device = require_device(db, x_device_token, device_id); data, parsed, fmt, suffix = await read_and_validate(image)
    stored = save_image(data, suffix)
    record = ImageRecord(device_id=device.device_id, original_filename=(image.filename or "image")[:255], stored_filename=stored, image_format=fmt, mime_type=ALLOWED_MIME[fmt], file_size=len(data), width=parsed.width, height=parsed.height)
    device.last_seen_at = datetime.now(timezone.utc); db.add(record); db.commit(); db.refresh(record)
    await broadcast({"type": "image_uploaded", "image": ImageOut.model_validate(record).model_dump(mode="json")})
    return {"status": "uploaded", "image_id": record.id, "filename": record.original_filename}

@app.get("/api/images")
def list_images(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), device_id: str | None = None, search: str | None = None, db: Session = Depends(get_db)):
    q = db.query(ImageRecord)
    if device_id: q = q.filter(ImageRecord.device_id == device_id)
    if search: q = q.filter(ImageRecord.original_filename.ilike(f"%{search[:80]}%"))
    total = q.count(); rows = q.order_by(ImageRecord.uploaded_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [ImageOut.model_validate(x) for x in rows], "page": page, "page_size": page_size, "total": total, "pages": (total + page_size - 1) // page_size}

@app.get("/api/images/{image_id}", response_model=ImageOut)
def get_image(image_id: int, db: Session = Depends(get_db)):
    row = db.get(ImageRecord, image_id)
    if not row: raise HTTPException(404, "Image not found")
    return row
@app.get("/api/images/{image_id}/file")
def image_file(image_id: int, db: Session = Depends(get_db)):
    row = db.get(ImageRecord, image_id)
    if not row: raise HTTPException(404, "Image not found")
    path = settings.upload_dir / row.stored_filename
    if not path.is_file(): raise HTTPException(404, "Stored file not found")
    return FileResponse(path, media_type=row.mime_type, filename=row.original_filename)
@app.delete("/api/images/{image_id}")
def delete_image(image_id: int, _: None = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.get(ImageRecord, image_id)
    if not row: raise HTTPException(404, "Image not found")
    remove_image(row.stored_filename); db.delete(row); db.commit(); return {"status": "deleted", "image_id": image_id}

@app.get("/api/dashboard/stats")
def stats(_: None = Depends(require_admin), db: Session = Depends(get_db)):
    count, storage, latest = db.query(func.count(ImageRecord.id), func.coalesce(func.sum(ImageRecord.file_size), 0), func.max(ImageRecord.uploaded_at)).one()
    return {"total_images": count, "total_devices": db.query(func.count(Device.id)).scalar(), "storage_bytes": storage, "latest_upload": latest}
@app.get("/api/dashboard/devices")
def devices(_: None = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(ImageRecord.device_id, func.count(ImageRecord.id), func.coalesce(func.sum(ImageRecord.file_size), 0)).group_by(ImageRecord.device_id).all()
    return [{"device_id": did, "image_count": count, "storage_bytes": size} for did, count, size in rows]
@app.delete("/api/demo/cleanup")
def cleanup(confirm: str = Query(...), _: None = Depends(require_admin), db: Session = Depends(get_db)):
    if confirm != "DELETE-DEMO-DATA": raise HTTPException(400, "Confirmation must be DELETE-DEMO-DATA")
    rows = db.query(ImageRecord).all()
    for row in rows: remove_image(row.stored_filename)
    deleted = len(rows); db.query(ImageRecord).delete(); db.commit(); return {"status": "cleaned", "deleted_images": deleted}
@app.websocket("/ws/updates")
async def updates(ws: WebSocket):
    await ws.accept(); events.add(ws)
    try:
        while True: await ws.receive_text()
    except WebSocketDisconnect: events.discard(ws)
