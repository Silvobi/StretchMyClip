"""StretchMyClip: tiny GUI batch tool for stretching videos to 16:9.

The app intentionally changes the video frame shape while leaving timing and
audio alone. FFmpeg does the actual video work; tkinter handles the UI.
"""

import json
import math
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from tkinter import Tk, filedialog, messagebox

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None

import tkinter as tk

try:
    from send2trash import send2trash
except ImportError:
    send2trash = None


APP_TITLE = "StretchMyClip!"
APP_FONT = "Comic Sans MS"
SUPPORTED_VIDEO_TYPES = [
    ("Video files", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v"),
    ("All files", "*.*"),
]
TARGET_ASPECT_RATIO = 16 / 9
ASPECT_TOLERANCE = 0.01
ENCODER_CANDIDATES = [
    ("h264_nvenc", "NVIDIA GPU"),
    ("h264_qsv", "Intel GPU"),
    ("h264_amf", "AMD GPU"),
]


def is_ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


@lru_cache(maxsize=1)
def detect_best_video_encoder() -> tuple[str, str]:
    # Ask the installed FFmpeg build which H.264 encoders it supports.
    # GPU encoders are preferred when available, with CPU as the fallback.
    if shutil.which("ffmpeg") is None:
        return "libx264", "CPU"

    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return "libx264", "CPU"

    encoder_list = result.stdout
    for encoder_name, encoder_label in ENCODER_CANDIDATES:
        if encoder_name in encoder_list:
            return encoder_name, encoder_label

    return "libx264", "CPU"


def probe_video_size(video_path: Path) -> tuple[int, int]:
    # ffprobe gives us the source dimensions without decoding the whole file.
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "json",
        str(video_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    stream = data["streams"][0]
    return int(stream["width"]), int(stream["height"])


def build_video_encoder_args(video_encoder: str) -> list[str]:
    # CPU uses quality-based CRF; GPU encoders use a higher VBR target because
    # hardware encoders usually need more bitrate for similar visual quality.
    if video_encoder == "libx264":
        return ["-c:v", "libx264", "-preset", "medium", "-crf", "18"]

    if video_encoder == "h264_nvenc":
        return [
            "-c:v",
            "h264_nvenc",
            "-preset",
            "p5",
            "-rc:v",
            "vbr",
            "-cq:v",
            "19",
            "-b:v",
            "10M",
            "-maxrate:v",
            "12M",
        ]

    if video_encoder == "h264_qsv":
        return [
            "-c:v",
            "h264_qsv",
            "-preset",
            "medium",
            "-b:v",
            "10M",
            "-maxrate:v",
            "12M",
        ]

    if video_encoder == "h264_amf":
        return [
            "-c:v",
            "h264_amf",
            "-quality",
            "quality",
            "-rc",
            "vbr_peak",
            "-b:v",
            "10M",
            "-maxrate:v",
            "12M",
        ]

    return ["-c:v", "libx264", "-preset", "medium", "-crf", "18"]


def compute_target_size(width: int, height: int) -> tuple[int, int]:
    # Keep the original height and stretch/squash only the width to 16:9.
    # The width is rounded up to an even number because many H.264 encoders
    # reject odd frame dimensions.
    target_width = math.ceil((height * 16 / 9) / 2) * 2
    return target_width, height


def is_already_16_by_9(width: int, height: int) -> bool:
    if height == 0:
        return False
    return abs((width / height) - TARGET_ASPECT_RATIO) <= ASPECT_TOLERANCE


def build_output_path(video_path: Path) -> Path:
    return video_path.with_name(f"{video_path.stem}_stretched_16x9{video_path.suffix}")


def stretch_video(
    video_path: Path, skip_if_16_by_9: bool, video_encoder: str
) -> tuple[Path | None, str]:
    width, height = probe_video_size(video_path)
    if skip_if_16_by_9 and is_already_16_by_9(width, height):
        return None, "already_16_9"

    target_width, target_height = compute_target_size(width, height)
    output_path = build_output_path(video_path)

    # setdar/setsar prevent players from using old aspect metadata and showing
    # a 16:9 container with a visually unstretched image inside it.
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"scale={target_width}:{target_height},setsar=1,setdar=16/9",
        *build_video_encoder_args(video_encoder),
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    subprocess.run(command, check=True)
    return output_path, "converted"


class StretchMyClipApp:
    def __init__(self) -> None:
        root_cls = TkinterDnD.Tk if TkinterDnD else Tk
        self.root = root_cls()
        self.root.title(APP_TITLE)
        self.root.geometry("880x620")
        self.root.minsize(520, 360)
        self.root.configure(bg="#f6efe4")

        self.status_var = tk.StringVar(value="Waiting for a video file.")
        self.skip_16_9_var = tk.BooleanVar(value=True)
        self.replace_original_var = tk.BooleanVar(value=False)
        self.video_encoder, self.encoder_label = detect_best_video_encoder()

        self._build_ui()

        # Drag-and-drop is optional. The app still works as a click-to-select
        # file picker if tkinterdnd2 is not installed.
        if DND_FILES:
            self.drop_zone.drop_target_register(DND_FILES)
            self.drop_zone.dnd_bind("<<Drop>>", self.on_drop)

    def _build_ui(self) -> None:
        frame = tk.Frame(self.root, bg="#f6efe4", padx=24, pady=24)
        frame.pack(fill="both", expand=True)

        heading = tk.Label(
            frame,
            text="StretchMyClip!",
            font=(APP_FONT, 24, "bold"),
            bg="#f6efe4",
            fg="#2c2218",
        )
        heading.pack(pady=(8, 18))

        self.drop_zone = tk.Label(
            frame,
            text="Drag and drop your file(s)\nor press to select file",
            font=(APP_FONT, 18),
            justify="center",
            relief="ridge",
            bd=2,
            padx=24,
            pady=46,
            bg="#fffaf2",
            fg="#3a2f24",
            cursor="hand2",
        )
        self.drop_zone.pack(fill="both", expand=True)
        self.drop_zone.bind("<Button-1>", lambda _event: self.select_file())

        options_frame = tk.Frame(frame, bg="#f6efe4")
        options_frame.pack(fill="x", pady=(14, 0))

        skip_checkbox = tk.Checkbutton(
            options_frame,
            text="Skip videos already in 16:9",
            variable=self.skip_16_9_var,
            bg="#f6efe4",
            fg="#3a2f24",
            activebackground="#f6efe4",
            activeforeground="#3a2f24",
            selectcolor="#fffaf2",
            font=(APP_FONT, 10),
        )
        skip_checkbox.pack(anchor="w")

        replace_checkbox = tk.Checkbutton(
            options_frame,
            text="Replace old clips with stretched ones (move originals to Recycle Bin so you can retrive them just in case :3)",
            variable=self.replace_original_var,
            bg="#f6efe4",
            fg="#3a2f24",
            activebackground="#f6efe4",
            activeforeground="#3a2f24",
            selectcolor="#fffaf2",
            font=(APP_FONT, 10),
        )
        replace_checkbox.pack(anchor="w", pady=(6, 0))

        encoder_status = tk.Label(
            frame,
            text=f"Encoder: {self.encoder_label} ({self.video_encoder})",
            font=(APP_FONT, 10),
            bg="#f6efe4",
            fg="#6a5a4a",
        )
        encoder_status.pack(anchor="w", pady=(10, 0))

        status = tk.Label(
            frame,
            textvariable=self.status_var,
            font=(APP_FONT, 10),
            bg="#f6efe4",
            fg="#6a5a4a",
        )
        status.pack(pady=(14, 0))

    def run(self) -> None:
        self.root.mainloop()

    def select_file(self) -> None:
        file_paths = filedialog.askopenfilenames(
            title="Choose a video file",
            filetypes=SUPPORTED_VIDEO_TYPES,
        )
        if file_paths:
            self.process_videos([Path(file_path) for file_path in file_paths])

    def on_drop(self, event) -> None:
        raw_paths = self.root.tk.splitlist(event.data)
        self.process_videos([Path(raw_path) for raw_path in raw_paths])

    def process_videos(self, video_paths: list[Path]) -> None:
        # All selected files use the same current UI options for this batch.
        if not is_ffmpeg_available():
            messagebox.showerror(
                APP_TITLE,
                "ffmpeg and ffprobe are required in PATH before this app can process videos.",
            )
            return

        if self.replace_original_var.get() and send2trash is None:
            messagebox.showerror(
                APP_TITLE,
                "Replacing originals requires the send2trash package.\n\n"
                "Install it with: python -m pip install -r requirements.txt",
            )
            return

        valid_paths = [video_path for video_path in video_paths if video_path.exists()]
        if not valid_paths:
            messagebox.showerror(APP_TITLE, "No valid files were selected.")
            return

        confirm = messagebox.askyesno(
            APP_TITLE,
            f"Stretch {len(valid_paths)} video(s) to 16:9?\n\n"
            f"First file: {valid_paths[0].name}\n"
            f"Encoder: {self.encoder_label} ({self.video_encoder})",
        )
        if not confirm:
            self.status_var.set("Selection canceled.")
            return

        converted_files: list[Path] = []
        skipped_files: list[str] = []
        failed_files: list[str] = []
        replaced_files: list[str] = []

        total_files = len(valid_paths)
        for index, video_path in enumerate(valid_paths, start=1):
            self.status_var.set(f"Processing {index}/{total_files}: {video_path.name}")
            self.root.update_idletasks()

            try:
                output_path, result = stretch_video(
                    video_path,
                    self.skip_16_9_var.get(),
                    self.video_encoder,
                )
            except subprocess.CalledProcessError:
                failed_files.append(video_path.name)
                continue
            except (KeyError, IndexError, json.JSONDecodeError):
                failed_files.append(video_path.name)
                continue

            if result == "already_16_9":
                skipped_files.append(video_path.name)
            elif output_path:
                if self.replace_original_var.get():
                    try:
                        # Keep the original recoverable in the Recycle Bin,
                        # then put the converted file back at the original path.
                        original_path = video_path
                        temp_output_path = output_path.with_name(f"{video_path.stem}_replacement{video_path.suffix}")

                        if temp_output_path.exists():
                            temp_output_path.unlink()

                        output_path.replace(temp_output_path)
                        send2trash(str(original_path))
                        temp_output_path.replace(original_path)
                        converted_files.append(original_path)
                        replaced_files.append(video_path.name)
                    except OSError:
                        failed_files.append(video_path.name)
                        if temp_output_path.exists():
                            temp_output_path.replace(video_path)
                        continue
                else:
                    converted_files.append(output_path)

        if failed_files and not converted_files and not skipped_files:
            self.status_var.set("Processing failed.")
            messagebox.showerror(
                APP_TITLE,
                "None of the selected files could be processed.",
            )
            return

        self.status_var.set(
            f"Done. Converted {len(converted_files)}, skipped {len(skipped_files)}, failed {len(failed_files)}."
        )

        summary_lines = [
            f"Converted: {len(converted_files)}",
            f"Skipped (already 16:9): {len(skipped_files)}",
            f"Failed: {len(failed_files)}",
            f"Encoder used: {self.encoder_label} ({self.video_encoder})",
        ]

        if replaced_files:
            summary_lines.append(f"Replaced originals: {len(replaced_files)}")

        if converted_files:
            summary_lines.append("")
            summary_lines.append(f"Last saved file: {converted_files[-1].name}")

        if skipped_files:
            summary_lines.append("")
            summary_lines.append("Skipped because already 16:9:")
            summary_lines.extend(skipped_files[:5])

        if failed_files:
            summary_lines.append("")
            summary_lines.append("Failed:")
            summary_lines.extend(failed_files[:5])

        messagebox.showinfo(APP_TITLE, "\n".join(summary_lines))


def main() -> int:
    app = StretchMyClipApp()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
