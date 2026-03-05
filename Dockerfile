FROM python:3.10-slim

# Thiết lập thư mục làm việc
WORKDIR /app

# Cài đặt các gói hệ thống cần thiết (ffmpeg rất cần thiết cho yt-dlp)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Cài đặt thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy mã nguồn vào Image
COPY main.py .

# Expose cổng 8000
EXPOSE 8000

# Lệnh chạy ứng dụng
CMD ["python", "main.py"]
