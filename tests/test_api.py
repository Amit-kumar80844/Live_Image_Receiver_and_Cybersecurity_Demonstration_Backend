import io
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

def image_bytes(fmt="PNG"):
    out = io.BytesIO(); Image.new("RGB", (20, 20), (20, 180, 140)).save(out, format=fmt); return out.getvalue()

def test_upload_and_stats(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")
    monkeypatch.setattr(settings, "admin_token", "admin")
    with TestClient(app) as c:
        reg = c.post('/api/demo/register', json={'device_id':'phone-test-1','name':'Phone 1'}); assert reg.status_code == 200
        tok = reg.json()['device_token']
        r = c.post('/api/images/upload', headers={'X-Device-Token':tok}, data={'device_id':'phone-test-1'}, files={'image':('x.png',image_bytes(),'image/png')})
        assert r.status_code == 201
        assert c.get('/api/dashboard/stats', headers={'X-Admin-Token':'admin'}).json()['total_images'] >= 1

def test_invalid_and_impersonation():
    with TestClient(app) as c:
        reg = c.post('/api/demo/register', json={'device_id':'phone-test-2','name':'Phone 2'}); tok = reg.json()['device_token']
        assert c.post('/api/images/upload', headers={'X-Device-Token':tok}, data={'device_id':'other'}, files={'image':('x.png',image_bytes(),'image/png')}).status_code == 403
        assert c.post('/api/images/upload', headers={'X-Device-Token':tok}, data={'device_id':'phone-test-2'}, files={'image':('x.png',b'not image','image/png')}).status_code == 400

def test_admin_required():
    with TestClient(app) as c: assert c.get('/api/dashboard/stats').status_code == 401
