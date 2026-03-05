#!/bin/bash

echo "Cài đặt môi trường ảo (Virtual Environment)..."
# Cài đặt python3-venv nếu chưa có (trên Ubuntu thường phải cài riêng module này)
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip

python3 -m venv venv
source venv/bin/activate

echo "Cài đặt các thư viện cần thiết..."
pip install -r requirements.txt

echo "Đang chạy Server Proxy..."
python3 main.py
