# StretchMyClip

Small desktop app for stretching a video into a 16:9 frame.

This was vibecoded with AI to solve a very specific annoyance: quickly stretch non-16:9 clips to standard 16:9 without manually changing unrelated settings like FPS or audio. As a side benefit, the re-encoded output can also be noticeably smaller while still looking good.

## What it does

- Opens a window with a drag-and-drop area.
- Lets you click the area to pick one or more files if you prefer.
- Keeps the original height and stretches or squashes the width to 16:9.
- Leaves timing alone and copies the audio stream as-is.
- Automatically prefers a supported GPU encoder and falls back to CPU if needed.
- Uses a higher-quality export profile instead of default encoder settings.
- Lets the user choose whether already-16:9 files are skipped or converted anyway.
- Can replace originals by moving the old files to the Recycle Bin after successful conversion.

## Requirements

- Python 3.10+
- `ffmpeg` and `ffprobe` available in your `PATH`

## Setup

```powershell
python -m pip install -r requirements.txt
```

## Run

```powershell
python main.py
```

Output files are saved next to the originals with `_stretched_16x9` added to the name.
