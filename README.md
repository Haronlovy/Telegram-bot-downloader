# 🎥 Universal Video Downloader Bot

A powerful, asynchronous Telegram bot built with Python that allows users to download videos from **TikTok, YouTube, Instagram, and X (Twitter)** directly to their Telegram chat.

✨ Features
* **Multi-Platform Support:** Works with TikTok, YouTube (Shorts), Instagram Reels, and X.
* **No Watermarks:** Downloads TikToks without the floating logo.
* **Auto-Compression:** Automatically selects the best quality under 50MB to fit Telegram's API limits.
* **Asynchronous & Concurrent:** Handles multiple users at once using `asyncio` and `Semaphores`.
* **Auto-Cleanup:** Automatically deletes downloaded files from the server after 1 hour to save disk space.

## 🛠️ Tech Stack
* **Language:** Python 3.10+
* **Framework:** `python-telegram-bot` (v20+)
* **Engine:** `yt-dlp` for media extraction.
* **Concurrency:** `asyncio` for non-blocking I/O.

## 🚀 Quick Start

### 1. Prerequisites
Ensure you have **FFmpeg** installed on your system.
```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# MacOS
brew install ffmpeg
# Telegram-bot-downloader
Video downloader 
