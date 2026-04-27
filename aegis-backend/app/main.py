"""
Aegis AI Content Moderation Service - Main Application

This is the core FastAPI application that exposes REST endpoints
for content moderation. It provides image analysis capabilities
to detect potentially harmful content such as violence, nudity,
hate symbols, and other policy violations.

Usage:
    Run with Uvicorn:
        uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

    API Documentation:
        - Swagger UI: http://localhost:8000/docs
        - ReDoc: http://localhost:8000/redoc
"""

from fastapi import FastAPI, File, HTTPException, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import logging

# -----------------------------------------------------------------------------
# Logging configuration for Presentation Mode
# Format: [AI-DECISION] {Timestamp} - {Type} - {Result} - {Details}
logging.basicConfig(
    level=logging.INFO,
    format='[AI-DECISION] %(asctime)s - %(message)s',
)
logger = logging.getLogger("aegis")

# Import Pydantic models for request/response schemas
from app.models.analysis import AnalysisResponse

# Import the vision service for image analysis
from app.services.vision_service import VisionService
from app.services.metadata_service import MetadataService
from app.services.profanity_service import analyze_profanity
from app.services.audio_service import AudioService


# =============================================================================
# Application Configuration
# =============================================================================

# Supported image MIME types
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/bmp",
}

# Maximum file size (10 MB)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB in bytes

# Global singleton service instances so heavy models load only once.
vision_service = VisionService()
audio_service = AudioService()
metadata_service = MetadataService()


# =============================================================================
# FastAPI Application Instance
# =============================================================================

app = FastAPI(
    title="Aegis AI Moderation Service",
    description="""
    🛡️ **Aegis** is a high-performance AI-powered content moderation service.
    
    ## Features
    
    * **Image Analysis** - Detect harmful content in uploaded images
    * **Multiple Categories** - Violence, nudity, hate symbols, weapons, drugs
    * **Bounding Boxes** - Precise location of detected content
    * **Confidence Scores** - Probability scores for each detection
    
    ## Quick Start
    
    Upload an image to the `/analyze-image` endpoint to get started.
    """,
    version="0.1.0",
    contact={
        "name": "Aegis Team",
        "email": "aegis@example.com",
    },
    license_info={
        "name": "MIT",
    },
)


# =============================================================================
# Middleware Configuration
# =============================================================================

# Enable CORS for frontend integration
# NOTE: In production, restrict origins to your specific domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for production!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# API Models & Endpoints
# =============================================================================

class MetadataRequest(BaseModel):
    title: str = Field(..., min_length=1)


class AudioTextRequest(BaseModel):
    text: str = Field(default="", description="Transcribed audio or subtitles text")

@app.get(
    "/",
    summary="Health Check",
    description="Returns a simple message to verify the service is running.",
    tags=["Health"],
)
async def root() -> dict:
    """
    Root endpoint for health checks and service verification.
    
    Returns:
        dict: A welcome message confirming the service is operational.
    """
    return {
        "message": "Aegis AI Service is running",
        "version": "0.1.0",
        "status": "healthy"
    }


@app.get(
    "/health",
    summary="Detailed Health Check",
    description="Returns detailed health status of the service.",
    tags=["Health"],
)
async def health_check() -> dict:
    """
    Detailed health check endpoint for monitoring systems.
    
    Returns:
        dict: Detailed health status including service components.
    """
    return {
        "status": "healthy",
        "service": "aegis-ai-moderation",
        "version": "0.1.0",
        "components": {
            "api": "operational",
                "vision_service": "operational (yolov11)",
        }
    }


@app.post(
    "/analyze-image",
    response_model=AnalysisResponse,
    summary="Analyze Image Content",
    description="""
    Upload an image to analyze it for potentially harmful content.
    
    The service will scan the image and return:
    - A list of detected content categories
    - Confidence scores for each detection
    - Bounding boxes indicating where content was found
    
    **Supported formats:** JPEG, PNG, WebP, GIF, BMP
    
    **Max file size:** 10 MB
    """,
    tags=["Analysis"],
    responses={
        200: {
            "description": "Successful analysis",
            "content": {
                "application/json": {
                    "example": {
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
                                "box": None
                            }
                        ]
                    }
                }
            }
        },
        400: {"description": "Invalid file format or size"},
        500: {"description": "Internal server error during analysis"},
    }
)
async def analyze_image(
    image: UploadFile = File(
        ...,
        description="Image file to analyze (JPEG, PNG, WebP, GIF, or BMP)"
    ),
    sensitivity: float = Form(0.75),
    filter_nudity: bool = Form(True),
    filter_violence: bool = Form(True),
) -> AnalysisResponse:
    """
    Analyze an uploaded image for potentially harmful content.
    
    This endpoint accepts image uploads and processes them through
    the AI vision service to detect content that may violate policies.
    
    Args:
        image: The uploaded image file. Must be a valid image format
              and under the maximum file size limit.
    
    Returns:
        AnalysisResponse: Contains analysis status and list of detections,
                         each with a label, confidence score, and optional
                         bounding box coordinates.
    
    Raises:
        HTTPException: 400 if file format is invalid or file is too large
        HTTPException: 500 if analysis fails due to internal error
    """
    # =========================================================================
    # Step 1: Validate the uploaded file
    # =========================================================================
    
    # Check if the content type is supported
    if image.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_format",
                "message": f"Unsupported file format: {image.content_type}",
                "allowed_formats": list(ALLOWED_CONTENT_TYPES),
            }
        )
    
    # =========================================================================
    # Step 2: Read the image bytes from the upload
    # =========================================================================
    
    try:
        # Read the entire file into memory
        image_bytes = await image.read()
        
        # Validate file size
        if len(image_bytes) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "file_too_large",
                    "message": f"File size exceeds maximum limit of {MAX_FILE_SIZE // (1024*1024)} MB",
                    "size_bytes": len(image_bytes),
                    "max_bytes": MAX_FILE_SIZE,
                }
            )
        
        # Validate minimum file size (likely corrupted if too small)
        if len(image_bytes) < 100:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_file",
                    "message": "File appears to be empty or corrupted",
                }
            )
            
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Handle unexpected errors during file reading
        raise HTTPException(
            status_code=500,
            detail={
                "error": "read_error",
                "message": f"Failed to read uploaded file: {str(e)}",
            }
        )
    
    # =========================================================================
    # Step 3: Analyze the image using the vision service
    # =========================================================================
    
    try:
        # Run inference via the singleton YOLO service instance.
        results = vision_service.analyze_image(
            image_bytes=image_bytes,
            sensitivity=float(sensitivity),
            filter_nudity=bool(filter_nudity),
            filter_violence=bool(filter_violence),
        )
        # Presentation log: log any notable categories (e.g., Violence)
        for det in results:
            details = f"label={det.label}, score={det.score:.2f}"
            label_lower = det.label.lower()
            result_str = "BLOCK" if ("violence" in label_lower or "nudity" in label_lower or label_lower == "kiss") else "ALLOW"
            logger.info(f"Vision - {result_str} - {details}")
        return AnalysisResponse(status="success", analysis=results)
        
    except Exception as e:
        # Handle unexpected errors during analysis
        raise HTTPException(
            status_code=500,
            detail={
                "error": "analysis_error",
                "message": f"Failed to analyze image: {str(e)}",
            }
        )


@app.post(
    "/analyze-metadata",
    summary="Analyze media metadata against blocked themes",
    tags=["Metadata"],
)
async def analyze_media_metadata(request: MetadataRequest) -> dict:
    """
    Query TMDb for genres/keywords, then compare against blocked themes.
    Returns BLOCK/ALLOW decision and reason.
    """
    try:
        result = await metadata_service.check_thematic_content(request.title)
        decision = result.get("decision", result.get("status", "ALLOW"))
        reason = result.get("reason", "")
        logger.info(f"Metadata - {decision} - title={request.title}, reason={reason}")
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "metadata_error", "message": str(e)},
        )


@app.post(
    "/analyze-text",
    summary="Analyze transcribed audio/subtitle text for profanity",
    tags=["Text"],
)
async def analyze_text(request: AudioTextRequest) -> dict:
    """
    Scan provided text for profanity and return action/duration.
    """
    try:
        return analyze_profanity(request.text or "")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "text_error", "message": str(e)},
        )


@app.post(
    "/analyze-audio",
    summary="Transcribe audio and analyze for profanity",
    tags=["Audio"],
)
async def analyze_audio(
    audio: UploadFile = File(..., description="Short audio chunk to analyze"),
    filter_profanity: bool = Form(True),
) -> dict:
    """
    Accepts an audio file, transcribes with Whisper, then runs profanity analysis.
    """
    try:
        audio_bytes = await audio.read()
        if not audio_bytes or len(audio_bytes) < 16:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_audio", "message": "Audio file is empty or too small"},
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "read_error", "message": f"Failed to read uploaded audio: {str(e)}"},
        )

    try:
        audio_result = await audio_service.analyze_audio(audio_bytes)
        text = audio_result.get("transcript", "")
        if not filter_profanity:
            audio_result["action"] = "ALLOW"
            audio_result["matched_words"] = []
        else:
            audio_result["action"] = audio_result.get("action", "ALLOW")

        action = audio_result.get("action", "ALLOW")
        logger.info(f"Audio - {action} - text: '{text[:120]}'")
        return audio_result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "audio_analysis_error", "message": str(e)},
        )
# =============================================================================
# Application Startup/Shutdown Events
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """
    Execute startup tasks when the application begins.
    
    In Phase 2, this will be used to:
    - Load AI models into memory
    - Warm up GPU if available
    - Initialize connection pools
    """
    print("🛡️ Aegis AI Moderation Service starting up...")
    print("📝 API documentation available at /docs")
    # TODO: Phase 2 - Load AI models here


@app.on_event("shutdown")
async def shutdown_event():
    """
    Execute cleanup tasks when the application shuts down.
    
    In Phase 2, this will be used to:
    - Unload AI models
    - Close database connections
    - Clean up temporary files
    """
    print("🛡️ Aegis AI Moderation Service shutting down...")
    # TODO: Phase 2 - Cleanup resources here


# =============================================================================
# Development Entry Point
# =============================================================================

if __name__ == "__main__":
    # This allows running the app directly with: python -m app.main
    # However, using uvicorn directly is recommended for development
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Enable hot-reload for development
    )
