# SafeView Run Instructions

This guide explains how to run the three SafeView components for presentation:
- Backend (`aegis-backend`)
- Browser Extension (`safeview-browser-extension`)
- Mobile App (`safeview_mobile`)

## 1) Backend (FastAPI)

### Prerequisites
- Python 3.10+
- ffmpeg installed and in PATH (for Whisper audio transcription)

### Setup
```powershell
cd C:\Users\hp\OneDrive\Desktop\projects\SafeView\aegis-backend
python -m venv venv
.\venv\Scripts\Activate
pip install -r requirements.txt
```

### Environment Variables
Set these before starting the backend:

```powershell
# Required for metadata analysis against TMDb
$env:TMDB_API_KEY="your_tmdb_api_key_here"

# Optional for future OpenAI API integrations
$env:OPENAI_API_KEY="your_openai_api_key_here"
```

If `TMDB_API_KEY` is missing, metadata endpoint defaults to `ALLOW` by design.

### Run
```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### API Docs
- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 2) Browser Extension (Chrome MV3)

### Load Extension
1. Open Chrome: `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select:
   `C:\Users\hp\OneDrive\Desktop\projects\SafeView\safeview-browser-extension`

### Use
- Open extension popup.
- Toggle filtering on.
- Browse pages with images; extension sends frames to backend at `http://localhost:8000`.

---

## 3) Mobile App (Flutter + Native Android)

### Prerequisites
- Flutter SDK
- Android SDK / Emulator (API 29+ recommended)
- Backend running on host machine

### Setup & Run
```powershell
cd C:\Users\hp\OneDrive\Desktop\projects\SafeView\safeview_mobile
flutter pub get
flutter run
```

### Important Emulator Networking
- Android emulator accesses host `localhost` using `10.0.2.2`.
- Native service is configured to call:
  - `http://10.0.2.2:8000/analyze-image`
  - `http://10.0.2.2:8000/analyze-audio`
  - `http://10.0.2.2:8000/analyze-metadata`

### Permissions Flow
When pressing **Start Protection**:
1. Grant Overlay permission
2. Grant Screen Capture permission
3. Audio capture/muting and overlays start in foreground service

---

## 4) Presentation Mode (Live Logs)

- Backend logs AI decisions with `[AI-DECISION]` prefix.
- Mobile dashboard shows **Live Analysis Feed** from native service events.
- Metadata blocks have priority over blur overlays.

