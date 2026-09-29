import os, json, uuid, hashlib, secrets
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

load_dotenv()
import gemini_utils as ai

app = FastAPI(title="PocketSmart: AI Budget Planner")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "dev-secret"), max_age=1800)
os.makedirs("static/uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

USERS, HISTORY = "users.json", "history.json"


def load(path):
    return json.load(open(path)) if os.path.exists(path) else ([] if path == HISTORY else {})


def save(path, data):
    json.dump(data, open(path, "w"), indent=2)


def hash_pw(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100_000).hex()


def me(request: Request):
    return request.session.get("user")


def page(request, name, **ctx):
    return templates.TemplateResponse(request, name, {"user": me(request), **ctx})


def log(user, kind, inp, res):
    if "error" in res:
        return
    h = load(HISTORY)
    h.append({"id": uuid.uuid4().hex[:8], "user": user, "type": kind,
              "time": datetime.now().strftime("%d %b %Y, %I:%M %p"), "input": inp, "result": res})
    save(HISTORY, h)


# ---------- pages & auth ----------
@app.get("/")
async def index(request: Request):
    return page(request, "index.html")


@app.get("/register")
async def register_page(request: Request):
    return page(request, "auth.html", mode="register", error=None)


@app.post("/register")
async def register(request: Request, username: str = Form(...), email: str = Form(...),
                   password: str = Form(...), confirm: str = Form(...)):
    users = load(USERS)
    err = None
    if password != confirm: err = "Passwords do not match."
    elif len(password) < 6: err = "Use at least 6 characters for the password."
    elif username.lower() in users: err = "That username is taken. Try another."
    if err:
        return page(request, "auth.html", mode="register", error=err)
    salt = secrets.token_hex(8)
    users[username.lower()] = {"name": username, "email": email, "salt": salt, "hash": hash_pw(password, salt)}
    save(USERS, users)
    request.session["user"] = username.lower()
    return RedirectResponse("/dashboard", 302)


@app.get("/login")
async def login_page(request: Request):
    if me(request): return RedirectResponse("/dashboard", 302)
    return page(request, "auth.html", mode="login", error=None)


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    u = load(USERS).get(username.lower())
    if not u or u["hash"] != hash_pw(password, u["salt"]):
        return page(request, "auth.html", mode="login", error="Wrong username or password.")
    request.session["user"] = username.lower()
    return RedirectResponse("/dashboard", 302)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", 302)


@app.get("/dashboard")
async def dashboard(request: Request):
    if not me(request): return RedirectResponse("/login", 302)
    recent = [h for h in load(HISTORY) if h["user"] == me(request)][-3:][::-1]
    return page(request, "dashboard.html", recent=recent)


@app.get("/planner/{kind}")
async def planner(request: Request, kind: str):
    if not me(request): return RedirectResponse("/login", 302)
    if kind not in ("home", "party", "jewelry"): return RedirectResponse("/dashboard", 302)
    return page(request, "planner.html", kind=kind)


@app.get("/history")
async def history(request: Request):
    if not me(request): return RedirectResponse("/login", 302)
    items = [h for h in load(HISTORY) if h["user"] == me(request)][::-1]
    return page(request, "history.html", items=items)


# ---------- AI endpoints ----------
def need_login(request):
    return None if me(request) else JSONResponse({"error": "Session expired. Please sign in again."}, 401)


@app.post("/generate-home")
async def generate_home(request: Request, total_budget: float = Form(...), lights: int = Form(0),
                        fans: int = Form(0), furniture: int = Form(0), tables: int = Form(0),
                        rooms: List[str] = Form([]), notes: str = Form("")):
    if r := need_login(request): return r
    inp = dict(total_budget=total_budget, lights=lights, fans=fans, furniture=furniture,
               tables=tables, rooms=rooms, notes=notes)
    res = ai.home(inp); log(me(request), "home", inp, res)
    return res


@app.post("/generate-party")
async def generate_party(request: Request, total_budget: float = Form(...), guests: int = Form(...),
                         party_type: str = Form("Birthday"), venue: str = Form("Home"),
                         needs: List[str] = Form([]), notes: str = Form("")):
    if r := need_login(request): return r
    inp = dict(total_budget=total_budget, guests=guests, party_type=party_type, venue=venue,
               needs=needs, notes=notes)
    res = ai.party(inp); log(me(request), "party", inp, res)
    return res


@app.post("/generate-jewelry")
async def generate_jewelry(request: Request, total_budget: float = Form(...), occasion: str = Form(...),
                           preferences: str = Form(""), image: Optional[UploadFile] = File(None)):
    if r := need_login(request): return r
    path = None
    if image and image.filename:
        path = f"static/uploads/{uuid.uuid4().hex[:8]}_{os.path.basename(image.filename)}"
        open(path, "wb").write(await image.read())
    inp = dict(total_budget=total_budget, occasion=occasion, preferences=preferences, has_image=bool(path))
    res = ai.jewelry(inp, path); log(me(request), "jewelry", inp, res)
    return res


if __name__ == "__main__":
    import uvicorn
    print("Starting PocketSmart at http://127.0.0.1:8000")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
