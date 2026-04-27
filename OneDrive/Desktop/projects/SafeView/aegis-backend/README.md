# 🛡️ Aegis AI Content Moderation Service

A high-performance backend service for AI-powered content moderation, built with FastAPI.

## 📋 Overview

Aegis is a content moderation system designed to analyze images and detect potentially harmful content such as:

- 🔴 Violence
- 🔴 Nudity/NSFW content
- 🔴 Hate symbols
- 🔴 Weapons
- 🔴 Drug-related content

**Current Status:** Phase 1 (Mock Implementation)

> ⚠️ This is Phase 1 of the project. The AI models return **mock data** for development and testing purposes. Real AI inference will be implemented in Phase 2.

## 🚀 Quick Start

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)

### Installation

1. **Clone the repository** (or navigate to the project directory):

```bash
cd aegis-backend
```

2. **Create a virtual environment**:

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

3. **Install dependencies**:

```bash
pip install -r requirements.txt
```

4. **Run the server**:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

5. **Access the API documentation**:

Open your browser and navigate to:
- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

## 📁 Project Structure

```
aegis-backend/
├── app/
│   ├── __init__.py              # Package initialization
│   ├── main.py                  # FastAPI application & endpoints
│   ├── models/
│   │   ├── __init__.py
│   │   └── analysis.py          # Pydantic request/response models
│   └── services/
│       ├── __init__.py
│       └── vision_service.py    # AI analysis logic (mock in Phase 1)
├── tests/
│   ├── __init__.py
│   └── test_api.py              # API integration tests
├── .gitignore
├── requirements.txt
└── README.md
```

## 🔌 API Endpoints

### Health Check

```http
GET /
```

Returns a simple status message confirming the service is running.

**Response:**
```json
{
    "message": "Aegis AI Service is running",
    "version": "0.1.0",
    "status": "healthy"
}
```

### Analyze Image

```http
POST /analyze-image
```

Upload an image to analyze it for potentially harmful content.

**Request:**
- Content-Type: `multipart/form-data`
- Body: `image` (file) - The image to analyze

**Supported formats:** JPEG, PNG, WebP, GIF, BMP

**Response:**
```json
{
    "status": "success",
    "analysis": [
        {
            "label": "violence",
            "score": 0.87,
            "box": {
                "x": 0.1,
                "y": 0.2,
                "width": 0.3,
                "height": 0.4
            }
        },
        {
            "label": "safe",
            "score": 0.65,
            "box": null
        }
    ]
}
```

## 🧪 Running Tests

Run the test suite with pytest:

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ -v --cov=app --cov-report=html

# Run specific test file
pytest tests/test_api.py -v
```

## 📦 Dependencies

### Core
- **FastAPI** - Modern, fast web framework
- **Uvicorn** - Lightning-fast ASGI server
- **Pydantic** - Data validation using Python type annotations
- **python-multipart** - Multipart form data parsing

### Testing
- **pytest** - Testing framework
- **httpx** - Async HTTP client for testing
- **pytest-asyncio** - Async test support

### AI/ML (Phase 2)
- PyTorch
- OpenCV
- NumPy
- Pillow

## 🔧 Configuration

Environment variables can be set in a `.env` file:

```env
# Server
HOST=0.0.0.0
PORT=8000
DEBUG=true

# AI Models (Phase 2)
MODEL_PATH=./models
CONFIDENCE_THRESHOLD=0.5
```

## 🛣️ Roadmap

### Phase 1 (Current) ✅
- [x] Project structure setup
- [x] FastAPI application skeleton
- [x] Pydantic models for API
- [x] Mock analysis service
- [x] Basic API tests
- [x] API documentation

### Phase 2 (Planned)
- [ ] Integrate PyTorch models
- [ ] Implement real image analysis
- [ ] Add violence detection model
- [ ] Add NSFW detection model
- [ ] GPU acceleration support

### Phase 3 (Future)
- [ ] Batch processing API
- [ ] WebSocket streaming
- [ ] Model hot-swapping
- [ ] Prometheus metrics
- [ ] Redis caching

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Support

For questions or issues, please open a GitHub issue or contact the Aegis team.

---

Built with ❤️ using FastAPI
