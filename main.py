#!/usr/bin/env python3

import logging
from contextlib import asynccontextmanager
from urllib.parse import unquote
import tempfile
import os
import mimetypes

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict

from config_service import ConfigService
from file_service import FileService
from download_service import DownloadService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global service instances (singletons as requested)
config_service = ConfigService()
file_service = FileService(config_service)

# Pydantic models for API responses
class DownloadResponse(BaseModel):
    success: bool
    message: str
    filename: Optional[str] = None
    file_path: Optional[str] = None
    error: Optional[str] = None

class DownloadRequest(BaseModel):
    url: HttpUrl
    custom_filename: Optional[str] = None

class StatusResponse(BaseModel):
    status: str
    download_directory: str
    supported_domains: Dict[str, list]
    endpoints: Dict[str, str]

# Application lifecycle management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    logger.info(f"Starting pyDownloader API on port {config_service.get_config().application_port}")
    
    # Verify configuration on startup
    try:
        config = config_service.get_config()
        logger.info(f"Download directory configured: {config.download_directory}")
    except Exception as e:
        logger.error(f"Configuration error on startup: {e}")
        raise
    
    yield
    
    logger.info("Shutting down pyDownloader API...")

# Initialize FastAPI app
app = FastAPI(
    title="pyDownloader API",
    description="A microservice for downloading content from various websites. Supports both streaming files to clients (/download) and saving files to server (/save).",
    version="1.0.0",
    lifespan=lifespan
)

def get_download_service() -> DownloadService:
    """Dependency injection for DownloadService - creates new instance per request."""
    return DownloadService()

def get_media_type(file_path: str) -> str:
    """Get the media type for a file based on its extension."""
    media_type, _ = mimetypes.guess_type(file_path)
    return media_type or 'application/octet-stream'

async def stream_file_and_cleanup(file_path: str, temp_dir: str) -> FileResponse:
    """
    Stream a file to the client and clean up the temporary directory after streaming.
    
    Args:
        file_path: Path to the file to stream
        temp_dir: Temporary directory to clean up after streaming
    
    Returns:
        FileResponse object for streaming the file
    """
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Downloaded file not found")
    
    # Get media type for proper Content-Type header
    media_type = get_media_type(file_path)
    
    # Get filename for Content-Disposition header
    filename = os.path.basename(file_path)
    
    # Create a background task to clean up the temporary directory after streaming
    def cleanup_temp_dir():
        try:
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temporary directory: {temp_dir}")
        except Exception as e:
            logger.error(f"Failed to clean up temporary directory {temp_dir}: {e}")
    
    # Return FileResponse with cleanup task
    response = FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename,
        background=BackgroundTasks()
    )
    response.background.add_task(cleanup_temp_dir)
    
    return response

@app.get("/", response_model=StatusResponse)
async def root():
    """Root endpoint providing service status and information."""
    try:
        config = config_service.get_config()
        
        # Get supported domains from download service
        download_service = DownloadService()
        supported_domains = {
            "youtube_dl": [
                'youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com',
                'twitch.tv', 'tiktok.com', 'instagram.com', 'twitter.com', 'x.com'
            ],
            "gallery_dl": [
                'reddit.com', 'imgur.com', 'deviantart.com', 'artstation.com',
                'pixiv.net', 'danbooru.donmai.us', 'gelbooru.com'
            ],
            "generic": ["Any HTTP/HTTPS URL"]
        }
        
        endpoints_info = {
            "/download": "Stream downloaded files directly to client",
            "/save": "Download and save files to server's configured directory",
            "/files": "List files in server's download directory",
            "/health": "Service health check"
        }
        
        return StatusResponse(
            status="running",
            download_directory=config.download_directory,
            supported_domains=supported_domains,
            endpoints=endpoints_info
        )
    except Exception as e:
        logger.error(f"Error in root endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/save/{url_to_download:path}", response_model=DownloadResponse)
async def save_from_url(
    url_to_download: str,
    download_service: DownloadService = Depends(get_download_service),
    custom_filename: Optional[str] = None,
    request: Request = None
):
    """
    Download content from the specified URL and save it to the server's configured directory.
    
    Args:
        url_to_download: The URL to download from (URL-encoded)
        custom_filename: Optional custom filename for the downloaded content
    """
    try:
        # URL decode the path parameter
        decoded_url = unquote(url_to_download)
        
        # Reconstruct the full URL with query parameters
        # FastAPI strips query parameters from path, so we need to rebuild
        if request and request.url.query:
            full_url = f"{decoded_url}?{request.url.query}"
        else:
            full_url = decoded_url
            
        logger.info(f"Download request for URL: {full_url}")
        logger.info(f"Raw URL path parameter: {url_to_download}")
        logger.info(f"Query string: {request.url.query if request else 'None'}")
        logger.info(f"Reconstructed URL length: {len(full_url)}")
        
        # Get download directory from config
        config = config_service.get_config()
        download_dir = config.download_directory
        
        # Create temporary directory for this download
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info(f"Using temporary directory: {temp_dir}")
            
            # Perform the download
            result = await download_service.download(full_url, temp_dir)
            
            if not result.success:
                logger.error(f"Download failed: {result.error}")
                return DownloadResponse(
                    success=False,
                    message="Download failed",
                    error=result.error
                )
            
            # Handle the downloaded content
            final_path = None
            final_filename = None
            
            if result.file_path and os.path.exists(result.file_path):
                if os.path.isfile(result.file_path):
                    # Single file downloaded
                    final_path = file_service.move_file(
                        result.file_path, 
                        custom_filename or result.filename
                    )
                    if final_path:
                        final_filename = os.path.basename(final_path)
                elif os.path.isdir(result.file_path):
                    # Directory of files downloaded (e.g., gallery-dl)
                    # Move all files from temp directory to download directory
                    moved_files = []
                    for item in os.listdir(result.file_path):
                        item_path = os.path.join(result.file_path, item)
                        if os.path.isfile(item_path):
                            moved_path = file_service.move_file(item_path)
                            if moved_path:
                                moved_files.append(os.path.basename(moved_path))
                    
                    if moved_files:
                        final_filename = f"{len(moved_files)} files downloaded"
                        final_path = download_dir
            else:
                # Fallback: check if anything was downloaded to temp_dir
                temp_files = [f for f in os.listdir(temp_dir) if os.path.isfile(os.path.join(temp_dir, f))]
                if temp_files:
                    moved_files = []
                    for temp_file in temp_files:
                        temp_path = os.path.join(temp_dir, temp_file)
                        moved_path = file_service.move_file(temp_path, custom_filename if len(temp_files) == 1 else None)
                        if moved_path:
                            moved_files.append(os.path.basename(moved_path))
                    
                    if moved_files:
                        if len(moved_files) == 1:
                            final_filename = moved_files[0]
                            final_path = os.path.join(download_dir, final_filename)
                        else:
                            final_filename = f"{len(moved_files)} files downloaded"
                            final_path = download_dir
            
            if final_path:
                logger.info(f"Download completed successfully: {final_filename}")
                return DownloadResponse(
                    success=True,
                    message="Download completed successfully",
                    filename=final_filename,
                    file_path=final_path
                )
            else:
                logger.error("Failed to save downloaded content")
                return DownloadResponse(
                    success=False,
                    message="Download completed but failed to save files",
                    error="File operation failed"
                )
                
    except Exception as e:
        logger.error(f"Unexpected error during download: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/save", response_model=DownloadResponse)
async def save_from_body(
    request: DownloadRequest,
    download_service: DownloadService = Depends(get_download_service)
):
    """
    Alternative endpoint that accepts URL in request body and saves to server's configured directory.
    
    Args:
        request: DownloadRequest containing URL and optional custom filename
    """
    return await save_from_url(
        str(request.url),
        download_service,
        request.custom_filename
    )

@app.get("/download/{url_to_download:path}")
async def download_from_url(
    url_to_download: str,
    download_service: DownloadService = Depends(get_download_service),
    custom_filename: Optional[str] = None,
    request: Request = None
):
    """
    Download content from the specified URL and stream it directly to the client.
    
    Args:
        url_to_download: The URL to download from (URL-encoded)
        custom_filename: Optional custom filename for the downloaded content
    
    Returns:
        The downloaded file streamed directly to the client
    """
    try:
        # URL decode the path parameter
        decoded_url = unquote(url_to_download)
        
        # Reconstruct the full URL with query parameters
        if request and request.url.query:
            full_url = f"{decoded_url}?{request.url.query}"
        else:
            full_url = decoded_url
            
        logger.info(f"Download (streaming) request for URL: {full_url}")
        
        # Create temporary directory for this download
        temp_dir = tempfile.mkdtemp()
        logger.info(f"Using temporary directory for streaming: {temp_dir}")
        
        try:
            # Perform the download
            result = await download_service.download(full_url, temp_dir)
            
            if not result.success:
                logger.error(f"Download failed: {result.error}")
                # Clean up temp directory on failure
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise HTTPException(status_code=400, detail=f"Download failed: {result.error}")
            
            # Find the downloaded file to stream
            file_to_stream = None
            
            if result.file_path and os.path.exists(result.file_path):
                if os.path.isfile(result.file_path):
                    # Single file downloaded
                    file_to_stream = result.file_path
                elif os.path.isdir(result.file_path):
                    # Directory downloaded - find the first media file
                    for item in os.listdir(result.file_path):
                        item_path = os.path.join(result.file_path, item)
                        if os.path.isfile(item_path):
                            file_to_stream = item_path
                            break
            else:
                # Fallback: check temp directory for any files
                temp_files = [f for f in os.listdir(temp_dir) if os.path.isfile(os.path.join(temp_dir, f))]
                if temp_files:
                    file_to_stream = os.path.join(temp_dir, temp_files[0])
            
            if not file_to_stream:
                # Clean up temp directory
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise HTTPException(status_code=404, detail="No downloadable content found")
            
            # Handle custom filename if provided
            if custom_filename:
                # Rename the file to use custom filename
                file_ext = os.path.splitext(file_to_stream)[1]
                if not custom_filename.endswith(file_ext):
                    custom_filename += file_ext
                new_path = os.path.join(os.path.dirname(file_to_stream), custom_filename)
                os.rename(file_to_stream, new_path)
                file_to_stream = new_path
            
            # Stream the file to client with cleanup
            return await stream_file_and_cleanup(file_to_stream, temp_dir)
            
        except Exception as e:
            # Clean up temp directory on any exception
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during download: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/download")
async def download_from_body(
    request: DownloadRequest,
    download_service: DownloadService = Depends(get_download_service),
    req: Request = None
):
    """
    Alternative endpoint that accepts URL in request body and streams file directly to client.
    
    Args:
        request: DownloadRequest containing URL and optional custom filename
    
    Returns:
        The downloaded file streamed directly to the client
    """
    return await download_from_url(
        str(request.url),
        download_service,
        request.custom_filename,
        req
    )

@app.get("/files")
async def list_files(pattern: str = "*"):
    """List files in the download directory."""
    try:
        files = file_service.list_files(pattern)
        file_info = []
        
        for file_path in files:
            filename = os.path.basename(file_path)
            info = file_service.get_file_info(filename)
            if info:
                file_info.append(info)
        
        return {
            "files": file_info,
            "count": len(file_info),
            "download_directory": file_service.get_download_directory()
        }
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/files/{filename}")
async def delete_file(filename: str):
    """Delete a specific file from the download directory."""
    try:
        success = file_service.delete_file(filename)
        if success:
            return {"message": f"File '{filename}' deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail=f"File '{filename}' not found")
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Verify configuration is accessible
        config = config_service.get_config()
        
        # Check if download directory is accessible
        download_dir_accessible = os.path.exists(config.download_directory) and os.access(config.download_directory, os.W_OK)
        
        return {
            "status": "healthy",
            "download_directory_accessible": download_dir_accessible,
            "download_directory": config.download_directory
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    
    # Get configuration for port
    config = config_service.get_config()
    
    # Configuration for development
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.application_port,
        reload=True,
        log_level="info"
    )
