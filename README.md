# pyDownloader API

A FastAPI-based microservice for downloading content from various websites and services including YouTube, social media platforms, image galleries, and more.

## Features

- **Multi-platform Support**: Downloads from YouTube, Vimeo, Instagram, Twitter, Reddit, Imgur, and many more
- **Async Processing**: Handles concurrent downloads efficiently using asyncio
- **Configurable**: Dynamic configuration via JSON file with validation
- **RESTful API**: Clean REST endpoints with comprehensive error handling
- **File Management**: Built-in file listing, deletion, and organization with conflict resolution
- **Health Monitoring**: Health check endpoints for monitoring
- **Singleton Architecture**: Efficient resource management with singleton services
- **Temporary Directory Isolation**: Downloads use isolated temporary directories for safety

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

- Any HTTP/HTTPS direct file links (via wget/curl)

## Technical Architecture

### Core Design Patterns

The application implements several key design patterns:

1. **Singleton Pattern**: Configuration and File services are singletons for resource efficiency
2. **Factory Pattern**: Download service uses factory pattern to select appropriate downloaders
3. **Strategy Pattern**: Different download strategies (yt-dlp, gallery-dl, generic) based on URL domain
4. **Dependency Injection**: FastAPI's dependency system manages service instances

### Service Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   FastAPI App   │────│  Config Service  │────│   File Service  │
│   (main.py)     │    │  (Singleton)     │    │   (Singleton)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                                               │
         └─────────────────┐                            │
                           │                            │
                ┌─────────────────┐                     │
                │ Download Service│                     │
                │ (Per Request)   │                     │
                └─────────────────┘                     │
                         │                              │
           ┌─────────────┼─────────────┐               │
           │             │             │               │
    ┌─────────────┐ ┌────────────┐ ┌──────────────┐   │
    │ YoutubeDL   │ │ GalleryDL  │ │   Generic    │   │
    │ Downloader  │ │ Downloader │ │  Downloader  │   │
    └─────────────┘ └────────────┘ └──────────────┘   │
                                                       │
                           ┌────────────────────────────┘
                           │
                    ┌─────────────┐
                    │ File System │
                    │ Operations  │
                    └─────────────┘
```

### 1. ConfigService (Singleton)

**File**: `config_service.py`

**Implementation Details**:

- **Dynamic Loading**: Reads `config.json` on every `get_config()` call (no caching)
- **Path Resolution**: Converts `~` to absolute paths using `Path.expanduser().resolve()`
- **Validation**: Post-initialization validation of directory paths and port numbers
- **Error Handling**: Comprehensive error handling for file operations and JSON parsing

**Key Features**:

```python
@dataclass
class Config:
    download_directory: str
    application_port: int = 8000

    def __post_init__(self):
        # Automatic path expansion and directory creation
        path = Path(self.download_directory).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        self.download_directory = str(path)
```

**Configuration Format** (`config.json`):

```json
{
  "downloadDirectory": "~/Downloads/pyDownloader",
  "applicationPort": 8000
}
```

### 2. FileService (Singleton)

**File**: `file_service.py`

**Implementation Details**:

- **Conflict Resolution**: Automatic filename conflict resolution with `_1`, `_2` suffixes
- **Path Safety**: All operations use `os.path.join()` and `Path` for safe path handling
- **Atomic Operations**: Uses `shutil.move()` and `shutil.copy2()` for atomic file operations
- **Metadata Support**: Provides file information including size, timestamps, and type

**Key Methods**:

```python
def move_file(self, source_path: str, destination_filename: Optional[str] = None) -> Optional[str]:
    # Handles file moving with automatic conflict resolution
    destination_path = self._get_unique_filename(destination_path)
    shutil.move(source_path, destination_path)

def _get_unique_filename(self, file_path: str) -> str:
    # Automatic filename conflict resolution
    if not os.path.exists(file_path):
        return file_path
    # Appends _1, _2, etc. until unique filename found
```

### 3. DownloadService (Per-Request Instances)

**File**: `download_service.py`

**Implementation Details**:

- **Abstract Base Class**: `BaseDownloader` defines contract for all downloaders
- **URL Domain Matching**: Each downloader specifies supported domains
- **Async Subprocess**: All external tools run via `asyncio.create_subprocess_exec()`
- **JSON Output Parsing**: yt-dlp outputs are parsed to extract file information
- **Fallback Mechanisms**: Multiple retry strategies for robust downloads

**Downloader Selection Logic**:

```python
def _get_downloader(self, url: str) -> Optional[BaseDownloader]:
    for downloader in self.downloaders:
        if downloader.supports_url(url):
            return downloader
    return None
```

#### YoutubeDLDownloader

**Advanced Features**:

- **Format Selection**: Flexible format selection with fallback (`best/bestvideo+bestaudio/best`)
- **JSON Output Parsing**: Parses yt-dlp JSON output to locate downloaded files
- **Retry Logic**: Automatic retry with simpler format selection on failure
- **Format Discovery**: Lists available formats for debugging failed downloads

**Command Structure**:

```python
cmd = [
    'yt-dlp',
    '--no-playlist',
    '--format', 'best/bestvideo+bestaudio/best',
    '--output', f'{output_dir}/%(title)s.%(ext)s',
    '--print-json',
    '--no-write-info-json',
    '--no-write-thumbnail',
    '--no-write-description',
    '--merge-output-format', 'mp4',
    '--ignore-errors',
    url
]
```

#### GalleryDLDownloader

**Implementation**:

- **Directory-based Output**: Downloads entire galleries to directories
- **Simple Command Structure**: Minimal configuration for maximum compatibility

#### GenericDownloader

**Fallback Strategy**:

- **Multiple Tools**: Tries wget first, then curl as fallback
- **Universal Support**: Handles any HTTP/HTTPS URL as last resort

### 4. FastAPI Application (main.py)

**Implementation Details**:

#### Application Lifecycle Management

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Configuration validation
    # Shutdown: Cleanup operations
```

#### Dependency Injection

```python
def get_download_service() -> DownloadService:
    # Creates new instance per request (not singleton)
    return DownloadService()
```

#### URL Handling Strategy

The application handles complex URL scenarios:

1. **Path Parameter Decoding**: URLs are URL-decoded from path parameters
2. **Query Parameter Reconstruction**: Query parameters are manually rebuilt
3. **Full URL Reconstruction**: Complete URL is reconstructed from fragments

```python
# URL reconstruction logic
decoded_url = unquote(url_to_download)
if request and request.url.query:
    full_url = f"{decoded_url}?{request.url.query}"
else:
    full_url = decoded_url
```

#### Temporary Directory Pattern

```python
with tempfile.TemporaryDirectory() as temp_dir:
    # All downloads happen in isolated temporary directories
    result = await download_service.download(full_url, temp_dir)
    # Files are moved to permanent location after download
```

## API Endpoints

### 1. Download Endpoints

#### GET `/download/{url_to_download:path}`

- **URL Encoding**: Supports URL-encoded paths
- **Query Parameter Support**: Reconstructs full URLs with query parameters
- **Custom Filenames**: Optional custom filename parameter
- **Response**: Standardized `DownloadResponse` model

#### POST `/download`

- **Request Body**: JSON with URL and optional custom filename
- **Content Type**: `application/json`
- **Validation**: Pydantic model validation

### 2. File Management Endpoints

#### GET `/files`

- **Pattern Matching**: Supports glob patterns for file filtering
- **File Metadata**: Returns comprehensive file information
- **Directory Listing**: Lists all files in download directory

#### DELETE `/files/{filename}`

- **Safe Deletion**: Only deletes files from configured download directory
- **Error Handling**: Returns appropriate HTTP status codes

### 3. Service Status Endpoints

#### GET `/`

- **Service Status**: Returns running status and configuration
- **Supported Domains**: Lists all supported domains by downloader type
- **Configuration Info**: Shows current download directory

#### GET `/health`

- **Health Checks**: Validates configuration and directory access
- **Directory Permissions**: Checks write permissions on download directory
- **Service Availability**: Returns HTTP 503 if unhealthy

## Error Handling & Logging

### Error Response Format

```python
class DownloadResponse(BaseModel):
    success: bool
    message: str
    filename: Optional[str] = None
    file_path: Optional[str] = None
    error: Optional[str] = None
```

### Logging Strategy

- **Structured Logging**: Consistent format across all services
- **Log Levels**: INFO for operations, ERROR for failures, DEBUG for traces
- **Request Tracing**: Full request lifecycle logging
- **External Tool Output**: Captures and logs subprocess output

### Exception Handling Patterns

```python
try:
    # Operation
except FileNotFoundError:
    # Specific handling
except Exception as e:
    logger.error(f"Unexpected error: {str(e)}")
    raise HTTPException(status_code=500, detail=str(e))
```

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
     "downloadDirectory": "~/Downloads/pyDownloader",
     "applicationPort": 8000
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

### API Examples

#### Download from URL (Path Parameter)

```bash
curl -X GET "http://localhost:8000/download/https%3A//youtube.com/watch%3Fv%3DdQw4w9WgXcQ"
```

#### Download from URL (Request Body)

```bash
curl -X POST "http://localhost:8000/download" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=dQw4w9WgXcQ", "custom_filename": "my_video"}'
```

#### List Files

```bash
curl "http://localhost:8000/files"
curl "http://localhost:8000/files?pattern=*.mp4"
```

#### Delete File

```bash
curl -X DELETE "http://localhost:8000/files/my_video.mp4"
```

## Development Guide

### Adding New Downloaders

1. **Create Downloader Class**:

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

2. **Register in DownloadService**:

```python
def __init__(self):
    self.downloaders = [
        YoutubeDLDownloader(),
        GalleryDLDownloader(),
        CustomDownloader(),  # Add here
        GenericDownloader()  # Keep as fallback
    ]
```

### Code Quality Standards

- **Type Hints**: All functions use proper type hints
- **Error Handling**: Comprehensive exception handling at all levels
- **Logging**: Structured logging for all operations
- **Documentation**: Docstrings for all public methods
- **Validation**: Input validation using Pydantic models

### Testing Considerations

- **Async Testing**: Use `pytest-asyncio` for async function testing
- **Mocking**: Mock external subprocess calls for unit tests
- **Temporary Directories**: Use `tempfile` for test isolation
- **Configuration Testing**: Test various configuration scenarios

## Security Considerations

- **URL Validation**: All URLs validated before processing
- **Path Sanitization**: File paths sanitized to prevent directory traversal
- **Resource Isolation**: Downloads use temporary directories
- **Permission Checks**: File system permissions validated
- **Input Validation**: All input validated via Pydantic models

## Performance Optimizations

- **Singleton Services**: Configuration and file services are singletons
- **Async Operations**: All I/O operations are asynchronous
- **Temporary Directory Cleanup**: Automatic cleanup prevents disk space issues
- **Efficient File Operations**: Uses optimized file operations (shutil)

## Troubleshooting

### Common Issues

1. **External Tool Errors**: Check if yt-dlp, gallery-dl, wget, curl are installed
2. **Permission Issues**: Verify write permissions on download directory
3. **Configuration Errors**: Validate JSON syntax in config.json
4. **URL Encoding Issues**: Ensure URLs are properly encoded for path parameters

### Debug Mode

Enable debug logging by modifying the logging configuration:

```python
logging.basicConfig(level=logging.DEBUG)
```

### Monitoring

- Check `/health` endpoint for service health
- Monitor logs for download success/failure rates
- Watch disk space in download directory
- Monitor external tool availability

## License

[Your License Here]
