# pyDownloader API

A FastAPI-based microservice for downloading content from various websites and services including YouTube, social media platforms, image galleries, and more.

## Features

- **Multi-platform Support**: Downloads from YouTube, Vimeo, Instagram, Twitter, Reddit, Imgur, and many more
- **Async Processing**: Handles concurrent downloads efficiently
- **Configurable**: Easy configuration via JSON file
- **RESTful API**: Clean REST endpoints with comprehensive error handling
- **File Management**: Built-in file listing, deletion, and organization
- **Health Monitoring**: Health check endpoints for monitoring

## Supported Services

### Video/Media Downloaders (via yt-dlp)

- YouTube (youtube.com, youtu.be)
- Vimeo (vimeo.com)
- Dailymotion (dailymotion.com)
- Twitch (twitch.tv)
- TikTok (tiktok.com)
- Instagram (instagram.com)
- Twitter/X (twitter.com, x.com)

### Gallery/Image Downloaders (via gallery-dl)

- Reddit (reddit.com)
- Imgur (imgur.com)
- DeviantArt (deviantart.com)
- ArtStation (artstation.com)
- Pixiv (pixiv.net)
- Danbooru (danbooru.donmai.us)
- Gelbooru (gelbooru.com)

### Generic Downloads

- Any HTTP/HTTPS direct file links

## Installation

1. **Clone the repository:**

   ```bash
   git clone <repository-url>
   cd pyDownloader
   ```

2. **Install Python dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Install external tools:**

   **On macOS (using Homebrew):**

   ```bash
   brew install yt-dlp gallery-dl wget curl
   ```

   **On Ubuntu/Debian:**

   ```bash
   sudo apt update
   sudo apt install yt-dlp gallery-dl wget curl
   ```

   **Using pip (alternative):**

   ```bash
   pip install yt-dlp gallery-dl
   ```

4. **Configure the application:**

   Edit `config.json` to set your preferred download directory:

   ```json
   {
     "downloadDirectory": "~/Downloads/pyDownloader"
   }
   ```

## Usage

### Starting the Server

**Development mode:**

```bash
python main.py
```

**Production mode:**

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### API Documentation

Once the server is running, visit:

- **Interactive API docs**: http://localhost:8000/docs
- **Alternative docs**: http://localhost:8000/redoc

### API Endpoints

#### 1. Download from URL (Path Parameter)

```http
POST /download/{url_to_download}
```

**Example:**

```bash
curl -X POST "http://localhost:8000/download/https%3A//youtube.com/watch%3Fv%3DdQw4w9WgXcQ"
```

#### 2. Download from URL (Request Body)

```http
POST /download
Content-Type: application/json

{
  "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
  "custom_filename": "my_video"
}
```

**Example:**

```bash
curl -X POST "http://localhost:8000/download" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=dQw4w9WgXcQ"}'
```

#### 3. List Downloaded Files

```http
GET /files?pattern=*
```

**Example:**

```bash
curl "http://localhost:8000/files"
curl "http://localhost:8000/files?pattern=*.mp4"
```

#### 4. Delete File

```http
DELETE /files/{filename}
```

**Example:**

```bash
curl -X DELETE "http://localhost:8000/files/my_video.mp4"
```

#### 5. Service Status

```http
GET /
```

#### 6. Health Check

```http
GET /health
```

### Response Format

All download endpoints return a standardized response:

```json
{
  "success": true,
  "message": "Download completed successfully",
  "filename": "downloaded_file.mp4",
  "file_path": "/path/to/downloads/downloaded_file.mp4",
  "error": null
}
```

## Configuration

The `config.json` file supports the following options:

```json
{
  "downloadDirectory": "~/Downloads/pyDownloader"
}
```

- `downloadDirectory`: Path where downloaded files will be saved (supports `~` for home directory)

## Architecture

The application follows a clean service-oriented architecture:

### Services

1. **ConfigService** (Singleton)

   - Loads configuration from `config.json`
   - Validates and resolves download directory paths
   - Provides dynamic configuration reloading

2. **FileService** (Singleton)

   - Handles file operations (move, copy, delete, list)
   - Manages download directory
   - Provides file metadata and conflict resolution

3. **DownloadService** (Per-request instances)
   - Selects appropriate downloader based on URL domain
   - Coordinates download operations
   - Supports multiple downloader backends

### Download Strategy

The service uses a **factory pattern** to select the appropriate downloader:

1. **Domain Analysis**: Parse the URL to identify the domain
2. **Downloader Selection**: Match domain against supported downloader patterns
3. **Download Execution**: Execute the appropriate tool (yt-dlp, gallery-dl, wget/curl)
4. **File Processing**: Move downloaded files to the configured directory

## Error Handling

The API provides comprehensive error handling for:

- Invalid URLs
- Unsupported domains/services
- Network failures
- File system errors
- Configuration issues
- External tool failures

## Logging

All operations are logged with appropriate levels:

- INFO: Successful operations, service status
- ERROR: Failed operations, exceptions
- DEBUG: Detailed operation traces (when enabled)

## Security Considerations

- **URL Validation**: All URLs are validated before processing
- **Path Sanitization**: File paths are sanitized to prevent directory traversal
- **Resource Limits**: Downloads use temporary directories to isolate operations

## Development

### Adding New Downloaders

To add support for additional services:

1. Create a new downloader class inheriting from `BaseDownloader`
2. Implement `supports_url()` and `download()` methods
3. Add the downloader to the `DownloadService` constructor

Example:

```python
class CustomDownloader(BaseDownloader):
    SUPPORTED_DOMAINS = ['example.com']

    def supports_url(self, url: str) -> bool:
        domain = urlparse(url).netloc.lower()
        return any(supported in domain for supported in self.SUPPORTED_DOMAINS)

    async def download(self, url: str, output_dir: str) -> DownloadResult:
        # Implementation here
        pass
```

### Testing

Test the API endpoints using the interactive documentation at `/docs` or with curl/Postman.

## Troubleshooting

### Common Issues

1. **"Command not found" errors**: Ensure yt-dlp, gallery-dl, wget, or curl are installed
2. **Permission denied**: Check write permissions for the download directory
3. **Download failures**: Check internet connectivity and URL validity
4. **Configuration errors**: Verify `config.json` syntax and paths

### Logs

Check the application logs for detailed error information. Logs include:

- Request details
- Download command execution
- File operation results
- Error traces

## License

[Your License Here]
