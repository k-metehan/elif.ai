"""
cityconcierge.io MVP Backend
Voice-in, voice-out nöbetçi eczane assistant for Bahçeşehir
"""

import json
import os
import time
import uuid
import secrets
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

from openai import AsyncOpenAI
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from analytics import log_query, classify_topic_local, get_stats

# Load environment variables
load_dotenv()

# Initialize async OpenAI client
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not found in environment variables")
client = AsyncOpenAI(api_key=api_key)

# Directory for temporary audio responses
AUDIO_DIR = Path(__file__).parent / "audio_responses"
AUDIO_DIR.mkdir(exist_ok=True)

DATA_DIR = Path(__file__).parent / "data"

def load_data_file(filename: str) -> dict:
    """Load a JSON data file with graceful fallback if missing."""
    path = DATA_DIR / filename
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"WARNING: {filename} not found, using empty data")
        return {}
    except json.JSONDecodeError:
        print(f"WARNING: {filename} is invalid JSON, using empty data")
        return {}

def check_data_freshness(data: dict, name: str, max_age_days: int = 2) -> str:
    """Return a warning string if data is stale, empty string if fresh."""
    last_updated = data.get("last_updated", "")
    if not last_updated:
        return f"({name} verisi tarih bilgisi yok — doğruluğunu teyit edin)"
    try:
        updated_date = datetime.strptime(last_updated, "%Y-%m-%d")
        age = (datetime.now() - updated_date).days
        if age > max_age_days:
            return f"({name} verisi {age} gün önce güncellendi — güncel olmayabilir)"
    except ValueError:
        pass
    return ""

PHARMACY_DATA = load_data_file("pharmacies.json")
EVENTS_DATA = load_data_file("events.json")
CLOSURES_DATA = load_data_file("closures.json")
WATER_DATA = load_data_file("water.json")
EMERGENCY_DATA = load_data_file("emergency.json")
ELECTRICITY_DATA = load_data_file("electricity.json")
WEATHER_DATA = load_data_file("weather.json")
EARTHQUAKES_DATA = load_data_file("earthquakes.json")
GAS_DATA = load_data_file("gas.json")

# In-memory conversation storage (per session)
conversation_history: Dict[str, List[Dict]] = {}

app = FastAPI(title="CityConcierge", version="0.1.0")

# CORS for frontend
ALLOWED_ORIGINS = [
    "https://elif.cityconcierge.io",
    "https://cityconcierge.io",
    "http://localhost:8080",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth setup for admin dashboard
security = HTTPBasic()

ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")
BRANDING_MODE = os.getenv("BRANDING_MODE", "cityconcierge")

if not ADMIN_USER or not ADMIN_PASS:
    import warnings
    warnings.warn(
        "ADMIN_USER and ADMIN_PASS not set — admin dashboard disabled. "
        "Set them in .env to enable /admin.",
        stacklevel=2,
    )


def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    """HTTP Basic Auth for admin dashboard."""
    if not ADMIN_USER or not ADMIN_PASS:
        raise HTTPException(
            status_code=503,
            detail="Admin dashboard not configured. Set ADMIN_USER and ADMIN_PASS in .env",
        )
    correct_user = secrets.compare_digest(credentials.username.encode(), ADMIN_USER.encode())
    correct_pass = secrets.compare_digest(credentials.password.encode(), ADMIN_PASS.encode())
    if not correct_user or not correct_pass:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

SYSTEM_PROMPT = """Sen Bahçeşehir'in en bilgili komşususun. Adın Elif.
Samimi, sıcak ve yardımseversin. Kısa cevap ver — 2-3 cümle yeter.

Kurallar:
- SADECE sana verilen verileri kullan. Tahmin yapma, uydurma.
- Her eczane cevabında telefon numarasını söyle.
- Her zaman "gitmeden önce bir arayın" de — nöbetçi değişebiliyor.
- Gece nöbetinde kapı kapalı olabilir, zili çalmalarını hatırlat.
- Su kesintisi veya yol kapanışı sorulursa, etkilenen bölgeyi ve süreyi söyle.
- Etkinlik sorulursa, tarih, saat ve yer bilgisini ver.
- Bilmiyorsan: "Hmm, bunu bilmiyorum ama Beyaz Masa'yı arayabilirsin: 153"
- İstanbul Türkçesi kullan: "şurada", "hemen", "bir bakayım"

ACİL DURUM KURALLARI:
- "deprem", "yangın", "sel", "acil", "toplanma alanı" gibi kelimeler duyarsan:
  1. Sakin ve güven veren bir tonda cevap ver
  2. En yakın toplanma alanını söyle
  3. İlgili acil numarayı ver (112 genel acil)
  4. Şu uyarıyı MUTLAKA ekle: "Bu bilgiler referans amaçlıdır. Acil durumda mutlaka 112'yi arayın."
- Asla "panik yapmayın" deme. Bunun yerine: "Sakin olun, size yardımcı olayım."
- Hava durumu sorulursa: güncel sıcaklık, hissedilen sıcaklık ve yarının tahminini ver.
- Elektrik kesintisi sorulursa: etkilenen bölge ve süreyi söyle. BEDAŞ arıza: 186.
- Doğalgaz kesintisi sorulursa: İGDAŞ acil hat: 187.
- Deprem sorulursa: son 24 saatteki yakın depremleri söyle.
  Küçük (< 4.0): "hissedilmeyecek büyüklükte" de.
  Büyük (>= 4.0): acil durum protokolüne geç.
- Başka bir konuda bilgi verirken, o gün vatandaşı etkileyen bir kesinti varsa
  (su, elektrik, gaz) proaktif olarak bahset.

Bugünün tarihi: {today}
{freshness_warnings}

=== ECZANE VERİLERİ ===
{pharmacy_data}

=== ETKİNLİKLER ===
{events_data}

=== YOL KAPANIŞLARI ===
{closures_data}

=== SU KESİNTİLERİ ===
{water_data}

=== ACİL DURUM BİLGİLERİ ===
{emergency_data}

=== HAVA DURUMU ===
{weather_data}

=== ELEKTRİK KESİNTİLERİ ===
{electricity_data}

=== DOĞALGAZ KESİNTİLERİ ===
{gas_data}

=== SON DEPREMLER ===
{earthquakes_data}
"""


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/pharmacies")
async def get_pharmacies():
    """Get all pharmacy data (for debugging)"""
    return PHARMACY_DATA


@app.get("/api/weather")
async def get_weather():
    """Get weather data"""
    return WEATHER_DATA


@app.get("/api/earthquakes")
async def get_earthquakes():
    """Get earthquake data"""
    return EARTHQUAKES_DATA


@app.get("/api/events")
async def get_events():
    """Get events data"""
    return EVENTS_DATA


@app.get("/api/water")
async def get_water():
    """Get water outage data"""
    return WATER_DATA


@app.get("/api/electricity")
async def get_electricity():
    """Get electricity outage data"""
    return ELECTRICITY_DATA


@app.get("/api/gas")
async def get_gas():
    """Get gas outage data"""
    return GAS_DATA


@app.post("/api/voice")
async def process_voice(
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),
    session_id: Optional[str] = Form(None)
):
    """
    Main voice pipeline:
    1. Receive audio blob (WebM)
    2. Transcribe with Whisper
    3. Generate response with GPT-4o-mini (with conversation history)
    4. Synthesize with TTS
    5. Return both text and audio
    """
    try:
        start_time = time.time()
        
        # Generate unique session if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Initialize conversation history for this session
        if session_id not in conversation_history:
            conversation_history[session_id] = []
        
        # Read audio file
        audio_content = await audio.read()
        
        # Step 1: Transcribe with Whisper
        transcript = await transcribe_audio(audio_content)
        print(f"User said: {transcript}")
        
        # Step 2: Generate response with GPT (with history)
        response_text = await generate_response(transcript, session_id)
        print(f"Elif responds: {response_text}")
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        # Step 3: Synthesize with TTS
        audio_response = await synthesize_speech(response_text)
        
        # Clean up old audio files (keep last 20)
        existing = sorted(AUDIO_DIR.glob("response_*.mp3"), key=lambda p: p.stat().st_mtime)
        for old_file in existing[:-20]:
            old_file.unlink(missing_ok=True)

        # Save audio with unique filename
        audio_filename = f"response_{uuid.uuid4().hex[:8]}.mp3"
        temp_audio_path = AUDIO_DIR / audio_filename
        temp_audio_path.write_bytes(audio_response)
        
        # Store in conversation history
        conversation_history[session_id].append({
            "timestamp": datetime.now().isoformat(),
            "user": transcript,
            "assistant": response_text
        })
        
        # Limit history to last 10 exchanges
        if len(conversation_history[session_id]) > 10:
            conversation_history[session_id] = conversation_history[session_id][-10:]
        
        # Log query in background (never blocks response)
        topic, is_emergency = classify_topic_local(transcript)
        background_tasks.add_task(
            log_query,
            session_id=session_id,
            user_query=transcript,
            response=response_text,
            topic=topic,
            is_emergency=is_emergency,
            response_time_ms=elapsed_ms,
            source="voice"
        )
        
        return JSONResponse({
            "success": True,
            "transcript": transcript,
            "response": response_text,
            "audio_url": f"/api/voice/{audio_filename}",
            "session_id": session_id
        })
        
    except Exception as e:
        print(f"Error in voice pipeline: {e}")
        raise HTTPException(status_code=500, detail="Bir hata oluştu. Lütfen tekrar deneyin.")


@app.post("/api/text")
async def process_text(
    background_tasks: BackgroundTasks,
    text: str = Form(...),
    session_id: Optional[str] = Form(None)
):
    """Text-based query endpoint (for testing without microphone)"""
    try:
        start_time = time.time()
        
        if not session_id:
            session_id = str(uuid.uuid4())
        if session_id not in conversation_history:
            conversation_history[session_id] = []

        response_text = await generate_response(text, session_id)
        
        elapsed_ms = int((time.time() - start_time) * 1000)

        conversation_history[session_id].append({
            "timestamp": datetime.now().isoformat(),
            "user": text,
            "assistant": response_text
        })
        if len(conversation_history[session_id]) > 10:
            conversation_history[session_id] = conversation_history[session_id][-10:]

        # Log query in background (never blocks response)
        topic, is_emergency = classify_topic_local(text)
        background_tasks.add_task(
            log_query,
            session_id=session_id,
            user_query=text,
            response=response_text,
            topic=topic,
            is_emergency=is_emergency,
            response_time_ms=elapsed_ms,
            source="text"
        )

        return JSONResponse({
            "success": True,
            "transcript": text,
            "response": response_text,
            "session_id": session_id
        })
    except Exception as e:
        print(f"Error in text pipeline: {e}")
        raise HTTPException(status_code=500, detail="Bir hata oluştu. Lütfen tekrar deneyin.")


@app.get("/api/voice/{filename}")
async def get_audio_response(filename: str):
    """Serve the generated audio response"""
    # Prevent path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    temp_audio_path = AUDIO_DIR / filename
    if not temp_audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(temp_audio_path, media_type="audio/mpeg")


async def transcribe_audio(audio_content: bytes) -> str:
    """Transcribe audio using OpenAI Whisper"""
    import io

    # Create a file-like object from bytes
    audio_file = io.BytesIO(audio_content)
    audio_file.name = "audio.webm"

    response = await client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        language="tr"
    )

    return response.text


async def generate_response(user_query: str, session_id: str) -> str:
    """Generate response using GPT-4o-mini with conversation history"""

    today = datetime.now().strftime("%Y-%m-%d")

    # Format all data for the prompt
    pharmacy_info = json.dumps(PHARMACY_DATA, ensure_ascii=False, indent=2)
    events_info = json.dumps(EVENTS_DATA, ensure_ascii=False, indent=2)
    closures_info = json.dumps(CLOSURES_DATA, ensure_ascii=False, indent=2)
    water_info = json.dumps(WATER_DATA, ensure_ascii=False, indent=2)
    emergency_info = json.dumps(EMERGENCY_DATA, ensure_ascii=False, indent=2)
    weather_info = json.dumps(WEATHER_DATA, ensure_ascii=False, indent=2) if WEATHER_DATA else "Hava durumu verisi yok."
    electricity_info = json.dumps(ELECTRICITY_DATA, ensure_ascii=False, indent=2) if ELECTRICITY_DATA else "Elektrik kesintisi verisi yok."
    gas_info = json.dumps(GAS_DATA, ensure_ascii=False, indent=2) if GAS_DATA else "Doğalgaz verisi yok."
    earthquakes_info = json.dumps(EARTHQUAKES_DATA, ensure_ascii=False, indent=2) if EARTHQUAKES_DATA else "Deprem verisi yok."

    # Check data freshness
    warnings = []
    for data, name in [
        (PHARMACY_DATA, "Eczane"),
        (EVENTS_DATA, "Etkinlik"),
        (CLOSURES_DATA, "Yol kapanışı"),
        (WATER_DATA, "Su kesintisi"),
        (ELECTRICITY_DATA, "Elektrik kesintisi"),
        (GAS_DATA, "Doğalgaz kesintisi"),
    ]:
        w = check_data_freshness(data, name)
        if w:
            warnings.append(w)
    # Weather and earthquake freshness use tighter thresholds
    w = check_data_freshness(WEATHER_DATA, "Hava durumu", max_age_days=1)
    if w:
        warnings.append(w)
    w = check_data_freshness(EARTHQUAKES_DATA, "Deprem", max_age_days=1)
    if w:
        warnings.append(w)
    freshness_warnings = "\n".join(warnings) if warnings else ""

    system_message = SYSTEM_PROMPT.format(
        today=today,
        freshness_warnings=freshness_warnings,
        pharmacy_data=pharmacy_info,
        events_data=events_info,
        closures_data=closures_info,
        water_data=water_info,
        emergency_data=emergency_info,
        weather_data=weather_info,
        electricity_data=electricity_info,
        gas_data=gas_info,
        earthquakes_data=earthquakes_info,
    )

    # Build messages with conversation history
    messages = [{"role": "system", "content": system_message}]

    if session_id in conversation_history:
        for exchange in conversation_history[session_id][-3:]:
            messages.append({"role": "user", "content": exchange["user"]})
            messages.append({"role": "assistant", "content": exchange["assistant"]})

    messages.append({"role": "user", "content": user_query})

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.3,
        max_tokens=300,  # increased from 200 — more topics = slightly longer answers
    )

    return response.choices[0].message.content


def numbers_to_turkish(text: str) -> str:
    """Convert numbers to written Turkish words so TTS pronounces them correctly.
    Handles phone numbers (digit-by-digit) and regular numbers (as words)."""
    import re

    ones = ["", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]
    tens = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"]
    digits_tr = ["sıfır", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]

    def number_to_words(n):
        """Convert integer to Turkish words."""
        if n == 0:
            return "sıfır"
        if n < 0:
            return "eksi " + number_to_words(-n)

        parts = []
        if n >= 1000:
            thousands = n // 1000
            if thousands == 1:
                parts.append("bin")
            else:
                parts.append(number_to_words(thousands) + " bin")
            n %= 1000
        if n >= 100:
            hundreds = n // 100
            if hundreds == 1:
                parts.append("yüz")
            else:
                parts.append(ones[hundreds] + " yüz")
            n %= 100
        if n >= 10:
            parts.append(tens[n // 10])
            n %= 10
        if n > 0:
            parts.append(ones[n])

        return " ".join(parts)

    def phone_to_words(match):
        """Read phone numbers digit by digit."""
        phone = match.group(0)
        # Read each digit individually with spaces
        spoken = " ".join(digits_tr[int(d)] for d in phone if d.isdigit())
        return spoken

    # First handle phone-like patterns (sequences of digits with spaces/dashes/parens)
    # e.g. "0212 555 1234" or "(0212) 555-1234" or "112"
    # Phone pattern: 3+ digits possibly separated by spaces, dashes, parens
    text = re.sub(r'[\(\)]', '', text)  # Remove parens around area codes
    text = re.sub(r'\b(\d[\d\s\-]{6,})\b', phone_to_words, text)

    # Then handle remaining standalone numbers (1-4 digits, likely quantities)
    def standalone_number(match):
        n = int(match.group(0))
        if n > 9999:
            # Very large numbers: read digit by digit
            return " ".join(digits_tr[int(d)] for d in match.group(0))
        return number_to_words(n)

    text = re.sub(r'\b(\d{1,4})\b', standalone_number, text)

    return text


async def synthesize_speech(text: str) -> bytes:
    """Synthesize speech using OpenAI TTS"""

    # Convert numbers to Turkish words to prevent TTS slurring
    tts_text = numbers_to_turkish(text)

    response = await client.audio.speech.create(
        model="tts-1",
        voice="nova",
        input=tts_text
    )

    return response.content


# Admin endpoints
@app.get("/api/admin/stats")
async def admin_stats(username: str = Depends(verify_admin)):
    """Get analytics stats (requires auth)."""
    return get_stats()


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(username: str = Depends(verify_admin)):
    """Serve admin dashboard HTML."""
    html_path = Path(__file__).parent / "admin.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


# Branding endpoint
@app.get("/api/branding")
async def get_branding():
    """Return branding config for the frontend."""
    if BRANDING_MODE == "basaksehir":
        return {
            "mode": "basaksehir",
            "title": "Başakşehir Belediyesi",
            "subtitle": "Sesli Asistan Pilotu",
            "accent": "#004B93",
            "accent_hover": "#003a75",
            "accent_glow": "rgba(0,75,147,0.3)",
            "show_stripe": True,
            "stripe_color": "#004B93",
        }
    else:
        return {
            "mode": "cityconcierge",
            "title": "Elif",
            "subtitle": "Bahçeşehir'in sesli komşusu",
            "accent": "#0d7377",
            "accent_hover": "#00595c",
            "accent_glow": "rgba(13,115,119,0.3)",
            "show_stripe": False,
            "stripe_color": None,
        }


@app.get("/pitch/comparison", response_class=HTMLResponse)
async def pitch_comparison():
    """Serve the 153 comparison pitch page."""
    html_path = Path(__file__).parent / "pitch" / "comparison.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/pitch/whatsapp", response_class=HTMLResponse)
async def pitch_whatsapp():
    """Serve the WhatsApp mockup pitch page."""
    html_path = Path(__file__).parent / "pitch" / "whatsapp.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/data-sources")
async def data_sources():
    """Show what data sources are loaded — useful for demo transparency."""
    sources = []
    for name, data in [
        ("Eczane", PHARMACY_DATA),
        ("Etkinlik", EVENTS_DATA),
        ("Yol Kapanışı", CLOSURES_DATA),
        ("Su Kesintisi", WATER_DATA),
        ("Acil Durum", EMERGENCY_DATA),
    ]:
        source = data.get("source", "unknown")
        updated = data.get("last_updated", "unknown")
        freshness = check_data_freshness(data, name)
        sources.append({
            "name": name,
            "source": source,
            "last_updated": updated,
            "status": "stale" if freshness else "fresh",
            "warning": freshness or None,
        })
    return {"data_sources": sources, "total": len(sources)}


# ===== STATIC FILE SERVING =====
from fastapi.staticfiles import StaticFiles

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    PITCH_DIR = Path(__file__).parent / "pitch"
    if PITCH_DIR.exists():
        app.mount("/pitch", StaticFiles(directory=str(PITCH_DIR), html=True), name="pitch")
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
    print(f"Serving frontend from: {FRONTEND_DIR}")
else:
    print(f"WARNING: Frontend directory not found at {FRONTEND_DIR}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
