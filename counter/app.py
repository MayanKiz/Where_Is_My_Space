"""Local control portal for the on-premise counter.

Runs on the institute's own machine. IT logs in here, enters camera details
(which are stored encrypted on THIS machine only), and starts the counters.
Only the resulting people-counts are sent to the cloud dashboard.

Run:  python app.py      then open http://127.0.0.1:8900
"""

import re
import time
import hmac
import html
import threading
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from starlette.middleware.sessions import SessionMiddleware

import json

import store
from config import get_settings
from counter_engine import manager, get_outbound

settings = get_settings()

@asynccontextmanager
async def _lifespan(_app):
    # Resume whatever was running before the last shutdown — "set and forget".
    manager.start_all([c for c in store.load_cameras() if c.get("enabled")])
    yield
    manager.stop_all()


app = FastAPI(title="Library Counter — Local Portal", lifespan=_lifespan)
# same_site="strict" blocks cross-site form POSTs (CSRF); session expires after max_age.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    same_site="strict",
    max_age=settings.SESSION_MAX_AGE,
)

_CAMERA_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# ── in-memory login throttle (per client IP) ─────────────────────────────────
_login_fails: dict[str, tuple[int, float]] = {}
_login_lock = threading.Lock()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _lockout_remaining(ip: str) -> int:
    with _login_lock:
        entry = _login_fails.get(ip)
        if not entry:
            return 0
        count, first_ts = entry
        if count < settings.LOGIN_MAX_ATTEMPTS:
            return 0
        elapsed = time.time() - first_ts
        if elapsed >= settings.LOGIN_LOCKOUT_SECONDS:
            _login_fails.pop(ip, None)
            return 0
        return int(settings.LOGIN_LOCKOUT_SECONDS - elapsed)


def _record_fail(ip: str) -> None:
    with _login_lock:
        count, first_ts = _login_fails.get(ip, (0, time.time()))
        # reset the window if the previous lockout has fully elapsed
        if time.time() - first_ts >= settings.LOGIN_LOCKOUT_SECONDS:
            count, first_ts = 0, time.time()
        _login_fails[ip] = (count + 1, first_ts)


def _clear_fails(ip: str) -> None:
    with _login_lock:
        _login_fails.pop(ip, None)


# ── auth helpers ─────────────────────────────────────────────────────────────
def _logged_in(request: Request) -> bool:
    return bool(request.session.get("user"))


def _current_email() -> str:
    auth = store.load_auth()
    return auth["email"] if auth else settings.PORTAL_EMAIL.strip().lower()


# The example password is published in the repo, so it never counts as "set".
_PLACEHOLDER_PASSWORDS = {"", "change-this-to-a-strong-password"}


def _env_password_usable() -> bool:
    pw = settings.PORTAL_PASSWORD
    return pw not in _PLACEHOLDER_PASSWORDS and len(pw) >= 8


def setup_problems() -> list[str]:
    """Config mistakes that block login or sending; shown at startup and on the login page."""
    problems = []
    if store.load_auth() is None and not _env_password_usable():
        problems.append("PORTAL_PASSWORD in .env is missing, still the example value, "
                        "or shorter than 8 characters. Set your own and restart.")
    if not settings.DEVICE_API_KEY:
        problems.append("DEVICE_API_KEY in .env is empty. Paste the key you were given and restart.")
    return problems


def _check_credentials(email: str, password: str) -> bool:
    # If the admin has changed their credentials in the portal, use those.
    if store.load_auth() is not None:
        return store.verify_auth(email, password)
    # Otherwise fall back to the initial credentials from .env.
    if not _env_password_usable():
        return False
    email_ok = hmac.compare_digest(
        email.strip().lower(), settings.PORTAL_EMAIL.strip().lower()
    )
    pass_ok = hmac.compare_digest(password, settings.PORTAL_PASSWORD)
    return email_ok and pass_ok


# ── HTML building blocks ─────────────────────────────────────────────────────
def _page(title: str, body: str) -> str:
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
  :root {{ --ink:#1c2433; --muted:#5a6b72; --line:#dde5e4; --card:#fff;
    --paper:#f3f7f6; --teal:#028090; --mint:#02c39a; --green:#2e7d5b; --red:#bd3f2c; --amber:#b57608; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--paper); color:var(--ink);
    font-family:"Segoe UI",system-ui,sans-serif; font-size:15px; line-height:1.5; }}
  .wrap {{ max-width:960px; margin:0 auto; padding:24px 16px 60px; }}
  header.bar {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:20px; }}
  h1 {{ font-size:1.5rem; margin:0; }}
  h2 {{ font-size:1.1rem; margin:26px 0 10px; }}
  .muted {{ color:var(--muted); }}
  a {{ color:var(--teal); }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:18px 20px; margin-bottom:16px; }}
  .btn {{ display:inline-block; border:none; border-radius:8px; padding:9px 16px; font-size:.95rem;
    font-weight:600; cursor:pointer; background:var(--teal); color:#fff; text-decoration:none; }}
  .btn.ghost {{ background:transparent; color:var(--teal); border:1px solid var(--teal); }}
  .btn.danger {{ background:var(--red); }}
  .btn.gray {{ background:#64748b; }}
  .btn.sm {{ padding:5px 11px; font-size:.82rem; }}
  input,select {{ width:100%; padding:9px 11px; border:1px solid var(--line); border-radius:8px; font-size:.95rem; background:#fff; color:var(--ink); }}
  label {{ display:block; font-size:.8rem; font-weight:600; color:var(--muted); margin:10px 0 4px; }}
  table {{ width:100%; border-collapse:collapse; }}
  th,td {{ text-align:left; padding:9px 8px; border-bottom:1px solid var(--line); font-size:.9rem; vertical-align:middle; }}
  th {{ font-size:.72rem; letter-spacing:.05em; text-transform:uppercase; color:var(--muted); }}
  .pill {{ display:inline-block; padding:2px 10px; border-radius:999px; font-size:.75rem; font-weight:700; }}
  .pill.on {{ background:#e3f1e9; color:var(--green); }}
  .pill.off {{ background:#f1f3f4; color:var(--muted); }}
  .pill.err {{ background:#f6e2dd; color:var(--red); }}
  .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:0 16px; }}
  @media (max-width:640px){{ .grid2 {{ grid-template-columns:1fr; }} }}
  .banner {{ background:#fdf3e3; border:1px solid var(--amber); color:#7a5600; border-radius:10px; padding:12px 16px; margin-bottom:16px; font-size:.9rem; }}
  .row-actions {{ display:flex; gap:6px; flex-wrap:wrap; }}
  code {{ background:var(--paper); border:1px solid var(--line); border-radius:4px; padding:1px 5px; font-size:.85em; }}
</style></head><body><div class="wrap">{body}</div></body></html>"""


def _message_page(title: str, message: str, status: int = 400) -> HTMLResponse:
    body = f"""<header class="bar"><h1>{html.escape(title)}</h1></header>
      <div class="card"><p>{html.escape(message)}</p>
      <a class="btn" href="/">Back to dashboard</a></div>"""
    return HTMLResponse(_page(title, body), status_code=status)


def _login_page(error: str = "") -> str:
    err = f'<p style="color:var(--red);font-size:.9rem;margin:8px 0 0">{html.escape(error)}</p>' if error else ""
    err += "".join(f'<div class="banner">Setup needed: {html.escape(p)}</div>' for p in setup_problems())
    return _page("Counter — Login", f"""
      <header class="bar"><h1>Library Counter</h1></header>
      <div class="card" style="max-width:420px;margin:40px auto">
        <h2 style="margin-top:0">IT Sign-in</h2>
        <p class="muted" style="font-size:.9rem">This portal runs only on this machine. Sign in with the institute IT credentials.</p>
        <form method="post" action="/login">
          <label>IT Email</label>
          <input name="email" type="email" autocomplete="username" required>
          <label>Password</label>
          <input name="password" type="password" autocomplete="current-password" required>
          {err}
          <div style="margin-top:16px"><button class="btn" type="submit">Sign in</button></div>
        </form>
      </div>""")


def _camera_form(cam: dict | None = None) -> str:
    c = cam or {}
    editing = cam is not None
    val = lambda k, d="": html.escape(str(c.get(k, d)))
    stype = c.get("source_type", "rtsp")
    sel = lambda t: "selected" if stype == t else ""
    chk = "checked" if c.get("detect_reserved", True) else ""
    title = "Edit camera" if editing else "Add a camera"
    id_field = (f'<input name="camera_id" type="hidden" value="{val("camera_id")}">'
                f'<p class="muted" style="font-size:.85rem">Camera ID: <code>{val("camera_id")}</code> (fixed)</p>'
                if editing else
                '<label>Camera ID <span class="muted">(must match the zone\'s camera_id in the cloud admin)</span></label>'
                '<input name="camera_id" placeholder="cam_02" pattern="[A-Za-z0-9_\\-]+" '
                'title="Letters, numbers, - and _ only (no spaces)" required>')
    mode_field = f'<input type="hidden" name="mode" value="{"edit" if editing else "new"}">'
    return f"""
      <div class="card">
        <h2 style="margin-top:0">{title}</h2>
        <form method="post" action="/cameras/save">
          {mode_field}
          {id_field}
          <div class="grid2">
            <div><label>Zone name</label><input name="zone_name" value="{val('zone_name')}" placeholder="Main Reading Hall" required></div>
            <div><label>Source type</label>
              <select name="source_type" onchange="srcToggle(this.value)" id="stype">
                <option value="rtsp" {sel('rtsp')}>IP / CCTV camera (RTSP)</option>
                <option value="webcam" {sel('webcam')}>USB / built-in webcam</option>
                <option value="test" {sel('test')}>Test (no camera — demo numbers)</option>
              </select>
            </div>
          </div>
          <div id="rtsp-fields">
            <label>Camera address <span class="muted">(host:port/path — no need to type rtsp://)</span></label>
            <input name="host_path" value="{val('host_path')}" placeholder="192.168.1.50:554/Streaming/Channels/101">
            <div class="grid2">
              <div><label>Username</label><input name="username" value="{val('username')}" autocomplete="off"></div>
              <div><label>Password</label><input name="password" type="password" value="{val('password')}" autocomplete="off"></div>
            </div>
          </div>
          <div id="webcam-fields" style="display:none">
            <label>Webcam index</label><input name="webcam_index" value="{val('webcam_index','0')}" placeholder="0">
          </div>
          <label style="display:flex;align-items:center;gap:8px;margin-top:14px;font-weight:600">
            <input type="checkbox" name="detect_reserved" value="1" {chk} style="width:auto"> Detect reserved-but-empty seats (laptop left on a seat)
          </label>
          <div style="margin-top:16px;display:flex;gap:8px">
            <button class="btn" type="submit">{'Save changes' if editing else 'Add camera'}</button>
            {'<a class="btn ghost" href="/">Cancel</a>' if editing else ''}
          </div>
        </form>
      </div>
      <script>
        function srcToggle(v){{
          document.getElementById('rtsp-fields').style.display   = (v==='rtsp')   ? 'block':'none';
          document.getElementById('webcam-fields').style.display = (v==='webcam') ? 'block':'none';
        }}
        srcToggle(document.getElementById('stype').value);
      </script>"""


def _dashboard(request: Request) -> str:
    cams = store.load_cameras()
    warnings = []
    warnings.extend(html.escape(p) for p in setup_problems())
    banner = "".join(f'<div class="banner">⚠️ {w}</div>' for w in warnings)

    rows = ""
    if not cams:
        rows = '<tr><td colspan="5" class="muted" style="padding:20px">No cameras yet. Add one below.</td></tr>'
    for c in cams:
        cid = c["camera_id"]
        running = manager.is_running(cid)
        state = '<span class="pill on">RUNNING</span>' if running else '<span class="pill off">stopped</span>'
        src = {"rtsp": "IP / CCTV", "webcam": "Webcam", "test": "Test"}.get(c.get("source_type"), c.get("source_type"))
        toggle_label = "Stop" if running else "Start"
        toggle_cls = "danger" if running else ""
        rows += f"""<tr>
          <td><b>{html.escape(c.get('zone_name',''))}</b><br><span class="muted">{html.escape(cid)}</span></td>
          <td>{src}</td>
          <td>{state}</td>
          <td id="live-{html.escape(cid)}" class="muted">—</td>
          <td><div class="row-actions">
            <form method="post" action="/cameras/toggle" style="display:inline"><input type="hidden" name="camera_id" value="{html.escape(cid)}">
              <button class="btn sm {toggle_cls}" type="submit">{toggle_label}</button></form>
            <a class="btn sm ghost" href="/cameras/edit?id={html.escape(cid)}">Edit</a>
            <form method="post" action="/cameras/delete" style="display:inline" onsubmit="return confirm('Delete this camera?')">
              <input type="hidden" name="camera_id" value="{html.escape(cid)}">
              <button class="btn sm gray" type="submit">Delete</button></form>
          </div></td></tr>"""

    controls = ""
    if cams:
        controls = """<div style="display:flex;gap:8px;margin:12px 0">
          <form method="post" action="/start-all"><button class="btn" type="submit">Start all</button></form>
          <form method="post" action="/stop-all"><button class="btn gray" type="submit">Stop all</button></form></div>"""

    return _page("Counter — Dashboard", f"""
      <header class="bar">
        <h1>Library Counter <span class="muted" style="font-size:.9rem">· local portal</span></h1>
        <div style="display:flex;gap:8px">
          <a class="btn ghost sm" href="/outbound">What leaves this machine</a>
          <a class="btn ghost sm" href="/account">Account</a>
          <a class="btn ghost sm" href="/logout">Sign out</a>
        </div>
      </header>
      {banner}
      <div class="card">
        <h2 style="margin-top:0">Cameras &amp; live status</h2>
        <p class="muted" style="font-size:.9rem">Counts update every {settings.INFERENCE_INTERVAL}s. Only the number is sent to <code>{html.escape(settings.BACKEND_URL)}</code> — never any video.</p>
        {controls}
        <table>
          <thead><tr><th>Zone</th><th>Source</th><th>State</th><th>Live count</th><th>Actions</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
      {_camera_form()}
      <script>
        async function refresh(){{
          try {{
            const r = await fetch('/api/status'); const s = await r.json();
            for (const [cid, st] of Object.entries(s)) {{
              const el = document.getElementById('live-'+cid); if(!el) continue;
              if (st.last_count === null) {{ el.textContent = st.error || 'starting…'; continue; }}
              let txt = st.last_count + ' people';
              if (st.last_reserved) txt += ' · ' + st.last_reserved + ' reserved';
              txt += '  (' + (st.last_update||'') + ')';
              if (st.last_post_ok === false) txt += ' ⚠ send failed';
              el.textContent = txt;
              el.style.color = st.last_post_ok === false ? 'var(--red)' : 'var(--ink)';
            }}
          }} catch(e) {{}}
        }}
        refresh(); setInterval(refresh, 3000);
      </script>""")


# ── routes ───────────────────────────────────────────────────────────────────
@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if _logged_in(request):
        return RedirectResponse("/", status_code=303)
    return HTMLResponse(_login_page())


@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    ip = _client_ip(request)
    remaining = _lockout_remaining(ip)
    if remaining:
        mins = (remaining + 59) // 60
        return HTMLResponse(
            _login_page(f"Too many attempts. Try again in about {mins} minute(s)."),
            status_code=429,
        )
    if _check_credentials(email, password):
        _clear_fails(ip)
        request.session["user"] = email.strip().lower()
        return RedirectResponse("/", status_code=303)
    _record_fail(ip)
    return HTMLResponse(_login_page("Incorrect email or password."), status_code=401)


def _account_page(current_email: str, msg: str = "", ok: bool = False) -> str:
    note = ""
    if msg:
        color = "var(--green)" if ok else "var(--red)"
        note = f'<p style="color:{color};font-size:.9rem;margin:0 0 10px">{html.escape(msg)}</p>'
    return _page("Counter — Account", f"""
      <header class="bar"><h1>Account</h1><a class="btn ghost sm" href="/">Back</a></header>
      <div class="card" style="max-width:480px">
        <h2 style="margin-top:0">Change login credentials</h2>
        <p class="muted" style="font-size:.9rem">Current email: <code>{html.escape(current_email)}</code></p>
        {note}
        <form method="post" action="/account">
          <label>Current password</label>
          <input name="current_password" type="password" autocomplete="current-password" required>
          <label>New email <span class="muted">(leave as-is to keep)</span></label>
          <input name="new_email" type="email" value="{html.escape(current_email)}" required>
          <label>New password <span class="muted">(min 8 characters)</span></label>
          <input name="new_password" type="password" autocomplete="new-password" required>
          <label>Confirm new password</label>
          <input name="confirm_password" type="password" autocomplete="new-password" required>
          <div style="margin-top:16px"><button class="btn" type="submit">Update credentials</button></div>
        </form>
      </div>""")


@app.get("/outbound", response_class=HTMLResponse)
def outbound_page(request: Request):
    if not _logged_in(request):
        return RedirectResponse("/login", status_code=303)
    rows = ""
    for e in get_outbound(60):
        state = '<span class="pill on">sent</span>' if e["ok"] else '<span class="pill err">failed</span>'
        payload = html.escape(json.dumps(e["body"]))
        rows += (f'<tr><td class="muted">{html.escape(e["at"])}</td><td>{state}</td>'
                 f'<td><code>{payload}</code></td><td class="muted">{html.escape(e["detail"])}</td></tr>')
    if not rows:
        rows = '<tr><td colspan="4" class="muted" style="padding:20px">Nothing sent yet. Start a camera to see the outgoing numbers here.</td></tr>'
    body = f"""
      <header class="bar"><h1>What leaves this machine</h1><a class="btn ghost sm" href="/">Back</a></header>
      <div class="card">
        <p class="muted" style="margin-top:0">This is the <strong>complete</strong> list of everything this computer sends to the cloud — the exact messages, newest first. Each one carries only a count. <strong>No image or video is ever sent.</strong></p>
        <table>
          <thead><tr><th>Time</th><th>Status</th><th>Exact message sent</th><th>Result</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
      <p class="muted" style="font-size:.85rem">Showing the most recent 60 messages. Refresh to update.</p>"""
    return HTMLResponse(_page("What leaves this machine", body))


@app.get("/account", response_class=HTMLResponse)
def account_page(request: Request):
    if not _logged_in(request):
        return RedirectResponse("/login", status_code=303)
    return HTMLResponse(_account_page(_current_email()))


@app.post("/account", response_class=HTMLResponse)
def account_update(
    request: Request,
    current_password: str = Form(...),
    new_email: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    if not _logged_in(request):
        return RedirectResponse("/login", status_code=303)
    current_email = _current_email()
    if not _check_credentials(current_email, current_password):
        return HTMLResponse(_account_page(current_email, "Current password is incorrect."), status_code=401)
    new_email = new_email.strip().lower()
    if "@" not in new_email or "." not in new_email:
        return HTMLResponse(_account_page(current_email, "Please enter a valid email."), status_code=400)
    if len(new_password) < 8:
        return HTMLResponse(_account_page(current_email, "New password must be at least 8 characters."), status_code=400)
    if new_password != confirm_password:
        return HTMLResponse(_account_page(current_email, "New passwords do not match."), status_code=400)
    store.save_auth(new_email, new_password)
    request.session["user"] = new_email   # keep the session valid under the new email
    return HTMLResponse(_account_page(new_email, "Credentials updated.", ok=True))


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    if not _logged_in(request):
        return RedirectResponse("/login", status_code=303)
    return HTMLResponse(_dashboard(request))


@app.get("/cameras/edit", response_class=HTMLResponse)
def edit_camera(request: Request, id: str):
    if not _logged_in(request):
        return RedirectResponse("/login", status_code=303)
    cam = store.get_camera(id)
    if not cam:
        return RedirectResponse("/", status_code=303)
    body = f'<header class="bar"><h1>Edit camera</h1><a class="btn ghost sm" href="/">Back</a></header>{_camera_form(cam)}'
    return HTMLResponse(_page("Edit camera", body))


@app.post("/cameras/save")
def save_camera(
    request: Request,
    camera_id: str = Form(...),
    zone_name: str = Form(...),
    mode: str = Form("new"),
    source_type: str = Form("rtsp"),
    host_path: str = Form(""),
    username: str = Form(""),
    password: str = Form(""),
    webcam_index: str = Form("0"),
    detect_reserved: str = Form(None),
):
    if not _logged_in(request):
        return RedirectResponse("/login", status_code=303)

    camera_id = camera_id.strip()
    zone_name = zone_name.strip()
    if not _CAMERA_ID_RE.match(camera_id):
        return _message_page("Invalid Camera ID",
            "Camera ID may contain only letters, numbers, dashes and underscores (max 64).")
    if not zone_name:
        return _message_page("Missing zone name", "Please enter a zone name.")
    if source_type not in ("rtsp", "webcam", "test"):
        return _message_page("Invalid source", "Unknown source type.")
    if source_type == "rtsp" and not host_path.strip():
        return _message_page("Missing camera address", "Enter the camera's host:port/path.")

    existing = store.get_camera(camera_id)
    if mode == "new" and existing is not None:
        return _message_page("Camera ID already exists",
            f"A camera with ID '{camera_id}' already exists. Use a different ID, or edit the existing one.")

    cam = {
        "camera_id": camera_id,
        "zone_name": zone_name,
        "source_type": source_type,
        "host_path": host_path.strip(),
        "username": username,
        "password": password,
        "webcam_index": int(webcam_index) if webcam_index.strip().isdigit() else 0,
        "detect_reserved": detect_reserved == "1",
        "enabled": existing.get("enabled", False) if existing else False,
    }
    store.upsert_camera(cam)
    # If it was already running, restart it so the new settings take effect.
    if manager.is_running(camera_id):
        manager.start_camera(cam)
    return RedirectResponse("/", status_code=303)


@app.post("/cameras/delete")
def delete_camera(request: Request, camera_id: str = Form(...)):
    if not _logged_in(request):
        return RedirectResponse("/login", status_code=303)
    manager.stop_camera(camera_id)
    store.delete_camera(camera_id)
    return RedirectResponse("/", status_code=303)


@app.post("/cameras/toggle")
def toggle_camera(request: Request, camera_id: str = Form(...)):
    if not _logged_in(request):
        return RedirectResponse("/login", status_code=303)
    cam = store.get_camera(camera_id)
    if cam:
        if manager.is_running(camera_id):
            manager.stop_camera(camera_id)
            cam["enabled"] = False
        else:
            cam["enabled"] = True
            manager.start_camera(cam)
        store.upsert_camera(cam)
    return RedirectResponse("/", status_code=303)


@app.post("/start-all")
def start_all(request: Request):
    if not _logged_in(request):
        return RedirectResponse("/login", status_code=303)
    cams = store.load_cameras()
    for cam in cams:
        cam["enabled"] = True
        store.upsert_camera(cam)
    manager.start_all(cams)
    return RedirectResponse("/", status_code=303)


@app.post("/stop-all")
def stop_all(request: Request):
    if not _logged_in(request):
        return RedirectResponse("/login", status_code=303)
    manager.stop_all()
    for cam in store.load_cameras():
        cam["enabled"] = False
        store.upsert_camera(cam)
    return RedirectResponse("/", status_code=303)


@app.get("/api/status")
def api_status(request: Request):
    if not _logged_in(request):
        return JSONResponse({}, status_code=401)
    return JSONResponse(manager.status())



if __name__ == "__main__":
    # ASCII only: Windows consoles/redirected output may not encode arrows etc.
    print(f"\n  Library Counter portal  ->  http://{settings.PORTAL_HOST}:{settings.PORTAL_PORT}")
    print(f"  Sending counts to       ->  {settings.BACKEND_URL}\n")
    for p in setup_problems():
        print(f"  !! SETUP NEEDED: {p}")
    uvicorn.run(app, host=settings.PORTAL_HOST, port=settings.PORTAL_PORT, log_level="warning")
