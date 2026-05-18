# StretchMyClip

It does what the name says, it streches your clips lol. (first time pushing github repo, kinda nervous >w<)

You just hit a clip and want to share it with your friends but you try-hard ass plays on 4:3 or other shenanigans? Fear not! I have a solution.
StretchMyClip is a small app vibe-coded in Python (yes, I have hella limited knowledge about coding). The program itself uses ffmpeg and basically it changes aspect ratio of the video to match standard 16:9. Also there is side benefit - it reduces clips size by a lot so you can also just compress the videos with it if you want idk.

## How does it works

- You open it and there is an drag-and-drop area where you can drop one or more video files. You can also click the area if you want, it will open a window with file picker.
- Keeps the original height and stretches or squashes the width to 16:9.
- Leaves timing alone and copies the audio stream as-is.
- It knows what GPU u use... (ooohhh heker scary :OOO) ...so it can tell what encoder it should use.
- Uses a higher-quality export profile instead of default encoder settings.
- You can decide whether videos that are already 16:9 should be skipped or converted anyway, by checking the box - this one is useful when you use NVIDIA App clipping thing - cuz NVIDIA clipping feature has some kind of stupid thing where it sometimes stretches the clips and sometimes it doesn't.
- You can also decide whether the old files should be replaced or not (replaced files gets moved to trash bin so you can retrive them if something fails)

## Requirements

- Python 3.10+
- `ffmpeg` and `ffprobe` available in your `PATH` (the easiest way I found to install both is just by typing `winget install ffmpeg` in terminal)

## Setup

```powershell
python -m pip install -r requirements.txt
```

## Run

```powershell
python main.py
```

Output files are saved next to the originals with `_stretched_16x9` added to the name.

I don't take this code seriously and wether should you, so yeah, do whatever the fuck you want with it idc lol. it can be easily replicated in codex or claude in like half an hour anyway

## License

WTFPL Version 2. Do what the fuck you want to.
