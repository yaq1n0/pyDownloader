# this file handles saving files to the file system

import os
import shutil
import logging
from typing import Optional, List
from pathlib import Path
from config_service import ConfigService

logger = logging.getLogger(__name__)

class FileService:
    """Service for handling file operations using the configured download directory."""
    
    def __init__(self, config_service: ConfigService):
        self.config_service = config_service
    
    def get_download_directory(self) -> str:
        """Get the configured download directory."""
        config = self.config_service.get_config()
        return config.download_directory
    
    def ensure_directory_exists(self, directory: str) -> bool:
        """Ensure a directory exists, create if it doesn't."""
        try:
            Path(directory).mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Failed to create directory {directory}: {str(e)}")
            return False
    
    def move_file(self, source_path: str, destination_filename: Optional[str] = None) -> Optional[str]:
        """
        Move a file to the configured download directory.
        
        Args:
            source_path: Path to the source file
            destination_filename: Optional custom filename for the destination
            
        Returns:
            Path to the moved file if successful, None otherwise
        """
        try:
            if not os.path.exists(source_path):
                logger.error(f"Source file does not exist: {source_path}")
                return None
            
            download_dir = self.get_download_directory()
            if not self.ensure_directory_exists(download_dir):
                return None
            
            # Use original filename if no custom name provided
            if destination_filename is None:
                destination_filename = os.path.basename(source_path)
            
            destination_path = os.path.join(download_dir, destination_filename)
            
            # Handle file name conflicts
            destination_path = self._get_unique_filename(destination_path)
            
            shutil.move(source_path, destination_path)
            logger.info(f"File moved from {source_path} to {destination_path}")
            
            return destination_path
            
        except Exception as e:
            logger.error(f"Failed to move file from {source_path}: {str(e)}")
            return None
    
    def copy_file(self, source_path: str, destination_filename: Optional[str] = None) -> Optional[str]:
        """
        Copy a file to the configured download directory.
        
        Args:
            source_path: Path to the source file
            destination_filename: Optional custom filename for the destination
            
        Returns:
            Path to the copied file if successful, None otherwise
        """
        try:
            if not os.path.exists(source_path):
                logger.error(f"Source file does not exist: {source_path}")
                return None
            
            download_dir = self.get_download_directory()
            if not self.ensure_directory_exists(download_dir):
                return None
            
            # Use original filename if no custom name provided
            if destination_filename is None:
                destination_filename = os.path.basename(source_path)
            
            destination_path = os.path.join(download_dir, destination_filename)
            
            # Handle file name conflicts
            destination_path = self._get_unique_filename(destination_path)
            
            shutil.copy2(source_path, destination_path)
            logger.info(f"File copied from {source_path} to {destination_path}")
            
            return destination_path
            
        except Exception as e:
            logger.error(f"Failed to copy file from {source_path}: {str(e)}")
            return None
    
    def list_files(self, pattern: str = "*") -> List[str]:
        """
        List files in the download directory matching the given pattern.
        
        Args:
            pattern: Glob pattern to match files (default: "*" for all files)
            
        Returns:
            List of file paths matching the pattern
        """
        try:
            download_dir = self.get_download_directory()
            download_path = Path(download_dir)
            
            if not download_path.exists():
                logger.warning(f"Download directory does not exist: {download_dir}")
                return []
            
            files = list(download_path.glob(pattern))
            file_paths = [str(f) for f in files if f.is_file()]
            
            logger.info(f"Found {len(file_paths)} files matching pattern '{pattern}'")
            return file_paths
            
        except Exception as e:
            logger.error(f"Failed to list files with pattern '{pattern}': {str(e)}")
            return []
    
    def delete_file(self, filename: str) -> bool:
        """
        Delete a file from the download directory.
        
        Args:
            filename: Name of the file to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            download_dir = self.get_download_directory()
            file_path = os.path.join(download_dir, filename)
            
            if not os.path.exists(file_path):
                logger.warning(f"File does not exist: {file_path}")
                return False
            
            os.remove(file_path)
            logger.info(f"File deleted: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete file {filename}: {str(e)}")
            return False
    
    def get_file_info(self, filename: str) -> Optional[dict]:
        """
        Get information about a file in the download directory.
        
        Args:
            filename: Name of the file
            
        Returns:
            Dictionary with file information or None if file doesn't exist
        """
        try:
            download_dir = self.get_download_directory()
            file_path = os.path.join(download_dir, filename)
            
            if not os.path.exists(file_path):
                return None
            
            stat = os.stat(file_path)
            return {
                'filename': filename,
                'full_path': file_path,
                'size_bytes': stat.st_size,
                'created_time': stat.st_ctime,
                'modified_time': stat.st_mtime,
                'is_file': os.path.isfile(file_path),
                'is_directory': os.path.isdir(file_path)
            }
            
        except Exception as e:
            logger.error(f"Failed to get file info for {filename}: {str(e)}")
            return None
    
    def _get_unique_filename(self, file_path: str) -> str:
        """
        Get a unique filename by appending a number if the file already exists.
        
        Args:
            file_path: Desired file path
            
        Returns:
            Unique file path
        """
        if not os.path.exists(file_path):
            return file_path
        
        directory = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        name, ext = os.path.splitext(filename)
        
        counter = 1
        while True:
            new_filename = f"{name}_{counter}{ext}"
            new_path = os.path.join(directory, new_filename)
            if not os.path.exists(new_path):
                return new_path
            counter += 1