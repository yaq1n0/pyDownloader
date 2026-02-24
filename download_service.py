# this files handles the downloading of files from various sources

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional
from urllib.parse import urlparse
import os

logger = logging.getLogger(__name__)

class DownloadResult:
    """Represents the result of a download operation."""
    def __init__(self, success: bool, file_path: Optional[str] = None, 
                 filename: Optional[str] = None, error: Optional[str] = None):
        self.success = success
        self.file_path = file_path
        self.filename = filename
        self.error = error

class BaseDownloader(ABC):
    """Abstract base class for all downloaders."""
    
    @abstractmethod
    async def download(self, url: str, output_dir: str) -> DownloadResult:
        """Download content from URL to output directory."""
        pass
    
    @abstractmethod
    def supports_url(self, url: str) -> bool:
        """Check if this downloader supports the given URL."""
        pass

class YoutubeDLDownloader(BaseDownloader):
    """Downloader for YouTube and other video sites using yt-dlp."""
    
    SUPPORTED_DOMAINS = [
        'youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com',
        'twitch.tv', 'tiktok.com', 'instagram.com', 'twitter.com', 'x.com'
    ]
    
    def supports_url(self, url: str) -> bool:
        try:
            domain = urlparse(url).netloc.lower()
            return any(supported in domain for supported in self.SUPPORTED_DOMAINS)
        except Exception:
            return False
    
    async def download(self, url: str, output_dir: str) -> DownloadResult:
        """Download using yt-dlp."""
        try:
            # yt-dlp command optimized for media download with flexible format selection
            cmd = [
                'yt-dlp',
                '--no-playlist',
                '--format', 'best/bestvideo+bestaudio/best',  # More flexible format selection
                '--output', f'{output_dir}/%(title)s.%(ext)s',
                '--print-json',  # Print JSON info about downloaded files
                '--no-write-info-json',  # Don't write separate .info.json files
                '--no-write-thumbnail',  # Don't write thumbnail files
                '--no-write-description',  # Don't write description files
                '--merge-output-format', 'mp4',  # Merge to mp4 if needed
                '--ignore-errors',  # Continue on download errors
                url
            ]
            
            logger.info(f"Executing yt-dlp command: {' '.join(cmd)}")
            
            # Run the command asynchronously
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                output_text = stdout.decode('utf-8')
                logger.info(f"yt-dlp completed successfully")
                
                # Parse JSON output to find downloaded files
                downloaded_files = []
                for line in output_text.strip().split('\n'):
                    if line.strip() and line.startswith('{'):
                        try:
                            import json
                            info = json.loads(line)
                            if 'requested_downloads' in info:
                                for download_info in info['requested_downloads']:
                                    if 'filepath' in download_info:
                                        filepath = download_info['filepath']
                                        if os.path.exists(filepath):
                                            downloaded_files.append(filepath)
                            elif '_filename' in info:
                                filepath = info['_filename']
                                if os.path.exists(filepath):
                                    downloaded_files.append(filepath)
                        except json.JSONDecodeError:
                            continue
                
                                 # If we found downloaded files, return the first one
                if downloaded_files:
                    main_file = downloaded_files[0]
                    logger.info(f"Found downloaded file from JSON: {main_file}")
                    return DownloadResult(
                        success=True,
                        file_path=main_file,
                        filename=os.path.basename(main_file)
                    )
                else:
                    # Fallback: look for any video files in the output directory
                    logger.info(f"No files found in JSON output, scanning directory: {output_dir}")
                    try:
                        dir_contents = os.listdir(output_dir)
                        logger.info(f"Directory contents: {dir_contents}")
                    except Exception as e:
                        logger.error(f"Error listing directory: {e}")
                        dir_contents = []
                    
                    video_extensions = ['.mp4', '.mkv', '.webm', '.avi', '.mov', '.flv', '.m4v']
                    for filename in dir_contents:
                        if any(filename.lower().endswith(ext) for ext in video_extensions):
                            filepath = os.path.join(output_dir, filename)
                            logger.info(f"Found video file: {filepath}")
                            return DownloadResult(
                                success=True,
                                file_path=filepath,
                                filename=filename
                            )
                    
                    return DownloadResult(
                        success=False,
                        error="Download completed but no video file found"
                    )
            else:
                error_msg = stderr.decode('utf-8')
                stdout_msg = stdout.decode('utf-8')
                logger.error(f"yt-dlp failed with return code {process.returncode}")
                logger.error(f"yt-dlp stderr: {error_msg}")
                logger.error(f"yt-dlp stdout: {stdout_msg}")
                
                # If format error, try to list available formats for debugging
                if "Requested format is not available" in error_msg:
                    logger.info("Attempting to list available formats for debugging...")
                    try:
                        list_cmd = ['yt-dlp', '--list-formats', url]
                        list_process = await asyncio.create_subprocess_exec(
                            *list_cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        list_stdout, list_stderr = await list_process.communicate()
                        if list_process.returncode == 0:
                            formats_info = list_stdout.decode('utf-8')
                            logger.info(f"Available formats:\n{formats_info}")
                            
                            # Try again with just 'best' format
                            logger.info("Retrying with simple 'best' format...")
                            retry_cmd = [
                                'yt-dlp',
                                '--no-playlist',
                                '--format', 'best',  # Simplest format selector
                                '--output', f'{output_dir}/%(title)s.%(ext)s',
                                '--print-json',
                                '--no-write-info-json',
                                '--no-write-thumbnail',
                                '--no-write-description',
                                '--ignore-errors',
                                url
                            ]
                            
                            retry_process = await asyncio.create_subprocess_exec(
                                *retry_cmd,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE
                            )
                            
                            retry_stdout, retry_stderr = await retry_process.communicate()
                            
                            if retry_process.returncode == 0:
                                # Parse the retry output
                                retry_output = retry_stdout.decode('utf-8')
                                logger.info("Retry with 'best' format succeeded!")
                                
                                # Try to find downloaded files
                                downloaded_files = []
                                for line in retry_output.strip().split('\n'):
                                    if line.strip() and line.startswith('{'):
                                        try:
                                            import json
                                            info = json.loads(line)
                                            if 'requested_downloads' in info:
                                                for download_info in info['requested_downloads']:
                                                    if 'filepath' in download_info:
                                                        filepath = download_info['filepath']
                                                        if os.path.exists(filepath):
                                                            downloaded_files.append(filepath)
                                            elif '_filename' in info:
                                                filepath = info['_filename']
                                                if os.path.exists(filepath):
                                                    downloaded_files.append(filepath)
                                        except json.JSONDecodeError:
                                            continue
                                
                                if downloaded_files:
                                    main_file = downloaded_files[0]
                                    logger.info(f"Found downloaded file from retry: {main_file}")
                                    return DownloadResult(
                                        success=True,
                                        file_path=main_file,
                                        filename=os.path.basename(main_file)
                                    )
                        else:
                            logger.error(f"Failed to list formats: {list_stderr.decode('utf-8')}")
                    except Exception as list_error:
                        logger.error(f"Error while trying to list formats: {list_error}")
                
                return DownloadResult(success=False, error=f"yt-dlp failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Exception during yt-dlp download: {str(e)}")
            return DownloadResult(success=False, error=str(e))

class GalleryDLDownloader(BaseDownloader):
    """Downloader for image galleries using gallery-dl."""
    
    SUPPORTED_DOMAINS = [
        'reddit.com', 'imgur.com', 'deviantart.com', 'artstation.com',
        'pixiv.net', 'danbooru.donmai.us', 'gelbooru.com'
    ]
    
    def supports_url(self, url: str) -> bool:
        try:
            domain = urlparse(url).netloc.lower()
            return any(supported in domain for supported in self.SUPPORTED_DOMAINS)
        except Exception:
            return False
    
    async def download(self, url: str, output_dir: str) -> DownloadResult:
        """Download using gallery-dl."""
        try:
            cmd = [
                'gallery-dl',
                '--destination', output_dir,
                url
            ]
            
            logger.info(f"Executing gallery-dl command: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return DownloadResult(
                    success=True,
                    file_path=output_dir,
                    filename="gallery_download_completed"
                )
            else:
                error_msg = stderr.decode('utf-8')
                logger.error(f"gallery-dl failed: {error_msg}")
                return DownloadResult(success=False, error=error_msg)
                
        except Exception as e:
            logger.error(f"Exception during gallery-dl download: {str(e)}")
            return DownloadResult(success=False, error=str(e))

class GenericDownloader(BaseDownloader):
    """Generic downloader for direct file downloads."""
    
    def supports_url(self, url: str) -> bool:
        # This is a fallback downloader that supports any HTTP(S) URL
        try:
            parsed = urlparse(url)
            return parsed.scheme in ['http', 'https']
        except Exception:
            return False
    
    async def download(self, url: str, output_dir: str) -> DownloadResult:
        """Download using wget or curl as fallback."""
        try:
            # Try wget first, then curl
            for cmd_template in [
                ['wget', '-P', output_dir, url],
                ['curl', '-o', f'{output_dir}/downloaded_file', url]
            ]:
                try:
                    process = await asyncio.create_subprocess_exec(
                        *cmd_template,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    stdout, stderr = await process.communicate()
                    
                    if process.returncode == 0:
                        return DownloadResult(
                            success=True,
                            file_path=output_dir,
                            filename="generic_download_completed"
                        )
                except FileNotFoundError:
                    continue  # Try next command
            
            return DownloadResult(
                success=False,
                error="No suitable downloader found (wget/curl not available)"
            )
            
        except Exception as e:
            logger.error(f"Exception during generic download: {str(e)}")
            return DownloadResult(success=False, error=str(e))

class DownloadService:
    """Service for downloading content from various URLs."""
    
    def __init__(self):
        self.downloaders = [
            YoutubeDLDownloader(),
            GalleryDLDownloader(),
            GenericDownloader()  # Fallback downloader
        ]
    
    def _get_downloader(self, url: str) -> Optional[BaseDownloader]:
        """Get the appropriate downloader for the given URL."""
        for downloader in self.downloaders:
            if downloader.supports_url(url):
                return downloader
        return None
    
    async def download(self, url: str, output_dir: str) -> DownloadResult:
        """Download content from URL using the appropriate downloader."""
        if not url or not url.strip():
            return DownloadResult(success=False, error="URL cannot be empty")
        
        # Basic URL validation
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return DownloadResult(success=False, error="Invalid URL format")
        except Exception as e:
            return DownloadResult(success=False, error=f"URL parsing error: {str(e)}")
        
        downloader = self._get_downloader(url)
        if not downloader:
            return DownloadResult(
                success=False,
                error=f"Unsupported URL: {url}"
            )
        
        logger.info(f"Using {downloader.__class__.__name__} for URL: {url}")
        
        try:
            result = await downloader.download(url, output_dir)
            return result
        except Exception as e:
            logger.error(f"Download failed: {str(e)}")
            return DownloadResult(success=False, error=str(e))
