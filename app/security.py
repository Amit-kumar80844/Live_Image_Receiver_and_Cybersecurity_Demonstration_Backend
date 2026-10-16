import hashlib, hmac, secrets
from fastapi import Header, HTTPException
from sqlalchemy.orm import Session
from app.config import settings
from app.models import Device
def hash_token(token): return hashlib.sha256(token.encode()).hexdigest()
def new_token(): return secrets.token_urlsafe(32)
def require_admin(x_admin_token: str | None = Header(default=None)):
    if not x_admin_token or not hmac.compare_digest(x_admin_token, settings.admin_token): raise HTTPException(401, "Administrator authentication required")
def require_device(db: Session, token, claimed_device_id):
    if not token: raise HTTPException(401, "Device authentication required")
    device = db.query(Device).filter(Device.device_id == claimed_device_id).first()
    if not device or not hmac.compare_digest(device.token_hash, hash_token(token)): raise HTTPException(403, "Invalid device credentials")
    return device
