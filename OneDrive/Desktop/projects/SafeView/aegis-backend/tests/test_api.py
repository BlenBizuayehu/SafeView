"""Deterministic API tests for Aegis endpoints using mocked vision inference."""

import io
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.analysis import AnalysisResult, BoundingBox


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def anyio_backend():
    """Specify the async backend for pytest-asyncio."""
    return "asyncio"


@pytest.fixture
async def client():
    """
    Create an async HTTP client for testing.
    
    Yields:
        AsyncClient: An httpx client configured to test the FastAPI app.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def create_test_image(size: int = 1000) -> io.BytesIO:
    """
    Create a minimal valid PNG image for testing.
    
    Args:
        size: Approximate size of the test data in bytes.
    
    Returns:
        BytesIO: A file-like object containing fake image data.
    """
    # Minimal PNG header (8 bytes) + IHDR chunk structure
    # This is enough to pass basic validation while being small
    png_header = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
        0x00, 0x00, 0x00, 0x0D,  # IHDR chunk length
        0x49, 0x48, 0x44, 0x52,  # "IHDR"
        0x00, 0x00, 0x00, 0x01,  # width: 1
        0x00, 0x00, 0x00, 0x01,  # height: 1
        0x08, 0x02,              # bit depth: 8, color type: RGB
        0x00, 0x00, 0x00,        # compression, filter, interlace
        0x90, 0x77, 0x53, 0xDE,  # CRC
    ])
    
    # Pad with additional data to reach desired size
    padding = bytes([0x00] * max(0, size - len(png_header)))
    
    return io.BytesIO(png_header + padding)


def mock_detection_results() -> list[AnalysisResult]:
    """Return a stable set of two detections for deterministic tests."""
    return [
        AnalysisResult(
            label="person",
            score=0.92,
            box=BoundingBox(x=0.10, y=0.20, width=0.30, height=0.40),
        ),
        AnalysisResult(
            label="car",
            score=0.81,
            box=BoundingBox(x=0.50, y=0.45, width=0.35, height=0.30),
        ),
    ]


# =============================================================================
# Root Endpoint Tests
# =============================================================================

class TestRootEndpoint:
    """Tests for the root (/) health check endpoint."""
    
    @pytest.mark.anyio
    async def test_root_returns_welcome_message(self, client: AsyncClient):
        """Test that root endpoint returns expected welcome message."""
        response = await client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert "Aegis" in data["message"]
        assert data["status"] == "healthy"
    
    @pytest.mark.anyio
    async def test_root_contains_version(self, client: AsyncClient):
        """Test that root endpoint includes version information."""
        response = await client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "version" in data
        assert data["version"] == "0.1.0"


# =============================================================================
# Health Check Endpoint Tests
# =============================================================================

class TestHealthEndpoint:
    """Tests for the /health endpoint."""
    
    @pytest.mark.anyio
    async def test_health_returns_detailed_status(self, client: AsyncClient):
        """Test that health endpoint returns detailed component status."""
        response = await client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert "components" in data
        assert "api" in data["components"]
        assert "vision_service" in data["components"]


# =============================================================================
# Image Analysis Endpoint Tests
# =============================================================================

class TestAnalyzeImageEndpoint:
    """Tests for the POST /analyze-image endpoint."""
    
    @pytest.mark.anyio
    async def test_analyze_multiple_detections(
        self, client: AsyncClient, mocker
    ):
        """Scenario 1: API returns two mocked detections."""
        mocked_analyze = mocker.patch(
            "app.main.vision_service.analyze_image",
            return_value=mock_detection_results(),
        )
        test_image = create_test_image(1000)
        response = await client.post(
            "/analyze-image",
            files={"image": ("test.png", test_image, "image/png")}
        )

        mocked_analyze.assert_called_once()
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["analysis"]) == 2
        assert data["analysis"][0]["label"] == "person"
        assert data["analysis"][0]["score"] == 0.92
        assert data["analysis"][0]["box"] == {
            "x": 0.1,
            "y": 0.2,
            "width": 0.3,
            "height": 0.4,
        }
        assert data["analysis"][1]["label"] == "car"
        assert data["analysis"][1]["score"] == 0.81

    @pytest.mark.anyio
    async def test_analyze_zero_detections(self, client: AsyncClient, mocker):
        """Scenario 2: API returns an empty analysis list."""
        mocked_analyze = mocker.patch(
            "app.main.vision_service.analyze_image",
            return_value=[],
        )
        test_image = create_test_image(1000)
        response = await client.post(
            "/analyze-image",
            files={"image": ("test.png", test_image, "image/png")}
        )

        mocked_analyze.assert_called_once()
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["analysis"] == []

    @pytest.mark.anyio
    async def test_analyze_model_error_returns_500(
        self, client: AsyncClient, mocker
    ):
        """Scenario 3: vision service exception maps to HTTP 500."""
        mocked_analyze = mocker.patch(
            "app.main.vision_service.analyze_image",
            side_effect=Exception("Model Failed"),
        )
        test_image = create_test_image(1000)
        response = await client.post(
            "/analyze-image",
            files={"image": ("test.png", test_image, "image/png")}
        )

        mocked_analyze.assert_called_once()
        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["error"] == "analysis_error"

    @pytest.mark.anyio
    async def test_analyze_rejects_invalid_format(self, client: AsyncClient, mocker):
        """Test that invalid file formats are rejected."""
        mocked_analyze = mocker.patch("app.main.vision_service.analyze_image")
        # Send a text file instead of an image
        text_file = io.BytesIO(b"This is not an image file")
        response = await client.post(
            "/analyze-image",
            files={"image": ("test.txt", text_file, "text/plain")}
        )
        mocked_analyze.assert_not_called()
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert data["detail"]["error"] == "invalid_format"

    @pytest.mark.anyio
    async def test_analyze_rejects_empty_file(self, client: AsyncClient, mocker):
        """Test that empty/tiny files are rejected."""
        mocked_analyze = mocker.patch("app.main.vision_service.analyze_image")
        # Create a file that's too small to be valid
        tiny_file = io.BytesIO(b"tiny")
        response = await client.post(
            "/analyze-image",
            files={"image": ("test.png", tiny_file, "image/png")}
        )
        mocked_analyze.assert_not_called()
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert data["detail"]["error"] == "invalid_file"

    @pytest.mark.anyio
    async def test_analyze_accepts_jpeg(self, client: AsyncClient, mocker):
        """Test that JPEG images are accepted."""
        mocked_analyze = mocker.patch(
            "app.main.vision_service.analyze_image",
            return_value=mock_detection_results(),
        )
        test_image = create_test_image(1000)
        response = await client.post(
            "/analyze-image",
            files={"image": ("test.jpg", test_image, "image/jpeg")}
        )
        mocked_analyze.assert_called_once()
        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_analyze_accepts_webp(self, client: AsyncClient, mocker):
        """Test that WebP images are accepted."""
        mocked_analyze = mocker.patch(
            "app.main.vision_service.analyze_image",
            return_value=mock_detection_results(),
        )
        test_image = create_test_image(1000)
        response = await client.post(
            "/analyze-image",
            files={"image": ("test.webp", test_image, "image/webp")}
        )
        mocked_analyze.assert_called_once()
        assert response.status_code == 200


# =============================================================================
# Response Model Validation Tests
# =============================================================================

class TestResponseModels:
    """Tests for response model validation and structure."""
    
    @pytest.mark.anyio
    async def test_analysis_response_matches_schema(self, client: AsyncClient, mocker):
        """Test that response matches the AnalysisResponse Pydantic model."""
        mocked_analyze = mocker.patch(
            "app.main.vision_service.analyze_image",
            return_value=mock_detection_results(),
        )
        test_image = create_test_image(1000)
        response = await client.post(
            "/analyze-image",
            files={"image": ("test.png", test_image, "image/png")}
        )

        mocked_analyze.assert_called_once()
        assert response.status_code == 200
        data = response.json()
        
        # Import and validate against Pydantic model
        from app.models.analysis import AnalysisResponse
        
        # This will raise ValidationError if structure is incorrect
        validated = AnalysisResponse(**data)
        
        assert validated.status == "success"
        assert isinstance(validated.analysis, list)


# =============================================================================
# API Documentation Tests
# =============================================================================

class TestAPIDocumentation:
    """Tests for API documentation endpoints."""
    
    @pytest.mark.anyio
    async def test_openapi_schema_available(self, client: AsyncClient):
        """Test that OpenAPI schema is accessible."""
        response = await client.get("/openapi.json")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "openapi" in data
        assert "info" in data
        assert data["info"]["title"] == "Aegis AI Moderation Service"
    
    @pytest.mark.anyio
    async def test_swagger_ui_available(self, client: AsyncClient):
        """Test that Swagger UI documentation is accessible."""
        response = await client.get("/docs")
        
        # Should redirect or return HTML
        assert response.status_code == 200
    
    @pytest.mark.anyio
    async def test_redoc_available(self, client: AsyncClient):
        """Test that ReDoc documentation is accessible."""
        response = await client.get("/redoc")
        
        assert response.status_code == 200
