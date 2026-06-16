"""Sri Vengamamba PG (S.V PG Hostel — Gents) – Single-Property Booking Backend
FastAPI + MongoDB. Bed-level booking with floors, rooms and Razorpay payment.
"""
from dotenv import load_dotenv
load_dotenv()

import os
import jwt
import bcrypt
import uuid
import hmac
import hashlib
import json as _json
import httpx
import razorpay
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from fastapi import FastAPI, HTTPException, Depends, Request, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

from utils import save_uploaded_file, generate_receipt, ALLOWED_IMG, ALLOWED_DOC

# ---------- Config ----------
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@svpg.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@123")
RZP_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "rzp_test_placeholder")
RZP_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "placeholder_secret")
RZP_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
IS_PLACEHOLDER_RZP = True

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")  
os.makedirs(UPLOAD_DIR, exist_ok=True)

RECEIPTS_DIR = os.path.join(UPLOAD_DIR, "receipts")
os.makedirs(RECEIPTS_DIR, exist_ok=True)

# ---------- Single Property (from GitHub repo) ----------
PG_CONFIG: Dict[str, Any] = {
    "name": "Sri Vengamamba PG",
    "tagline": "S.V PG Hostel — Gents",
    "owner": "Mohan",
    "phone": "+91 98765 43210",
    "email": "info@svpg.in",
    "address": "Sri Vengamamba PG, Near Tech Park, Bengaluru",
    "city": "Bengaluru",
    "gender": "Gents only",
    "confirmation_code": "MOHANSVPG",

    # Floor → list of bed counts per room (matches repo's roomStructure)
    "room_structure": {
        "1": [2, 2, 3, 3, 2, 2],
        "2": [2, 2, 3, 3, 2, 2],
        "3": [2, 2, 3, 3, 2, 2],
        "4": [2, 2, 3, 3, 2, 2],
        "5": [2, 2, 3, 3, 2, 2],
        "6": [2, 2, 3, 3],
    },

    # Pricing — straight from repo
    "price_2sharing": 11000,
    "price_3sharing": 9000,
    "advance": 20000,
    "max_beds_per_booking": 3,

    "amenities": [
        "WiFi", "Hot Water", "Power Backup", "Laundry",
        "Housekeeping", "CCTV", "Security", "Refrigerator",
        "Washing Machine", "RO Water",
    ],

    "food_timings": [
        {"meal": "Breakfast", "time": "7:30 AM – 9:30 AM", "menu": "Idli, Dosa, Poha, Upma (rotating)"},
        {"meal": "Lunch", "time": "12:30 PM – 2:30 PM", "menu": "Rice, Dal, 2 Curries, Curd, Pickle"},
        {"meal": "Snacks", "time": "5:30 PM – 6:30 PM", "menu": "Tea + Biscuits / Fritters"},
        {"meal": "Dinner", "time": "8:00 PM – 10:00 PM", "menu": "Chapati, Rice, Sabji, Dal"},
    ],

    "rules": [
        "Gents only PG — no female guests inside rooms.",
        "Main gate closes at 11:00 PM. Late arrivals must inform warden.",
        "No smoking, alcohol or drugs allowed on the premises.",
        "No loud music after 10:00 PM.",
        "Visitors permitted only in common area between 9 AM – 8 PM.",
        "Cooking inside rooms is strictly prohibited.",
        "Keep your room and common areas clean.",
        "₹20,000 refundable advance is mandatory at booking.",
        "Rent must be paid by the 5th of every month.",
        "Two-month notice required before vacating; otherwise advance is forfeited.",
    ],

    "images": [
        "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=1600",
        "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=1600",
        "https://images.unsplash.com/photo-1505691938895-1758d7feb511?w=1600",
        "https://images.unsplash.com/photo-1631049307264-da0ec9d70304?w=1600",
        "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=1600",
    ],
}


# ---------- Setup ----------
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client[DB_NAME]

razorpay_client: Optional[razorpay.Client] = None
if not IS_PLACEHOLDER_RZP:
    try:
        razorpay_client = razorpay.Client(auth=(RZP_KEY_ID, RZP_KEY_SECRET))
    except Exception:
        razorpay_client = None


# ---------- Helpers ----------
def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_token(user_id: str, role: str, days: int = 7) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(days=days),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def serialize(doc: Optional[dict]) -> Optional[dict]:
    if not doc:
        return doc
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    d.pop("password_hash", None)
    for k, v in list(d.items()):
        if isinstance(v, datetime):
            d[k] = v.isoformat()
        if isinstance(v, ObjectId):
            d[k] = str(v)
    return d


def room_number(floor: int, room: int) -> str:
    return f"{floor}{str(room).zfill(2)}"


def bed_price(floor: str, room_idx_1based: int) -> int:
    """Return per-bed monthly rent based on the sharing count of that room."""
    beds = PG_CONFIG["room_structure"][str(floor)][room_idx_1based - 1]
    return PG_CONFIG["price_2sharing"] if beds == 2 else PG_CONFIG["price_3sharing"]


async def get_user_from_token(request: Request) -> Optional[dict]:
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        uid = payload.get("sub", "")
        return await db.users.find_one({"user_id": uid})
    except Exception:
        return None


async def require_user(request: Request) -> dict:
    u = await get_user_from_token(request)
    if not u:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return u


async def require_admin(request: Request) -> dict:
    u = await require_user(request)
    if u.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return u


# ---------- Models ----------
class RegisterReq(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=6)
    phone: str = ""


class LoginReq(BaseModel):
    email: EmailStr
    password: str


class BedSel(BaseModel):
    floor: int
    room: int  # 1-based index inside the floor
    bed: int   # 1-based index inside the room


class BookingCreateReq(BaseModel):
    beds: List[BedSel]
    name: str = Field(min_length=2)
    phone: str = Field(min_length=10)
    alt_phone: str = Field(min_length=10)
    email: EmailStr
    aadhaar_number: str = Field(min_length=12, max_length=12, pattern=r"^\d{12}$")
    join_date: str  # YYYY-MM-DD
    notes: str = ""
    photo_url: str = Field(min_length=1)
    aadhaar_url: str = Field(min_length=1)


class MarkPaidReq(BaseModel):
    payment_method: str = "cash"
    payment_reference: str = ""


class SendReminderReq(BaseModel):
    channel: str = "email"  # email | sms (future)
    message: str = ""


class PaymentVerifyReq(BaseModel):
    booking_group_id: str
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


# ---------- Lifespan ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.bookings.create_index([("floor", 1), ("room", 1), ("bed", 1)])
    await db.bookings.create_index("user_id")
    await db.bookings.create_index("booking_group_id")

    # Seed admin
    if not await db.users.find_one({"email": ADMIN_EMAIL.lower()}):
        await db.users.insert_one({
            "user_id": f"user_{uuid.uuid4().hex[:12]}",
            "name": "S.V PG Admin",
            "email": ADMIN_EMAIL.lower(),
            "phone": "",
            "password_hash": hash_password(ADMIN_PASSWORD),
            "role": "admin",
            "created_at": utc_now(),
            "rules_accepted": True,
        })

    # ----- Schedule daily auto-reminders (runs on 5th of every month at 09:00 IST) -----
    scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(
        _auto_send_monthly_reminders,
        CronTrigger(day=5, hour=9, minute=0, timezone="Asia/Kolkata"),
        id="monthly_rent_reminders",
        replace_existing=True,
    )
    scheduler.start()
    app.state.scheduler = scheduler

    try:
        yield
    finally:
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            pass


app = FastAPI(lifespan=lifespan, title="Sri Vengamamba PG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost:5500",
    "https://sri-vengamamba-pg.vercel.app",
    "https://sri-vengamamba-pg.onrender.com",
],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded files
from fastapi.staticfiles import StaticFiles
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app.mount(
    "/uploads",
    StaticFiles(directory=os.path.join(BASE_DIR, "uploads")),
    name="uploads"
)

# ---------- Public config ----------
@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "time": utc_now().isoformat()}


@app.get("/api/pg/config")
async def pg_config() -> dict:
    """Public PG details + pricing + structure (no secrets)."""
    pub = {k: v for k, v in PG_CONFIG.items() if k != "confirmation_code"}
    return pub


@app.get("/api/pg/availability")
async def pg_availability() -> dict:
    """Return list of booked beds as {floor, room, bed, name (masked)}."""
    cursor = db.bookings.find(
        {"status": {"$in": ["paid", "confirmed"]}},
        {"floor": 1, "room": 1, "bed": 1, "name": 1, "_id": 0},
    )
    booked = [b async for b in cursor]
    for b in booked:
        n = (b.get("name") or "").strip()
        b["name"] = (n.split()[0] if n else "Booked")
    return {"booked": booked, "total_booked": len(booked)}


# ---------- Auth ----------
@app.post("/api/auth/register")
async def register(req: RegisterReq) -> dict:
    email = req.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    doc = {
        "user_id": user_id,
        "name": req.name,
        "email": email,
        "phone": req.phone or "",
        "password_hash": hash_password(req.password),
        "role": "guest",
        "rules_accepted": False,
        "created_at": utc_now(),
    }
    await db.users.insert_one(doc)
    return {"token": create_token(user_id, "guest"), "user": serialize(doc)}


@app.post("/api/auth/login")
async def login(req: LoginReq) -> dict:
    email = req.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(req.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"token": create_token(user["user_id"], user["role"]), "user": serialize(user)}


@app.get("/api/auth/me")
async def me(user: dict = Depends(require_user)) -> dict:
    return serialize(user)


@app.post("/api/auth/accept-rules")
async def accept_rules(user: dict = Depends(require_user)) -> dict:
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"rules_accepted": True}})
    return {"ok": True}


# ---------- Booking ----------
PENDING_HOLD_MINUTES = 15  # how long a pending booking holds a bed before being auto-released


async def _cleanup_stale_pending() -> int:
    """Delete pending+unpaid bookings older than PENDING_HOLD_MINUTES (frees the beds)."""
    cutoff = utc_now() - timedelta(minutes=PENDING_HOLD_MINUTES)
    res = await db.bookings.delete_many({
        "status": "pending", "payment_status": "unpaid", "created_at": {"$lt": cutoff},
    })
    return res.deleted_count


async def _are_beds_free(beds: List[BedSel], current_user_id: Optional[str] = None) -> List[BedSel]:
    """Return any beds taken by someone else. Pending bookings only block for PENDING_HOLD_MINUTES.

    Rules:
      • paid / confirmed bookings always block the bed
      • pending bookings block only if newer than PENDING_HOLD_MINUTES AND belong to a different user
      • the same user's own pending booking does NOT block (so retries work)
    """
    await _cleanup_stale_pending()
    cutoff = utc_now() - timedelta(minutes=PENDING_HOLD_MINUTES)
    taken: List[BedSel] = []
    for b in beds:
        # Always-blocking: paid/confirmed
        existing = await db.bookings.find_one({
            "floor": b.floor, "room": b.room, "bed": b.bed,
            "status": {"$in": ["paid", "confirmed"]},
        })
        if existing:
            taken.append(b)
            continue
        # Pending: block only if recent AND different user
        pending_other = await db.bookings.find_one({
            "floor": b.floor, "room": b.room, "bed": b.bed,
            "status": "pending", "payment_status": "unpaid",
            "created_at": {"$gte": cutoff},
            "user_id": {"$ne": current_user_id} if current_user_id else {"$exists": True},
        })
        if pending_other:
            taken.append(b)
    return taken


def _validate_bed_selection(beds: List[BedSel]) -> None:
    """Raise HTTPException if any bed coordinate is out of bounds."""
    floors = PG_CONFIG["room_structure"]
    for bed_sel in beds:
        if str(bed_sel.floor) not in floors:
            raise HTTPException(status_code=400, detail=f"Invalid floor {bed_sel.floor}")
        rooms_on_floor = floors[str(bed_sel.floor)]
        if bed_sel.room < 1 or bed_sel.room > len(rooms_on_floor):
            raise HTTPException(status_code=400, detail=f"Invalid room {bed_sel.room} on floor {bed_sel.floor}")
        if bed_sel.bed < 1 or bed_sel.bed > rooms_on_floor[bed_sel.room - 1]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid bed {bed_sel.bed} in room {bed_sel.room} on floor {bed_sel.floor}",
            )


def _calculate_booking_total(beds: List[BedSel]) -> tuple[int, int, int]:
    """Return (bed_total, advance, total) for the given bed selection."""
    bed_total = sum(bed_price(str(b.floor), b.room) for b in beds)
    advance = PG_CONFIG["advance"]
    return bed_total, advance, bed_total + advance


def _build_booking_doc(
    bed_sel: BedSel, *, idx: int, booking_group_id: str, user: dict,
    req: "BookingCreateReq", advance: int, now: datetime,
) -> dict:
    """Build a single MongoDB booking document. `idx` 0 attaches the deposit."""
    return {
        "booking_group_id": booking_group_id,
        "user_id": user["user_id"],
        "floor": bed_sel.floor,
        "room": bed_sel.room,
        "room_number": room_number(bed_sel.floor, bed_sel.room),
        "bed": bed_sel.bed,
        "sharing_type": PG_CONFIG["room_structure"][str(bed_sel.floor)][bed_sel.room - 1],
        "monthly_rent": bed_price(str(bed_sel.floor), bed_sel.room),
        "advance": advance if idx == 0 else 0,
        "name": req.name,
        "phone": req.phone,
        "alt_phone": req.alt_phone,
        "email": req.email.lower(),
        "aadhaar_number": req.aadhaar_number,
        "join_date": req.join_date,
        "notes": req.notes,
        "photo_url": req.photo_url,
        "aadhaar_url": req.aadhaar_url,
        "status": "pending",
        "payment_status": "unpaid",
        "razorpay_order_id": "",
        "razorpay_payment_id": "",
        "created_at": now,
    }


@app.post("/api/bookings")
async def create_booking(req: BookingCreateReq, user: dict = Depends(require_user)) -> dict:
    # Preconditions
    if not user.get("rules_accepted"):
        raise HTTPException(status_code=403, detail="Please accept PG rules first")
    if not req.beds:
        raise HTTPException(status_code=400, detail="Select at least one bed")
    if len(req.beds) > PG_CONFIG["max_beds_per_booking"]:
        raise HTTPException(status_code=400, detail=f"Max {PG_CONFIG['max_beds_per_booking']} beds per booking")

    _validate_bed_selection(req.beds)

    taken = await _are_beds_free(req.beds, current_user_id=user["user_id"])
    if taken:
        raise HTTPException(
            status_code=409,
            detail="Some beds are already booked: " + ", ".join(
                f"F{t.floor}R{room_number(t.floor, t.room)}B{t.bed}" for t in taken
            ),
        )

    bed_total, advance, total = _calculate_booking_total(req.beds)
    booking_group_id = f"bk_{uuid.uuid4().hex[:14]}"
    now = utc_now()
    docs = [
        _build_booking_doc(bed_sel, idx=i, booking_group_id=booking_group_id,
                           user=user, req=req, advance=advance, now=now)
        for i, bed_sel in enumerate(req.beds)
    ]
    await db.bookings.insert_many(docs)

    return {
        "booking_group_id": booking_group_id,
        "beds": [bed_sel.model_dump() for bed_sel in req.beds],
        "bed_total": bed_total,
        "advance": advance,
        "total": total,
    }


@app.get("/api/bookings/my")
async def my_bookings(user: dict = Depends(require_user)) -> dict:
    items = [serialize(d) async for d in db.bookings.find({"user_id": user["user_id"]}).sort("created_at", -1)]
    return {"items": items}


@app.get("/api/bookings/group/{group_id}")
async def get_booking_group(group_id: str, user: dict = Depends(require_user)) -> dict:
    items = [serialize(d) async for d in db.bookings.find({"booking_group_id": group_id})]
    if not items:
        raise HTTPException(status_code=404, detail="Booking not found")
    if user["role"] != "admin" and items[0]["user_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"items": items}


@app.post("/api/bookings/group/{group_id}/cancel")
async def cancel_group(group_id: str, user: dict = Depends(require_user)) -> dict:
    items = await db.bookings.find({"booking_group_id": group_id}).to_list(length=None)
    if not items:
        raise HTTPException(status_code=404, detail="Booking not found")
    if user["role"] != "admin" and items[0]["user_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    if items[0].get("payment_status") == "paid":
        raise HTTPException(status_code=400, detail="Cannot cancel a paid booking. Contact admin.")
    await db.bookings.update_many({"booking_group_id": group_id}, {"$set": {"status": "cancelled"}})
    return {"ok": True}


@app.post("/api/uploads/photo")
async def upload_photo(file: UploadFile = File(...), user: dict = Depends(require_user)) -> dict:
    """Upload a guest photo (jpg/png/webp, max 5 MB)."""
    raw = await file.read()
    try:
        url = save_uploaded_file(file.filename or "photo.jpg", raw, ALLOWED_IMG)
        return {"url": url, "filename": file.filename, "size": len(raw)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/uploads/aadhaar")
async def upload_aadhaar(file: UploadFile = File(...), user: dict = Depends(require_user)) -> dict:
    """Upload Aadhaar card (jpg/png/webp/pdf, max 5 MB)."""
    raw = await file.read()
    try:
        url = save_uploaded_file(file.filename or "aadhaar.jpg", raw, ALLOWED_DOC)
        return {"url": url, "filename": file.filename, "size": len(raw)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


async def _generate_receipt_for_group(booking_group_id: str) -> Optional[str]:
    """Pull bookings + PG config and produce a PDF receipt. Returns public URL or None."""
    items = await db.bookings.find({"booking_group_id": booking_group_id}).to_list(length=None)
    if not items:
        return None
    try:
        url = generate_receipt(booking_group_id, PG_CONFIG, items)
        await db.bookings.update_many(
            {"booking_group_id": booking_group_id},
            {"$set": {"receipt_url": url}},
        )
        return url
    except Exception:
        return None


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

pdf_path = os.path.join(
    BASE_DIR,
    "uploads",
    "receipts",
    f"{group_id}.pdf"
)
async def download_receipt(group_id: str, user: dict = Depends(require_user)) -> FileResponse:
    """Return the PDF receipt for a paid booking group."""
    items = await db.bookings.find({"booking_group_id": group_id}).to_list(length=None)
    if not items:
        raise HTTPException(status_code=404, detail="Booking not found")
    if user["role"] != "admin" and items[0]["user_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    if items[0].get("payment_status") != "paid":
        raise HTTPException(status_code=400, detail="Payment not completed")

    # (Re)generate if missing
    existing_url = items[0].get("receipt_url", "")
    pdf_path = f"/app/backend/uploads/receipts/{group_id}.pdf"
    if not existing_url or not os.path.exists(pdf_path):
        await _generate_receipt_for_group(group_id)

    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=500, detail="Receipt generation failed")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"SVPG_Receipt_{group_id}.pdf",
    )


# ---------- Razorpay ----------
@app.get("/api/payments/config")
async def payment_config() -> dict:
    return {"key_id": RZP_KEY_ID, "is_placeholder": IS_PLACEHOLDER_RZP}


@app.post("/api/payments/order/{group_id}")
async def create_order(group_id: str, user: dict = Depends(require_user)) -> dict:
    items = await db.bookings.find({"booking_group_id": group_id}).to_list(length=None)
    if not items or items[0]["user_id"] != user["user_id"]:
        raise HTTPException(status_code=404, detail="Booking not found")
    total = sum(b["monthly_rent"] for b in items) + items[0].get("advance", 0)
    amount_paise = int(total) * 100

    if IS_PLACEHOLDER_RZP or not razorpay_client:
        order_id = f"order_mock_{uuid.uuid4().hex[:14]}"
        await db.bookings.update_many(
            {"booking_group_id": group_id},
            {"$set": {"razorpay_order_id": order_id}},
        )
        return {
            "order_id": order_id, "amount": amount_paise, "currency": "INR",
            "key_id": RZP_KEY_ID, "is_mock": True,
        }

    order = razorpay_client.order.create({
        "amount": amount_paise, "currency": "INR",
        "receipt": group_id[:40], "payment_capture": 1,
    })
    await db.bookings.update_many(
        {"booking_group_id": group_id},
        {"$set": {"razorpay_order_id": order["id"]}},
    )
    return {
        "order_id": order["id"], "amount": amount_paise, "currency": "INR",
        "key_id": RZP_KEY_ID, "is_mock": False,
    }


@app.post("/api/payments/verify")
async def verify_payment(req: PaymentVerifyReq, user: dict = Depends(require_user)) -> dict:
    items = await db.bookings.find({"booking_group_id": req.booking_group_id}).to_list(length=None)
    if not items or items[0]["user_id"] != user["user_id"]:
        raise HTTPException(status_code=404, detail="Booking not found")

    if IS_PLACEHOLDER_RZP or not razorpay_client:
        await db.bookings.update_many(
            {"booking_group_id": req.booking_group_id},
            {"$set": {
                "razorpay_payment_id": req.razorpay_payment_id,
                "razorpay_signature": req.razorpay_signature,
                "payment_status": "paid", "status": "paid", "paid_at": utc_now(),
            }},
        )
        receipt_url = await _generate_receipt_for_group(req.booking_group_id)
        await _ensure_rent_schedule(req.booking_group_id)
        return {"ok": True, "mock": True, "receipt_url": receipt_url}

    body = f"{req.razorpay_order_id}|{req.razorpay_payment_id}".encode()
    expected = hmac.new(RZP_KEY_SECRET.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, req.razorpay_signature):
        raise HTTPException(status_code=400, detail="Invalid payment signature")
    await db.bookings.update_many(
        {"booking_group_id": req.booking_group_id},
        {"$set": {
            "razorpay_payment_id": req.razorpay_payment_id,
            "razorpay_signature": req.razorpay_signature,
            "payment_status": "paid", "status": "paid", "paid_at": utc_now(),
        }},
    )
    receipt_url = await _generate_receipt_for_group(req.booking_group_id)
    await _ensure_rent_schedule(req.booking_group_id)
    return {"ok": True, "receipt_url": receipt_url}


async def _mark_group_paid_by_order(order_id: str, payment_id: str) -> None:
    bk = await db.bookings.find_one({"razorpay_order_id": order_id})
    if not bk or bk.get("payment_status") == "paid":
        return
    await db.bookings.update_many(
        {"razorpay_order_id": order_id},
        {"$set": {
            "razorpay_payment_id": payment_id,
            "payment_status": "paid", "status": "paid",
            "paid_at": utc_now(), "paid_via": "webhook",
        }},
    )
    # Generate receipt + rent schedule for webhook-confirmed payments too
    await _generate_receipt_for_group(bk["booking_group_id"])
    await _ensure_rent_schedule(bk["booking_group_id"])


# ---------- Rent schedule & reminders ----------
def _next_n_months(start_iso: str, n: int = 12) -> List[str]:
    """Return list of YYYY-MM strings for the next N months from join date."""
    try:
        y, m, _ = (start_iso or utc_now().date().isoformat()).split("-")
        y, m = int(y), int(m)
    except Exception:
        d = utc_now()
        y, m = d.year, d.month
    result = []
    for i in range(n):
        mm = (m - 1 + i) % 12 + 1
        yy = y + (m - 1 + i) // 12
        result.append(f"{yy:04d}-{mm:02d}")
    return result


async def _ensure_rent_schedule(booking_group_id: str) -> int:
    """Idempotently create 12 monthly rent_payments entries for a paid booking group."""
    items = await db.bookings.find({"booking_group_id": booking_group_id}).to_list(length=None)
    if not items or items[0].get("payment_status") != "paid":
        return 0
    existing = await db.rent_payments.count_documents({"booking_group_id": booking_group_id})
    if existing > 0:
        return 0
    first = items[0]
    total_rent = sum(b.get("monthly_rent", 0) for b in items)
    months = _next_n_months(first.get("join_date") or "", 12)
    docs = []
    for i, mo in enumerate(months):
        docs.append({
            "booking_group_id": booking_group_id,
            "user_id": first["user_id"],
            "name": first.get("name", ""),
            "phone": first.get("phone", ""),
            "email": first.get("email", ""),
            "month": mo,
            "amount": total_rent,
            "status": "paid" if i == 0 else "pending",  # first month covered by initial payment
            "paid_at": utc_now() if i == 0 else None,
            "payment_method": "razorpay" if i == 0 else "",
            "payment_reference": first.get("razorpay_payment_id", "") if i == 0 else "",
            "created_at": utc_now(),
        })
    if docs:
        await db.rent_payments.insert_many(docs)
    return len(docs)


def _send_email_via_sendgrid(to_email: str, subject: str, body_html: str) -> dict:
    """Send email via SendGrid if SENDGRID_API_KEY env var configured. Returns status dict."""
    api_key = os.environ.get("SENDGRID_API_KEY", "")
    from_email = os.environ.get("SENDGRID_FROM_EMAIL", "noreply@svpg.in")
    if not api_key:
        return {"sent": False, "reason": "SENDGRID_API_KEY not configured – reminder logged only"}
    try:
        import httpx as _httpx
        r = _httpx.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "personalizations": [{"to": [{"email": to_email}], "subject": subject}],
                "from": {"email": from_email, "name": "Sri Vengamamba PG"},
                "content": [{"type": "text/html", "value": body_html}],
            },
            timeout=10,
        )
        if r.status_code in (200, 202):
            return {"sent": True}
        return {"sent": False, "reason": f"SendGrid {r.status_code}: {r.text[:120]}"}
    except Exception as e:
        return {"sent": False, "reason": f"SendGrid exception: {e}"}


def _build_reminder_html(rent: dict) -> str:
    return (
        f"<p>Dear {rent.get('name','Resident')},</p>"
        f"<p>This is a friendly reminder that your rent of <b>INR {rent.get('amount',0):,}</b> "
        f"for the month <b>{rent['month']}</b> is pending.</p>"
        f"<p>Please pay at the earliest to avoid late charges. Thank you.</p>"
        f"<p>– Sri Vengamamba PG Management</p>"
    )


async def _send_reminder_for_rent(rent: dict, triggered_by: str = "auto-cron") -> dict:
    """Helper to send + log a reminder for one rent row. Returns send_result."""
    subject = f"Rent reminder – {rent['month']} – Sri Vengamamba PG"
    body = _build_reminder_html(rent)
    send_result = _send_email_via_sendgrid(rent.get("email", ""), subject, body)
    await db.reminders.insert_one({
        "rent_id": str(rent.get("_id", "")),
        "booking_group_id": rent.get("booking_group_id"),
        "user_id": rent.get("user_id"),
        "to_email": rent.get("email"),
        "month": rent.get("month"),
        "channel": "email",
        "subject": subject,
        "body": body,
        "sent_at": utc_now(),
        "sent": send_result.get("sent", False),
        "reason": send_result.get("reason", ""),
        "triggered_by": triggered_by,
    })
    await db.rent_payments.update_one(
        {"_id": rent["_id"]},
        {"$set": {"last_reminded_at": utc_now()}},
    )
    return send_result


async def _auto_send_monthly_reminders() -> int:
    """Cron job — sends reminders to every resident with pending rent for the current month.
    Triggered on the 5th of every month at 09:00 IST."""
    current_month = utc_now().strftime("%Y-%m")
    sent_count = 0
    async for rent in db.rent_payments.find({"month": current_month, "status": "pending"}):
        try:
            res = await _send_reminder_for_rent(rent, triggered_by="auto-cron")
            if res.get("sent"):
                sent_count += 1
        except Exception:
            continue
    return sent_count


@app.post("/api/payments/webhook")
async def razorpay_webhook(request: Request) -> dict:
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    if not RZP_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook secret not configured")
    expected = hmac.new(RZP_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
    try:
        payload = _json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    event = payload.get("event", "")
    payment = (payload.get("payload") or {}).get("payment", {}).get("entity") or {}
    order_id = payment.get("order_id", "")
    payment_id = payment.get("id", "")
    await db.webhook_events.insert_one({
        "event": event, "order_id": order_id, "payment_id": payment_id,
        "received_at": utc_now(), "raw": payload,
    })
    if event in ("payment.captured", "payment.authorized", "order.paid") and order_id:
        await _mark_group_paid_by_order(order_id, payment_id)
    elif event == "payment.failed" and order_id:
        await db.bookings.update_many(
            {"razorpay_order_id": order_id, "payment_status": {"$ne": "paid"}},
            {"$set": {"payment_status": "failed", "razorpay_payment_id": payment_id}},
        )
    return {"ok": True, "event": event}


# ---------- Admin ----------
@app.get("/api/admin/stats")
async def admin_stats(user: dict = Depends(require_admin)) -> dict:
    # Total beds in property
    total_beds = sum(sum(rooms) for rooms in PG_CONFIG["room_structure"].values())
    booked = await db.bookings.count_documents({"status": {"$in": ["paid", "confirmed"]}})
    paid_bookings = await db.bookings.count_documents({"payment_status": "paid"})
    revenue_cursor = db.bookings.aggregate([
        {"$match": {"payment_status": "paid"}},
        {"$group": {"_id": None, "total": {"$sum": "$monthly_rent"}, "advance": {"$sum": "$advance"}}},
    ])
    revenue = {"total_rent": 0, "advance": 0}
    async for r in revenue_cursor:
        revenue = {"total_rent": r.get("total", 0), "advance": r.get("advance", 0)}

    # Current month rent summary
    current_month = utc_now().strftime("%Y-%m")
    rent_paid = await db.rent_payments.count_documents({"month": current_month, "status": "paid"})
    rent_pending = await db.rent_payments.count_documents({"month": current_month, "status": "pending"})
    rent_collected_cursor = db.rent_payments.aggregate([
        {"$match": {"month": current_month, "status": "paid"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ])
    rent_collected_month = 0
    async for r in rent_collected_cursor:
        rent_collected_month = r.get("total", 0)
    rent_pending_cursor = db.rent_payments.aggregate([
        {"$match": {"month": current_month, "status": "pending"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ])
    rent_pending_amount = 0
    async for r in rent_pending_cursor:
        rent_pending_amount = r.get("total", 0)

    return {
        "total_beds": total_beds,
        "booked_beds": booked,
        "available_beds": total_beds - booked,
        "occupancy_pct": round(booked * 100 / total_beds, 1) if total_beds else 0,
        "users": await db.users.count_documents({}),
        "guests": await db.users.count_documents({"role": "guest"}),
        "paid_bookings": paid_bookings,
        "pending_bookings": await db.bookings.count_documents({"status": "pending"}),
        "revenue_rent": revenue["total_rent"],
        "revenue_advance": revenue["advance"],
        "current_month": current_month,
        "rent_paid_count": rent_paid,
        "rent_pending_count": rent_pending,
        "rent_collected_month": rent_collected_month,
        "rent_pending_amount": rent_pending_amount,
    }


@app.get("/api/admin/bookings")
async def admin_bookings(user: dict = Depends(require_admin)) -> dict:
    items = [serialize(d) async for d in db.bookings.find().sort("created_at", -1).limit(500)]
    return {"items": items}


@app.get("/api/admin/users")
async def admin_users(user: dict = Depends(require_admin)) -> dict:
    items = [serialize(d) async for d in db.users.find().sort("created_at", -1).limit(500)]
    return {"items": items}


@app.post("/api/admin/bookings/{booking_id}/confirm")
async def admin_confirm(booking_id: str, user: dict = Depends(require_admin)) -> dict:
    if not ObjectId.is_valid(booking_id):
        raise HTTPException(status_code=404, detail="Booking not found")
    res = await db.bookings.update_one(
        {"_id": ObjectId(booking_id)},
        {"$set": {"status": "confirmed"}},
    )
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Booking not found")
    return {"ok": True}


@app.post("/api/admin/bookings/{booking_id}/cancel")
async def admin_cancel(booking_id: str, user: dict = Depends(require_admin)) -> dict:
    if not ObjectId.is_valid(booking_id):
        raise HTTPException(status_code=404, detail="Booking not found")
    res = await db.bookings.update_one(
        {"_id": ObjectId(booking_id)},
        {"$set": {"status": "cancelled"}},
    )
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Booking not found")
    return {"ok": True}


@app.get("/api/admin/webhook_events")
async def admin_webhook_events(user: dict = Depends(require_admin)) -> dict:
    items = [serialize(d) async for d in db.webhook_events.find().sort("received_at", -1).limit(100)]
    return {"items": items, "count": len(items)}


# ---------- Residents (admin) ----------
@app.get("/api/admin/residents")
async def admin_residents(user: dict = Depends(require_admin)) -> dict:
    """Return paid residents grouped by booking_group_id with their beds + docs."""
    pipeline = [
        {"$match": {"payment_status": "paid", "status": {"$ne": "checked_out"}}},
        {"$sort": {"created_at": -1}},
    ]
    bookings = [serialize(d) async for d in db.bookings.aggregate(pipeline)]
    groups: dict = {}
    for b in bookings:
        gid = b["booking_group_id"]
        if gid not in groups:
            groups[gid] = {
                "booking_group_id": gid,
                "name": b.get("name", ""),
                "phone": b.get("phone", ""),
                "alt_phone": b.get("alt_phone", ""),
                "email": b.get("email", ""),
                "aadhaar_number": b.get("aadhaar_number", ""),
                "join_date": b.get("join_date", ""),
                "photo_url": b.get("photo_url", ""),
                "aadhaar_url": b.get("aadhaar_url", ""),
                "status": b.get("status", ""),
                "created_at": b.get("created_at", ""),
                "beds": [],
                "monthly_rent": 0,
            }
        groups[gid]["beds"].append({
            "floor": b["floor"], "room": b["room_number"], "bed": b["bed"],
            "sharing": b.get("sharing_type"),
        })
        groups[gid]["monthly_rent"] += b.get("monthly_rent", 0)
    return {"items": list(groups.values())}


# ---------- Rent matrix (admin) ----------
@app.get("/api/admin/rent_matrix")
async def admin_rent_matrix(months: int = 6, user: dict = Depends(require_admin)) -> dict:
    """Return rent payment matrix: residents × months. months param = last N months centered on current."""
    # Build month window: 1 past, current, N-2 future (or just 6 future from earliest join date)
    rent_rows = [serialize(d) async for d in db.rent_payments.find().sort([("user_id", 1), ("month", 1)])]
    if not rent_rows:
        return {"months": [], "residents": []}

    all_months = sorted(set(r["month"] for r in rent_rows))[:months]
    # Group by booking_group_id
    by_group: dict = {}
    for r in rent_rows:
        gid = r["booking_group_id"]
        if gid not in by_group:
            by_group[gid] = {
                "booking_group_id": gid,
                "name": r.get("name", ""),
                "phone": r.get("phone", ""),
                "email": r.get("email", ""),
                "amount": r.get("amount", 0),
                "months": {},  # month → {status, id, paid_at}
            }
        by_group[gid]["months"][r["month"]] = {
            "id": r["id"],
            "status": r["status"],
            "paid_at": r.get("paid_at"),
            "payment_method": r.get("payment_method", ""),
            "reminded": bool(r.get("last_reminded_at")),
        }
    return {"months": all_months, "residents": list(by_group.values())}


@app.post("/api/admin/rent/{rent_id}/mark_paid")
async def admin_mark_rent_paid(rent_id: str, req: MarkPaidReq, user: dict = Depends(require_admin)) -> dict:
    if not ObjectId.is_valid(rent_id):
        raise HTTPException(status_code=404, detail="Not found")
    res = await db.rent_payments.update_one(
        {"_id": ObjectId(rent_id)},
        {"$set": {
            "status": "paid",
            "paid_at": utc_now(),
            "payment_method": req.payment_method,
            "payment_reference": req.payment_reference,
            "marked_paid_by": user["user_id"],
        }},
    )
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


@app.post("/api/admin/rent/{rent_id}/send_reminder")
async def admin_send_rent_reminder(rent_id: str, req: SendReminderReq, user: dict = Depends(require_admin)) -> dict:
    if not ObjectId.is_valid(rent_id):
        raise HTTPException(status_code=404, detail="Not found")
    rent = await db.rent_payments.find_one({"_id": ObjectId(rent_id)})
    if not rent:
        raise HTTPException(status_code=404, detail="Not found")
    send_result = await _send_reminder_for_rent(rent, triggered_by=user["user_id"])
    return {"ok": True, "sent": send_result.get("sent", False), "reason": send_result.get("reason", "")}


@app.get("/api/admin/reminders")
async def admin_list_reminders(user: dict = Depends(require_admin)) -> dict:
    items = [serialize(d) async for d in db.reminders.find().sort("sent_at", -1).limit(200)]
    return {"items": items}


@app.post("/api/admin/reminders/send_overdue")
async def admin_send_all_overdue(user: dict = Depends(require_admin)) -> dict:
    """Send reminders to every resident with pending rent for the current month or earlier."""
    current_month = utc_now().strftime("%Y-%m")
    queued = 0
    sent = 0
    failed = 0
    async for rent in db.rent_payments.find({"month": {"$lte": current_month}, "status": "pending"}):
        queued += 1
        try:
            res = await _send_reminder_for_rent(rent, triggered_by=user["user_id"])
            if res.get("sent"):
                sent += 1
            else:
                failed += 1
        except Exception:
            failed += 1
    return {"queued": queued, "sent": sent, "logged_only": failed}


@app.get("/api/admin/scheduler/status")
async def admin_scheduler_status(user: dict = Depends(require_admin)) -> dict:
    """Show next scheduled run for the monthly auto-reminder cron."""
    sched = getattr(app.state, "scheduler", None)
    if not sched:
        return {"running": False}
    jobs = []
    for j in sched.get_jobs():
        jobs.append({
            "id": j.id,
            "next_run": j.next_run_time.isoformat() if j.next_run_time else None,
            "trigger": str(j.trigger),
        })
    return {"running": sched.running, "jobs": jobs}


# ---------- Checkout (admin) ----------
@app.post("/api/admin/bookings/group/{group_id}/checkout")
async def admin_checkout(group_id: str, user: dict = Depends(require_admin)) -> dict:
    """Mark a resident as checked out. Frees their beds + closes future rent payments."""
    items = await db.bookings.find({"booking_group_id": group_id}).to_list(length=None)
    if not items:
        raise HTTPException(status_code=404, detail="Booking not found")
    now = utc_now()
    await db.bookings.update_many(
        {"booking_group_id": group_id},
        {"$set": {"status": "checked_out", "checked_out_at": now}},
    )
    # Cancel future pending rent payments
    await db.rent_payments.update_many(
        {"booking_group_id": group_id, "status": "pending"},
        {"$set": {"status": "cancelled", "cancelled_at": now}},
    )
    return {"ok": True, "checked_out_beds": len(items)}
