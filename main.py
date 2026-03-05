from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
import yt_dlp
import requests
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

html_content = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Facebook Stream Proxy</title>
    <link href="https://vjs.zencdn.net/8.3.0/video-js.css" rel="stylesheet" />
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #121212; color: #fff; margin: 0; padding: 20px; display: flex; flex-direction: column; align-items: center; }
        .container { width: 100%; max-width: 800px; background: #1e1e1e; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        h1 { text-align: center; color: #1877f2; }
        .input-group { display: flex; gap: 10px; margin-bottom: 20px; }
        input[type="text"] { flex: 1; padding: 10px; border: 1px solid #333; border-radius: 4px; background: #222; color: #fff; }
        button { padding: 10px 20px; background: #1877f2; border: none; border-radius: 4px; color: white; cursor: pointer; font-weight: bold; }
        button:hover { background: #166fe5; }
        .video-container { width: 100%; border-radius: 8px; overflow: hidden; background: #000; display: none; margin-top: 20px; }
        .error { color: #ff4a4a; margin-top: 10px; text-align: center; display: none; }
        .loading { text-align: center; margin-top: 10px; display: none; color: #aaa; }
    </style>
</head>
<body>
    <div class="container">
        <h1>FB Proxy Web Player</h1>
        <div class="input-group">
            <input type="text" id="fbUrl" placeholder="Dán link Facebook video/stream vào đây..." />
            <button onclick="playVideo()">Xem ngay</button>
        </div>
        <div class="loading" id="loading">Đang lấy link video... Có thể mất vài giây.</div>
        <div class="error" id="errorMsg"></div>
        <div class="video-container" id="videoWrapper">
            <!-- Video tag will be injected here -->
        </div>
    </div>

    <script src="https://vjs.zencdn.net/8.3.0/video.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/dashjs@4.7.1/dist/dash.all.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/videojs-contrib-dash@5.1.1/dist/videojs-dash.min.js"></script>
    <script>
        // Chặn và định tuyến mọi request tới fbcdn qua proxy của server để tránh CORS Error
        const originalFetch = window.fetch;
        window.fetch = async function() {
            let args = Array.from(arguments);
            let url = args[0] instanceof Request ? args[0].url : args[0];
            if (typeof url === 'string' && !url.includes('/api/proxy') && (url.includes('fbcdn.net') || url.includes('.mpd') || url.includes('.m3u8') || url.includes('.mp4'))) {
                const proxyUrl = '/api/proxy?url=' + encodeURIComponent(url);
                if (args[0] instanceof Request) {
                    args[0] = new Request(proxyUrl, args[0]);
                } else {
                    args[0] = proxyUrl;
                }
            }
            return originalFetch.apply(window, args);
        };

        const originalOpen = XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open = function(method, url) {
            if (typeof url === 'string' && !url.includes('/api/proxy') && (url.includes('fbcdn.net') || url.includes('.mpd') || url.includes('.m3u8') || url.includes('.mp4'))) {
                url = '/api/proxy?url=' + encodeURIComponent(url);
            }
            return originalOpen.apply(this, [method, url]);
        };

        async function playVideo() {
            const urlInput = document.getElementById('fbUrl').value;
            const errorMsg = document.getElementById('errorMsg');
            const loading = document.getElementById('loading');
            const videoWrapper = document.getElementById('videoWrapper');

            if (!urlInput) return;

            errorMsg.style.display = 'none';
            videoWrapper.style.display = 'none';
            loading.style.display = 'block';
            
            // Clean up old player if exists
            videoWrapper.innerHTML = '';

            try {
                const response = await fetch(`/api/extract?url=${encodeURIComponent(urlInput)}`);
                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.detail || data.error || 'Có lỗi xảy ra khi lấy video.');
                }

                loading.style.display = 'none';
                
                // Create video element
                const videoEl = document.createElement('video');
                videoEl.id = 'fbPlayer';
                videoEl.className = 'video-js vjs-default-skin vjs-16-9';
                videoEl.controls = true;
                videoEl.autoplay = true;
                
                const sourceEl = document.createElement('source');
                // Link sẽ tự động bị chặn bởi XHR/Fetch override phía trên và chạy qua /api/proxy
                sourceEl.src = data.stream_url;
                
                if (data.is_dash) {
                    sourceEl.type = 'application/dash+xml';
                } else if (data.is_hls) {
                    sourceEl.type = 'application/x-mpegURL';
                } else {
                    sourceEl.type = 'video/mp4';
                }
                
                videoEl.appendChild(sourceEl);
                videoWrapper.appendChild(videoEl);
                videoWrapper.style.display = 'block';

                // Initialize Video.js với cấu hình tối ưu Livestream
                videojs(videoEl, {
                    liveui: true,
                    fluid: true,
                    html5: {
                        dash: {
                            setFastSwitchEnabled: true,
                        }
                    }
                }, function() {
                    if (data.is_live) {
                        this.addClass('vjs-live');
                    }
                });
            } catch (err) {
                loading.style.display = 'none';
                errorMsg.textContent = err.message;
                errorMsg.style.display = 'block';
            }
        }
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(content=html_content)

@app.get("/api/extract")
async def extract_url(url: str):
    ydl_opts = {
        'format': 'best/bestvideo+bestaudio',
        'quiet': True,
        'no_warnings': True,
        'live_from_start': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Ưu tiên lấy url trực tiếp, nếu không có thì tìm trong formats
            stream_url = info.get('url')
            if not stream_url and 'formats' in info:
                # Với livestream, ưu tiên format có chứa 'manifest' hoặc hls/dash
                valid_formats = [f for f in info['formats'] if f.get('url')]
                if valid_formats:
                    # Sắp xếp để lấy cái tốt nhất (thường là cuối danh sách)
                    stream_url = valid_formats[-1].get('url')
                
            if not stream_url:
                raise Exception("Không thể trích xuất liên kết luồng. Video có thể là riêng tư hoặc yêu cầu đăng nhập.")
                
            # Xác định loại luồng
            is_hls = '.m3u8' in stream_url.lower() or info.get('protocol') in ['m3u8', 'm3u8_native'] or info.get('ext') == 'm3u8'
            is_dash = '.mpd' in stream_url.lower() or info.get('protocol') in ['dash', 'dash_native'] or 'dash' in stream_url.lower() or info.get('ext') == 'mpd'
            
            # Một số livestream FB trả về protocol là 'https' nhưng thực tế là m3u8/dash
            if not is_hls and not is_dash:
                if 'live' in info.get('protocol', '').lower() or info.get('is_live'):
                    is_hls = True # Giả định là HLS nếu là live mà không rõ protocol
            
            return {
                "success": True, 
                "stream_url": stream_url,
                "is_hls": is_hls,
                "is_dash": is_dash,
                "is_live": info.get('is_live', False),
                "title": info.get('title', 'Facebook Video')
            }
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/proxy")
async def proxy_video(request: Request, url: str):
    """
    Proxy hoàn chỉnh hỗ trợ Range bypass CORS
    """
    headers = {
        "User-Agent": request.headers.get("user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"),
        "Referer": "https://www.facebook.com/"
    }
    
    # Chuyển tiếp header Range từ Client browser xuống Facebook
    if "range" in request.headers:
        headers["Range"] = request.headers["range"]
    
    req = requests.get(url, headers=headers, stream=True)
    
    # Sửa lỗi DASH relative path cho file MPD
    if ".mpd" in url.lower():
        content = req.text
        # Trích xuất đường dẫn thư mục cha của file MPD
        base_url = url.split("?")[0].rsplit("/", 1)[0] + "/"
        
        import re
        # Chèn thẻ BaseURL tuyệt đối ngay sau thẻ MPD để dash.js nối đúng link CDN thay vì link localhost
        if "<BaseURL>" not in content:
            content = re.sub(r'(<MPD[^>]*>)', r'\1\n  <BaseURL>' + base_url + '</BaseURL>', content, count=1)
            
        resp_headers = {
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "application/dash+xml",
            "Access-Control-Expose-Headers": "Content-Range, Accept-Ranges, Content-Length"
        }
        from fastapi import Response
        return Response(content=content, media_type="application/dash+xml", headers=resp_headers)
    
    resp_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Range",
        "Access-Control-Expose-Headers": "Content-Range, Accept-Ranges, Content-Length"
    }

    if "Content-Type" in req.headers:
        resp_headers["Content-Type"] = req.headers["Content-Type"]
    if "Content-Range" in req.headers:
        resp_headers["Content-Range"] = req.headers["Content-Range"]
    if "Accept-Ranges" in req.headers:
        resp_headers["Accept-Ranges"] = req.headers["Accept-Ranges"]

    return StreamingResponse(
        req.iter_content(chunk_size=1024*1024), 
        status_code=req.status_code,
        headers=resp_headers
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
