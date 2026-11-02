"""Omensite Journal web app. Local by default. No orders and no public feed."""

from __future__ import annotations

import html
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import db
from app.auth import ANON, COOKIE, new_token, same_text
from app.discord_auth import (
    STATE_COOKIE,
    DiscordError,
    DiscordNotConfigured,
    authorize_url,
    fetch_profile,
)
from app.catalog import (
    ACCOUNT_KINDS,
    BIASES,
    DRAWS,
    EMOTIONS,
    GRADES,
    KILL_ZONES,
    MACROS,
    MISTAKES,
    PREMIUM,
    SESSIONS,
    TAGS,
    ZONES,
)
from app.firms import FIRMS
from app.public_pages import PUBLIC_PAGES, PRODUCT_PAGES, SOLUTION_PAGES, RESOURCE_PAGES
from app.sample_data import sample_overview
from app.instruments import FUTURES
from app.present import factor, hold, money, pct, plain, rmult
from app.services import (
    add_checklist_item,
    add_earnings_row,
    add_playbook_shot,
    add_symbol_watch,
    blank_draft,
    build_preview,
    checklist_for_form,
    confirm_import,
    create_account_for,
    dashboard_context,
    decorate_trades,
    disable_checklist_item,
    discard_preview,
    draft_from_form,
    draft_from_trade,
    export_backup,
    export_csv_text,
    finish_onboarding,
    load_sample,
    login_discord,
    news_context,
    next_high_impact,
    open_demo,
    parse_trade_form,
    plan_context,
    remove_account_for,
    remove_playbook,
    remove_playbook_shot,
    remove_shot,
    remove_trade,
    read_image,
    restore_backup,
    review_context,
    save_plan,
    save_playbook,
    save_shot_markup,
    save_trade,
    save_trade_shot,
    start_session,
    trade_detail,
    update_profile,
    user_zone,
)
from app.services_error import JournalError as FormError

DEMO_COOKIE = "omensite_demo"
DEMO_EMAIL = "demo@omensite.journal"

ROOT = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(ROOT / "templates"))
templates.env.filters["money"] = money
templates.env.filters["rmult"] = rmult
templates.env.filters["pct"] = pct
templates.env.filters["factor"] = factor
templates.env.filters["hold"] = hold
templates.env.filters["plain"] = plain
def shell_context(request: Request) -> dict:
    news = None
    if not request.url.path.startswith("/static"):
        try:
            with db.session() as conn:
                news = next_high_impact(conn)
        except Exception:
            news = None
    return {
        "tag_choices": TAGS,
        "mistake_choices": MISTAKES,
        "emotion_choices": EMOTIONS,
        "bias_choices": BIASES,
        "draw_choices": DRAWS,
        "premium_choices": PREMIUM,
        "session_choices": SESSIONS,
        "kill_choices": KILL_ZONES,
        "macro_choices": MACROS,
        "grade_choices": GRADES,
        "zones": ZONES,
        "account_kinds": ACCOUNT_KINDS,
        "futures": list(FUTURES.values()),
        "path": request.url.path,
        "next_news": news,
    }


templates.context_processors.append(shell_context)

NOTICES = {
    "sample": "Sample trades are in the journal.",
    "sample-exists": "The sample journal is already loaded.",
    "deleted": "Deleted.",
    "account": "Account saved.",
    "profile": "Settings saved.",
    "restored": "Backup added. Existing rows were left in place.",
    "plan": "The day's plan is saved.",
}


class NeedLogin(Exception):
    pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    with db.session() as conn:
        db.init_db(conn)
    yield


app = FastAPI(title="Omensite Journal", lifespan=lifespan)


@app.middleware("http")
async def attach_user(request: Request, call_next):
    request.state.user = None
    request.state.csrf = ""
    request.state.new_anon = None
    request.state.demo_mode = False
    if not request.url.path.startswith("/static"):
        with db.session() as conn:
            demo_token = request.cookies.get(DEMO_COOKIE)
            token = request.cookies.get(COOKIE)
            row = db.session_user(conn, demo_token) if demo_token else None
            if row is None and token:
                row = db.session_user(conn, token)
            if row:
                request.state.user = row
                request.state.csrf = row["csrf"]
                request.state.demo_mode = row["email"] == DEMO_EMAIL
            if not request.state.csrf:
                anon = request.cookies.get(ANON)
                if not anon:
                    anon = new_token()
                    request.state.new_anon = anon
                request.state.csrf = anon
    try:
        if (request.state.demo_mode and request.method not in {"GET", "HEAD", "OPTIONS"}
                and request.url.path not in {"/logout", "/demo"}):
            response = render(request, "error.html", 403, message="This demo is read-only.",
                              explanation="Explore the sample journal, or create your own account to add trades and save changes.")
        else:
            response = await call_next(request)
    finally:
        for form in request.scope.get("_omensite_forms", []):
            await form.close()
    if request.state.new_anon:
        response.set_cookie(
            ANON,
            request.state.new_anon,
            httponly=True,
            samesite="lax",
            max_age=7 * 86400,
            path="/",
            secure=request.url.scheme == "https",
        )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


async def read_form(request: Request):
    form = await request.form()
    request.scope.setdefault("_omensite_forms", []).append(form)
    return form


def current(request: Request) -> dict:
    if request.state.user is None:
        raise NeedLogin()
    return request.state.user


def assert_csrf(request: Request, form=None) -> None:
    sent = request.headers.get("x-csrf") or ""
    if form is not None and not sent:
        sent = str(form.get("csrf") or "")
    if not same_text(sent, request.state.csrf or ""):
        raise HTTPException(status_code=403, detail="The form expired. Refresh the page and try again.")


def render(request: Request, name: str, status: int = 200, **extra):
    code = request.query_params.get("notice", "")
    notice = NOTICES.get(code, "")
    if code == "imported" and request.query_params.get("count", "").isdigit():
        notice = f"Imported {request.query_params['count']} trades."
    extra.setdefault("notice", notice)
    extra.setdefault("csrf", request.state.csrf)
    extra.setdefault("user", request.state.user)
    extra.setdefault("error", "")
    extra.setdefault("demo_mode", getattr(request.state, "demo_mode", False))
    extra.setdefault("auth_mode", "login")
    extra.setdefault("sample", sample_overview())
    return templates.TemplateResponse(request, name, extra, status_code=status)


def home_for(conn, user_id: int) -> str:
    row = db.user_by_id(conn, user_id)
    if row and not row.get("onboarded"):
        return "/onboarding"
    return "/"


def set_session_cookie(response: Response, request: Request, token: str) -> None:
    response.delete_cookie(DEMO_COOKIE, path="/")
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=14 * 86400,
        path="/",
        secure=request.url.scheme == "https",
    )


def clear_demo_mode(response: Response, request: Request) -> None:
    response.delete_cookie(DEMO_COOKIE, path="/")
    legacy_token = request.cookies.get(COOKIE)
    if legacy_token:
        with db.session() as conn:
            row = db.session_user(conn, legacy_token)
        if row and row["email"] == DEMO_EMAIL:
            response.delete_cookie(COOKIE, path="/")


@app.exception_handler(NeedLogin)
async def redirect_login(request: Request, exc: NeedLogin):
    return RedirectResponse("/login", status_code=303)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    if exc.status_code == 303:
        return RedirectResponse(exc.headers.get("Location", "/"), status_code=303)
    message = exc.detail if isinstance(exc.detail, str) else "The page is not available."
    return render(request, "error.html", exc.status_code, message=message,
                  explanation="Return to Omensite Journal or explore the demo workspace.")


@app.get("/health")
def health():
    return {"ok": True, "name": "Omensite Journal"}


@app.get("/home")
def public_home(request: Request):
    return render(request, "home.html")


@app.get("/signup")
@app.get("/register")
def signup_page(request: Request):
    if request.state.user and not request.state.demo_mode:
        return RedirectResponse("/", status_code=303)
    return render(request, "auth.html", auth_mode="signup")


@app.get("/demo/exit")
def exit_demo(request: Request):
    response = RedirectResponse("/home", status_code=303)
    clear_demo_mode(response, request)
    return response


@app.get("/demo")
def enter_demo(request: Request):
    with db.session() as conn:
        user_id = open_demo(conn)
        token = start_session(conn, user_id)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(DEMO_COOKIE, token, httponly=True, samesite="lax",
                        max_age=6 * 3600, path="/", secure=request.url.scheme == "https")
    return response


@app.get("/products")
@app.get("/solutions")
@app.get("/brokers")
@app.get("/resources")
@app.get("/privacy")
def public_page(request: Request):
    key = request.url.path.strip("/")
    return render(request, "public_page.html", page=PUBLIC_PAGES[key],
                  products=PRODUCT_PAGES, solutions=SOLUTION_PAGES, resources=RESOURCE_PAGES)


@app.get("/products/{slug}")
def product_page(request: Request, slug: str):
    if slug not in PRODUCT_PAGES:
        raise HTTPException(404, "That product page is not available.")
    return render(request, "public_page.html", page={**PRODUCT_PAGES[slug], "kind": "detail"})


@app.get("/solutions/{slug}")
def solution_page(request: Request, slug: str):
    if slug not in SOLUTION_PAGES:
        raise HTTPException(404, "That solution page is not available.")
    return render(request, "public_page.html", page={**SOLUTION_PAGES[slug], "kind": "detail"})


@app.get("/resources/{slug}")
def resource_page(request: Request, slug: str):
    if slug not in RESOURCE_PAGES:
        raise HTTPException(404, "That resource page is not available.")
    return render(request, "public_page.html", page={**RESOURCE_PAGES[slug], "kind": "guide"})


@app.get("/login")
def login_page(request: Request):
    if request.state.user and not request.state.demo_mode:
        return RedirectResponse("/", status_code=303)
    return render(request, "auth.html")


@app.get("/auth/discord")
def discord_start(request: Request):
    if request.state.user and not request.state.demo_mode:
        return RedirectResponse("/", status_code=303)
    try:
        url, state = authorize_url(request)
    except DiscordNotConfigured:
        return render(request, "auth.html", 503, error="Discord sign-in is not available yet. Please try again later.")
    response = RedirectResponse(url, status_code=303)
    response.set_cookie(
        STATE_COOKIE,
        state,
        httponly=True,
        samesite="lax",
        max_age=600,
        path="/",
        secure=request.url.scheme == "https",
    )
    return response


@app.get("/auth/discord/callback")
def discord_callback(request: Request):
    if request.state.user and not request.state.demo_mode:
        return RedirectResponse("/", status_code=303)
    if request.query_params.get("error"):
        return render(request, "auth.html", 400, error="Discord did not complete sign-in.")
    sent = str(request.query_params.get("state") or "")
    saved = request.cookies.get(STATE_COOKIE) or ""
    if not same_text(sent, saved):
        return render(request, "auth.html", 400, error="That sign-in expired. Try Discord again.")
    try:
        profile = fetch_profile(request, str(request.query_params.get("code") or ""))
        with db.session() as conn:
            user_id = login_discord(conn, profile)
            token = start_session(conn, user_id)
            dest = home_for(conn, user_id)
    except (DiscordNotConfigured, DiscordError, FormError) as exc:
        return render(request, "auth.html", 400, error=str(exc))
    response = RedirectResponse(dest, status_code=303)
    set_session_cookie(response, request, token)
    response.delete_cookie(STATE_COOKIE, path="/")
    return response


@app.get("/forgot")
@app.get("/reset/{token}")
def retired_password_page(request: Request, token: str = ""):
    return RedirectResponse("/login", status_code=303)


@app.post("/demo")
async def demo(request: Request):
    form = await read_form(request)
    assert_csrf(request, form)
    return RedirectResponse("/demo", status_code=303)


@app.get("/onboarding")
def onboarding_page(request: Request):
    user = current(request)
    with db.session() as conn:
        if db.user_by_id(conn, user["id"]).get("onboarded"):
            return RedirectResponse("/", status_code=303)
    return render(request, "onboarding.html", firms={"topstep": {**FIRMS["topstep"], "note": "Illustrative starting values. Replace them with the limits shown in your Topstep account."}})


@app.post("/onboarding")
async def onboarding_submit(request: Request):
    user = current(request)
    form = await read_form(request)
    assert_csrf(request, form)
    try:
        with db.session() as conn:
            finish_onboarding(conn, user, form)
    except FormError as exc:
        return render(
            request,
            "onboarding.html",
            400,
            error=str(exc),
            firms={"topstep": {**FIRMS["topstep"], "note": "Illustrative starting values. Replace them with the limits shown in your Topstep account."}},
        )
    return RedirectResponse("/", status_code=303)


@app.post("/logout")
async def logout(request: Request):
    form = await read_form(request)
    assert_csrf(request, form)
    if request.state.demo_mode:
        response = RedirectResponse("/home", status_code=303)
        clear_demo_mode(response, request)
        return response
    token = request.cookies.get(COOKIE)
    if token:
        with db.session() as conn:
            db.delete_session(conn, token)
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(COOKIE, path="/")
    return response


@app.get("/")
def dashboard_page(request: Request):
    if request.state.user is None:
        return render(request, "home.html")
    user = current(request)
    range_key = request.query_params.get("range", "all")
    if range_key not in {"7d", "30d", "mtd", "all"}:
        range_key = "all"
    account_raw = request.query_params.get("account", "")
    account_id = int(account_raw) if account_raw.isdigit() else None
    with db.session() as conn:
        if account_id is not None and db.account(conn, user["id"], account_id) is None:
            account_id = None
        ctx = dashboard_context(conn, user, account_id, range_key, request.query_params.get("month", ""))
    return render(request, "dashboard.html", **ctx)


@app.get("/trades")
def trades_page(request: Request):
    user = current(request)
    with db.session() as conn:
        rows = decorate_trades(conn, user)
        accounts = db.accounts(conn, user["id"])
    instrument = request.query_params.get("instrument", "")
    session_name = request.query_params.get("session", "")
    direction = request.query_params.get("direction", "")
    grade = request.query_params.get("grade", "")
    account = request.query_params.get("account", "")
    filtered = []
    for trade in rows:
        if instrument and trade["instrument"] != instrument:
            continue
        if session_name and trade["session"] != session_name:
            continue
        if direction and trade["direction"] != direction:
            continue
        if grade and (trade["grade"] or "") != grade:
            continue
        if account and str(trade["account_id"]) != account:
            continue
        filtered.append(trade)
    symbols = sorted({trade["instrument"] for trade in rows})
    return render(
        request,
        "trades.html",
        trades=filtered,
        accounts=accounts,
        symbols=symbols,
        filters={
            "instrument": instrument,
            "session": session_name,
            "direction": direction,
            "grade": grade,
            "account": account,
        },
    )


def _form_page(request, user, draft, accounts, checks, trade_id, error, status=200):
    return render(
        request,
        "trade_form.html",
        status,
        draft=draft,
        accounts=accounts,
        checks=checks,
        trade_id=trade_id,
        error=error,
    )


@app.get("/trades/new")
def new_trade(request: Request):
    user = current(request)
    with db.session() as conn:
        accounts = db.accounts(conn, user["id"])
        checks = [item for item in db.checklist(conn, user["id"]) if item["active"]]
    account_id = accounts[0]["id"] if accounts else ""
    return _form_page(request, user, blank_draft(account_id), accounts, checks, None, "")


@app.post("/trades")
async def create_trade(request: Request):
    return await _save_trade(request, None)


@app.get("/trades/{trade_id}")
def trade_page(request: Request, trade_id: int):
    user = current(request)
    with db.session() as conn:
        detail = trade_detail(conn, user, trade_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Trade not found.")
    return render(request, "trade_detail.html", **detail)


@app.get("/trades/{trade_id}/edit")
def edit_trade(request: Request, trade_id: int):
    user = current(request)
    with db.session() as conn:
        detail = trade_detail(conn, user, trade_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Trade not found.")
        items = db.checklist(conn, user["id"])
        accounts = db.accounts(conn, user["id"])
        shown = checklist_for_form(items, detail["checks"])
        draft = draft_from_trade(detail["trade"], detail["legs"], detail["tags"], detail["mistakes"], detail["checks"], user_zone(user))
    return _form_page(request, user, draft, accounts, shown, trade_id, "")


@app.post("/trades/{trade_id}")
async def update_trade(request: Request, trade_id: int):
    return await _save_trade(request, trade_id)


async def _save_trade(request: Request, trade_id: int | None):
    user = current(request)
    form = await read_form(request)
    assert_csrf(request, form)
    with db.session() as conn:
        items = db.checklist(conn, user["id"])
        previous = db.checks_for_trade(conn, trade_id) if trade_id else []
        shown = checklist_for_form(items, previous)
        accounts = db.accounts(conn, user["id"])
        try:
            parsed = parse_trade_form(form, user_zone(user), shown)
            saved = save_trade(conn, user["id"], parsed, trade_id)
        except FormError as exc:
            return _form_page(request, user, draft_from_form(form), accounts, shown, trade_id, str(exc), 400)
    return RedirectResponse(f"/trades/{saved}", status_code=303)


@app.post("/trades/{trade_id}/delete")
async def delete_trade(request: Request, trade_id: int):
    user = current(request)
    form = await read_form(request)
    assert_csrf(request, form)
    try:
        with db.session() as conn:
            remove_trade(conn, user["id"], trade_id)
    except FormError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RedirectResponse("/trades?notice=deleted", status_code=303)


@app.post("/trades/{trade_id}/shots")
async def upload_shot(request: Request, trade_id: int):
    user = current(request)
    form = await read_form(request)
    assert_csrf(request, form)
    upload = form.get("image")
    data = await upload.read() if upload is not None and hasattr(upload, "read") else b""
    try:
        with db.session() as conn:
            save_trade_shot(conn, user, trade_id, str(form.get("slot") or ""), data)
    except FormError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(f"/trades/{trade_id}", status_code=303)


@app.post("/trades/{trade_id}/shots/{shot_id}/markup")
async def markup(request: Request, trade_id: int, shot_id: int):
    user = current(request)
    assert_csrf(request)
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Markup could not be read.") from exc
    shapes = payload.get("shapes") if isinstance(payload, dict) else None
    try:
        with db.session() as conn:
            if db.shot(conn, user["id"], shot_id) is None or db.shot(conn, user["id"], shot_id)["trade_id"] != trade_id:
                raise HTTPException(status_code=404, detail="Chart not found.")
            save_shot_markup(conn, user, shot_id, shapes)
    except FormError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@app.post("/trades/{trade_id}/shots/{shot_id}/delete")
async def delete_shot(request: Request, trade_id: int, shot_id: int):
    user = current(request)
    form = await read_form(request)
    assert_csrf(request, form)
    try:
        with db.session() as conn:
            row = db.shot(conn, user["id"], shot_id)
            if row is None or row["trade_id"] != trade_id:
                raise HTTPException(status_code=404, detail="Chart not found.")
            remove_shot(conn, user, shot_id)
    except FormError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RedirectResponse(f"/trades/{trade_id}", status_code=303)


@app.get("/media/{shot_id}")
def media(request: Request, shot_id: int):
    user = current(request)
    with db.session() as conn:
        row = db.shot(conn, user["id"], shot_id)
        content = read_image(conn, user["id"], row["filename"]) if row else None
    if row is None:
        raise HTTPException(status_code=404, detail="Chart not found.")
    if content is None:
        raise HTTPException(status_code=404, detail="Chart not found.")
    types = {".png": "image/png", ".jpg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
    return Response(content=content, media_type=types.get(Path(row["filename"]).suffix, "application/octet-stream"))


@app.get("/import")
def import_page(request: Request):
    user = current(request)
    with db.session() as conn:
        accounts = db.accounts(conn, user["id"])
    return render(request, "import.html", accounts=accounts, preview=None, token="")


@app.post("/import/preview")
async def import_preview(request: Request):
    user = current(request)
    form = await read_form(request)
    assert_csrf(request, form)
    upload = form.get("file")
    raw = await upload.read() if upload is not None and hasattr(upload, "read") else b""
    if len(raw) > 2_000_000:
        return render(request, "import.html", 400, accounts=[], preview=None, token="", error="CSV files are limited to 2 MB.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError:
        return render(request, "import.html", 400, accounts=[], preview=None, token="", error="The file needs to be UTF-8 text.")
    try:
        with db.session() as conn:
            accounts = db.accounts(conn, user["id"])
        token, rows = build_preview(user["id"], text, user_zone(user))
    except FormError as exc:
        with db.session() as conn:
            accounts = db.accounts(conn, user["id"])
        return render(request, "import.html", 400, accounts=accounts, preview=None, token="", error=str(exc))
    return render(request, "import.html", accounts=accounts, preview=rows, token=token)


@app.post("/import/confirm")
async def import_confirm(request: Request):
    user = current(request)
    form = await read_form(request)
    assert_csrf(request, form)
    account_raw = str(form.get("account_id") or "")
    token = str(form.get("token") or "")
    if not account_raw.isdigit():
        raise HTTPException(status_code=400, detail="Choose an account.")
    try:
        with db.session() as conn:
            count = confirm_import(conn, user, token, int(account_raw))
        discard_preview(user["id"], token)
    except FormError as exc:
        with db.session() as conn:
            accounts = db.accounts(conn, user["id"])
        return render(request, "import.html", 400, accounts=accounts, preview=None, token="", error=str(exc))
    return RedirectResponse(f"/trades?notice=imported&count={count}", status_code=303)


@app.get("/news")
def news_page(request: Request):
    user = current(request)
    with db.session() as conn:
        ctx = news_context(conn, user)
    return render(request, "news.html", **ctx)


@app.post("/news/watchlist")
async def add_watch(request: Request):
    user = current(request)
    form = await read_form(request)
    assert_csrf(request, form)
    try:
        with db.session() as conn:
            add_symbol_watch(conn, user, str(form.get("symbol") or ""))
    except FormError as exc:
        with db.session() as conn:
            ctx = news_context(conn, user)
        return render(request, "news.html", 400, error=str(exc), **ctx)
    return RedirectResponse("/news", status_code=303)


@app.post("/news/watchlist/{watch_id}/delete")
async def delete_watch(request: Request, watch_id: int):
    user = current(request)
    form = await read_form(request)
    assert_csrf(request, form)
    with db.session() as conn:
        db.delete_watch(conn, user["id"], watch_id)
    return RedirectResponse("/news", status_code=303)


@app.post("/news/earnings")
async def add_earning(request: Request):
    user = current(request)
    form = await read_form(request)
    assert_csrf(request, form)
    try:
        with db.session() as conn:
            add_earnings_row(conn, user, form, user_zone(user))
    except FormError as exc:
        with db.session() as conn:
            ctx = news_context(conn, user)
        return render(request, "news.html", 400, error=str(exc), **ctx)
    return RedirectResponse("/news", status_code=303)


@app.post("/news/earnings/{earning_id}/delete")
async def delete_earning(request: Request, earning_id: int):
    user = current(request)
    form = await read_form(request)
    assert_csrf(request, form)
    with db.session() as conn:
        db.delete_earning(conn, user["id"], earning_id)
    return RedirectResponse("/news", status_code=303)


@app.get("/plan")
def plan_page(request: Request):
    user = current(request)
    try:
        with db.session() as conn:
            ctx = plan_context(conn, user, request.query_params.get("day", ""))
    except FormError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return render(request, "plan.html", **ctx)


@app.post("/plan")
async def plan_save(request: Request):
    user = current(request)
    form = await read_form(request)
    assert_csrf(request, form)
    try:
        with db.session() as conn:
            day = save_plan(conn, user, form)
    except FormError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(f"/plan?day={day}&notice=plan", status_code=303)


@app.get("/reviews")
def reviews_page(request: Request):
    user = current(request)
    try:
        with db.session() as conn:
            ctx = review_context(
                conn,
                user,
                request.query_params.get("week", ""),
                request.query_params.get("month", ""),
            )
    except FormError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return render(request, "reviews.html", **ctx)


@app.get("/playbook")
def playbook_page(request: Request):
    user = current(request)
    with db.session() as conn:
        books = db.playbooks(conn, user["id"])
        for book in books:
            images = db.playbook_images(conn, book["id"])
            book["cover"] = images[0]["id"] if images else None
    return render(request, "playbook.html", books=books)


@app.post("/playbook")
async def playbook_create(request: Request):
    user = current(request)
    form = await read_form(request)
    assert_csrf(request, form)
    try:
        with db.session() as conn:
            book_id = save_playbook(conn, user, form)
    except FormError as exc:
        with db.session() as conn:
            books = db.playbooks(conn, user["id"])
        return render(request, "playbook.html", 400, books=books, error=str(exc))
    return RedirectResponse(f"/playbook/{book_id}", status_code=303)


@app.get("/playbook/{playbook_id}")
def playbook_detail(request: Request, playbook_id: int):
    user = current(request)
    with db.session() as conn:
        book = db.playbook(conn, user["id"], playbook_id)
        images = db.playbook_images(conn, playbook_id) if book else []
    if book is None:
        raise HTTPException(status_code=404, detail="Setup not found.")
    return render(request, "playbook_detail.html", book=book, images=images)


@app.post("/playbook/{playbook_id}")
async def playbook_update(request: Request, playbook_id: int):
    user = current(request)
    form = await read_form(request)
    assert_csrf(request, form)
    try:
        with db.session() as conn:
            save_playbook(conn, user, form, playbook_id)
    except FormError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(f"/playbook/{playbook_id}", status_code=303)


@app.post("/playbook/{playbook_id}/delete")
async def playbook_delete(request: Request, playbook_id: int):
    user = current(request)
    form = await read_form(request)
    assert_csrf(request, form)
    try:
        with db.session() as conn:
            remove_playbook(conn, user, playbook_id)
    except FormError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RedirectResponse("/playbook?notice=deleted", status_code=303)


@app.post("/playbook/{playbook_id}/images")
async def playbook_image_add(request: Request, playbook_id: int):
    user = current(request)
    form = await read_form(request)
    assert_csrf(request, form)
    upload = form.get("image")
    data = await upload.read() if upload is not None and hasattr(upload, "read") else b""
    try:
        with db.session() as conn:
            add_playbook_shot(conn, user, playbook_id, data)
    except FormError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(f"/playbook/{playbook_id}", status_code=303)


@app.post("/playbook/{playbook_id}/images/{image_id}/delete")
async def playbook_image_delete(request: Request, playbook_id: int, image_id: int):
    user = current(request)
    form = await read_form(request)
    assert_csrf(request, form)
    with db.session() as conn:
        row = db.playbook_image(conn, user["id"], image_id)
        if row is None or row["playbook_id"] != playbook_id:
            raise HTTPException(status_code=404, detail="Image not found.")
        remove_playbook_shot(conn, user, image_id)
    return RedirectResponse(f"/playbook/{playbook_id}", status_code=303)


@app.get("/playbook-media/{image_id}")
def playbook_media(request: Request, image_id: int):
    user = current(request)
    with db.session() as conn:
        row = db.playbook_image(conn, user["id"], image_id)
        content = read_image(conn, user["id"], row["filename"]) if row else None
    if row is None:
        raise HTTPException(status_code=404, detail="Image not found.")
    if content is None:
        raise HTTPException(status_code=404, detail="Image not found.")
    types = {".png": "image/png", ".jpg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
    return Response(content=content, media_type=types.get(Path(row["filename"]).suffix, "application/octet-stream"))


@app.get("/settings")
def settings_page(request: Request):
    user = current(request)
    with db.session() as conn:
        accounts = db.accounts(conn, user["id"])
        checks = db.checklist(conn, user["id"])
    return render(request, "settings.html", accounts=accounts, checks=checks)


@app.post("/settings/profile")
async def settings_profile(request: Request):
    user = current(request)
    form = await read_form(request)
    assert_csrf(request, form)
    try:
        with db.session() as conn:
            update_profile(conn, user, str(form.get("timezone") or ""), str(form.get("window") or ""))
    except FormError as exc:
        with db.session() as conn:
            accounts = db.accounts(conn, user["id"])
            checks = db.checklist(conn, user["id"])
        return render(request, "settings.html", 400, accounts=accounts, checks=checks, error=str(exc))
    return RedirectResponse("/settings?notice=profile", status_code=303)


@app.post("/settings/accounts")
async def settings_account(request: Request):
    user = current(request)
    form = await read_form(request)
    assert_csrf(request, form)
    try:
        with db.session() as conn:
            create_account_for(conn, user, form)
    except FormError as exc:
        with db.session() as conn:
            accounts = db.accounts(conn, user["id"])
            checks = db.checklist(conn, user["id"])
        return render(request, "settings.html", 400, accounts=accounts, checks=checks, error=str(exc))
    return RedirectResponse("/settings?notice=account", status_code=303)


@app.post("/settings/accounts/{account_id}/delete")
async def settings_account_delete(request: Request, account_id: int):
    user = current(request)
    form = await read_form(request)
    assert_csrf(request, form)
    try:
        with db.session() as conn:
            remove_account_for(conn, user, account_id)
    except FormError as exc:
        with db.session() as conn:
            accounts = db.accounts(conn, user["id"])
            checks = db.checklist(conn, user["id"])
        return render(request, "settings.html", 400, accounts=accounts, checks=checks, error=str(exc))
    return RedirectResponse("/settings?notice=deleted", status_code=303)


@app.post("/settings/checks")
async def settings_check(request: Request):
    user = current(request)
    form = await read_form(request)
    assert_csrf(request, form)
    try:
        with db.session() as conn:
            add_checklist_item(conn, user, str(form.get("label") or ""))
    except FormError as exc:
        with db.session() as conn:
            accounts = db.accounts(conn, user["id"])
            checks = db.checklist(conn, user["id"])
        return render(request, "settings.html", 400, accounts=accounts, checks=checks, error=str(exc))
    return RedirectResponse("/settings?notice=profile", status_code=303)


@app.post("/settings/checks/{item_id}/disable")
async def settings_check_disable(request: Request, item_id: int):
    user = current(request)
    form = await read_form(request)
    assert_csrf(request, form)
    with db.session() as conn:
        disable_checklist_item(conn, user, item_id)
    return RedirectResponse("/settings?notice=profile", status_code=303)


@app.post("/settings/sample")
async def settings_sample(request: Request):
    user = current(request)
    form = await read_form(request)
    assert_csrf(request, form)
    with db.session() as conn:
        code = load_sample(conn, user)
    return RedirectResponse(f"/?notice={code}", status_code=303)


@app.get("/export.csv")
def export_csv(request: Request):
    user = current(request)
    with db.session() as conn:
        text = export_csv_text(conn, user)
    return Response(
        content=text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=omensite-journal.csv"},
    )


@app.get("/export.json")
def export_json(request: Request):
    user = current(request)
    with db.session() as conn:
        payload = export_backup(conn, user)
    return Response(
        content=json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=omensite-journal-backup.json"},
    )


@app.post("/settings/restore")
async def settings_restore(request: Request):
    user = current(request)
    form = await read_form(request)
    assert_csrf(request, form)
    upload = form.get("backup")
    raw = await upload.read() if upload is not None and hasattr(upload, "read") else b""
    if len(raw) > 40 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Backups are limited to 40 MB.")
    try:
        payload = json.loads(raw.decode("utf-8"))
        with db.session() as conn:
            restore_backup(conn, user, payload)
    except FormError as exc:
        with db.session() as conn:
            accounts = db.accounts(conn, user["id"])
            checks = db.checklist(conn, user["id"])
        return render(request, "settings.html", 400, accounts=accounts, checks=checks, error=str(exc))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="That file is not a journal backup.") from exc
    return RedirectResponse("/settings?notice=restored", status_code=303)


@app.get("/report")
def report_page(request: Request):
    user = current(request)
    with db.session() as conn:
        ctx = dashboard_context(conn, user)
        ctx["trades"] = decorate_trades(conn, user)
    return render(request, "report.html", **ctx)


app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")
