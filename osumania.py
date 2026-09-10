import os
import sys
import math
import time
import wave
import random
import shutil
import tempfile
import subprocess
import threading
import urllib.request
import tkinter as tk
from tkinter import filedialog, messagebox

import numpy as np


# ============================================================
# ManiaTK
# 4K osu!mania-inspired rhythm game
# Python 3.14 compatible
# No pygame
#
# IMPORTANT:
# - Menu buttons are real Tkinter buttons and are rebuilt
#   whenever the screen changes.
# - Notes are locked to a detected beat grid.
# - Audio is played with FFplay.
# ============================================================

APP_NAME = "ManiaTK"
GAME_VERSION = "1.0.4"

DEFAULT_NOTE_SPEED = 420
MIN_NOTE_SPEED = 180
MAX_NOTE_SPEED = 900

DEFAULT_KEYS = ["d", "f", "j", "k"]

LANES = 4

DIFFICULTIES = {
    "Easy": {
        "threshold": 0.72,
        "subdivision": 1,
        "min_spacing": 0.50,
        "chords": False,
    },
    "Normal": {
        "threshold": 0.58,
        "subdivision": 1,
        "min_spacing": 0.25,
        "chords": False,
    },
    "Hard": {
        "threshold": 0.47,
        "subdivision": 2,
        "min_spacing": 0.125,
        "chords": True,
    },
    "Insane": {
        "threshold": 0.39,
        "subdivision": 2,
        "min_spacing": 0.125,
        "chords": True,
    },
    "Extreme": {
        "threshold": 0.31,
        "subdivision": 4,
        "min_spacing": 0.0625,
        "chords": True,
    },
    "Osu Pro": {
        "threshold": 0.24,
        "subdivision": 4,
        "min_spacing": 0.0625,
        "chords": True,
    },
}

GITHUB_VERSION_URL = (
    "https://raw.githubusercontent.com/"
    "mendozathird8-svg/My-Project/main/version.txt"
)


# ============================================================
# Utility
# ============================================================

def resource_path(filename):
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, filename)


def find_program(names):
    for name in names:
        path = shutil.which(name)
        if path:
            return path

        local = resource_path(name)
        if os.path.exists(local):
            return local

    return None


def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


# ============================================================
# FFPLAY AUDIO PLAYER
# ============================================================

class AudioPlayer:
    def __init__(self):
        self.process = None
        self.file = None
        self.position = 0.0
        self.started_at = None
        self.paused = False

        self.ffplay = find_program([
            "ffplay.exe",
            "ffplay"
        ])

    def available(self):
        return self.ffplay is not None

    def stop_process(self):
        if self.process:
            try:
                if self.process.poll() is None:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=0.5)
                    except Exception:
                        self.process.kill()
            except Exception:
                pass

        self.process = None

    def play(self, filename, position=0.0):
        if not self.ffplay:
            raise RuntimeError(
                "FFplay was not found.\n\n"
                "Install FFmpeg and make sure ffplay.exe is available."
            )

        self.stop_process()

        self.file = filename
        self.position = max(0.0, position)
        self.paused = False

        command = [
            self.ffplay,
            "-nodisp",
            "-autoexit",
            "-loglevel",
            "quiet",
            "-ss",
            str(self.position),
            "-i",
            filename,
        ]

        try:
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(
                    subprocess,
                    "CREATE_NO_WINDOW",
                    0
                ),
            )
        except Exception as e:
            self.process = None
            raise RuntimeError(
                "Could not start FFplay:\n\n" + str(e)
            )

        self.started_at = time.perf_counter()

    def get_position(self):
        if self.paused:
            return self.position

        if self.started_at is not None:
            return self.position + (
                time.perf_counter() - self.started_at
            )

        return self.position

    def pause(self):
        if not self.process:
            return

        self.position = self.get_position()
        self.paused = True

        self.stop_process()
        self.started_at = None

    def resume(self):
        if not self.file:
            return

        self.play(
            self.file,
            self.position
        )

    def stop(self):
        self.stop_process()
        self.position = 0.0
        self.started_at = None
        self.paused = False
        self.file = None


# ============================================================
# MAIN GAME
# ============================================================

class ManiaTK:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(
            f"{APP_NAME} {GAME_VERSION}"
        )

        self.root.geometry("1100x700")
        self.root.minsize(900, 600)

        self.root.configure(bg="#170000")

        self.canvas = tk.Canvas(
            self.root,
            bg="#170000",
            highlightthickness=0
        )
        self.canvas.pack(
            fill="both",
            expand=True
        )

        self.audio = AudioPlayer()

        self.screen = "menu"

        self.song_file = None
        self.wav_file = None
        self.temp_wav = None
        self.song_name = "No song selected"

        self.duration = 0.0
        self.bpm = 120.0
        self.beat_interval = 0.5
        self.beat_phase = 0.0

        self.onset_times = []
        self.onset_strengths = []

        self.notes = []

        self.selected_difficulty = "Normal"
        self.note_speed = DEFAULT_NOTE_SPEED

        self.keys = DEFAULT_KEYS.copy()

        self.score = 0
        self.combo = 0
        self.max_combo = 0

        self.perfects = 0
        self.greats = 0
        self.goods = 0
        self.okays = 0
        self.misses = 0

        self.pressed = [False] * LANES

        self.game_start_time = 0
        self.paused_position = 0

        self.menu_widgets = []

        self.analysis_running = False
        self.analysis_status = ""

        self.particles = []

        for _ in range(100):
            self.particles.append({
                "x": random.random(),
                "y": random.random(),
                "speed": random.uniform(
                    0.0002,
                    0.0012
                ),
                "size": random.randint(
                    1,
                    3
                )
            })

        self.root.bind(
            "<KeyPress>",
            self.key_down
        )

        self.root.bind(
            "<KeyRelease>",
            self.key_up
        )

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.close
        )

        self.show_menu()

        self.animate()

    # ========================================================
    # BACKGROUND
    # ========================================================

    def draw_background(self):
        self.canvas.delete("background")

        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()

        if width <= 1:
            return

        self.canvas.create_rectangle(
            0,
            0,
            width,
            height,
            fill="#170000",
            outline="",
            tags="background"
        )

        # Subtle red glow
        for i in range(8):
            margin = i * 30

            self.canvas.create_rectangle(
                margin,
                margin,
                width - margin,
                height - margin,
                outline="#2a0000",
                tags="background"
            )

        # Particles
        for p in self.particles:
            x = p["x"] * width
            y = p["y"] * height

            self.canvas.create_oval(
                x,
                y,
                x + p["size"],
                y + p["size"],
                fill="white",
                outline="",
                tags="background"
            )

    def animate(self):
        for p in self.particles:
            p["y"] += p["speed"]

            if p["y"] > 1.05:
                p["y"] = -0.05
                p["x"] = random.random()

        self.draw_background()

        if self.screen == "game":
            self.draw_game()

        elif self.screen == "pause":
            self.draw_pause()

        elif self.screen == "results":
            self.draw_results()

        elif self.screen == "analysis":
            self.draw_analysis()

        self.root.after(
            33,
            self.animate
        )

    # ========================================================
    # SCREEN HELPERS
    # ========================================================

    def clear_widgets(self):
        for widget in self.menu_widgets:
            try:
                widget.destroy()
            except Exception:
                pass

        self.menu_widgets.clear()

    def set_screen(self, screen):
        self.clear_widgets()
        self.screen = screen

    def make_button(
        self,
        text,
        command,
        x,
        y,
        width=300,
        height=52
    ):
        button = tk.Button(
            self.root,
            text=text,
            command=command,
            font=(
                "Arial",
                15,
                "bold"
            ),
            fg="white",
            bg="#6d0000",
            activeforeground="white",
            activebackground="#b00000",
            relief="flat",
            bd=0,
            cursor="hand2"
        )

        button.place(
            relx=x,
            rely=y,
            anchor="center",
            width=width,
            height=height
        )

        self.menu_widgets.append(button)

        return button

    def make_label(
        self,
        text,
        x,
        y,
        font=("Arial", 14),
        fg="white"
    ):
        label = tk.Label(
            self.root,
            text=text,
            font=font,
            fg=fg,
            bg="#170000"
        )

        label.place(
            relx=x,
            rely=y,
            anchor="center"
        )

        self.menu_widgets.append(label)

        return label

    # ========================================================
    # MAIN MENU
    # ========================================================

    def show_menu(self):
        self.set_screen("menu")

        self.make_label(
            "MANIATK",
            0.5,
            0.10,
            font=(
                "Arial",
                42,
                "bold"
            )
        )

        self.make_label(
            "4K Rhythm Game",
            0.5,
            0.17,
            font=(
                "Arial",
                16
            ),
            fg="#dddddd"
        )

        if self.song_file:
            song_text = (
                "Song: " +
                self.song_name
            )
        else:
            song_text = "Song: None"

        self.make_label(
            song_text,
            0.5,
            0.235,
            font=(
                "Arial",
                13
            ),
            fg="#bbbbbb"
        )

        self.make_button(
            "IMPORT SONG / VIDEO",
            self.import_song,
            0.5,
            0.34
        )

        self.make_button(
            "PASTE YOUTUBE LINK",
            self.youtube_dialog,
            0.5,
            0.43
        )

        self.make_button(
            "DIFFICULTY: " +
            self.selected_difficulty,
            self.show_difficulty,
            0.5,
            0.52
        )

        self.make_button(
            f"NOTE SPEED: {self.note_speed}",
            self.show_speed,
            0.5,
            0.61
        )

        self.make_button(
            "KEY SETTINGS",
            self.show_keys,
            0.5,
            0.70
        )

        self.make_button(
            "TUTORIAL",
            self.show_tutorial,
            0.5,
            0.79
        )

        self.make_button(
            "QUIT",
            self.close,
            0.5,
            0.88,
            width=180,
            height=44
        )

    # ========================================================
    # IMPORT
    # ========================================================

    def import_song(self):
        filename = filedialog.askopenfilename(
            title="Select a song or video",
            filetypes=[
                (
                    "Media files",
                    "*.mp3 *.mp4 *.wav *.ogg "
                    "*.m4a *.wma *.flac *.avi *.mkv"
                ),
                (
                    "All files",
                    "*.*"
                ),
            ]
        )

        if not filename:
            return

        self.song_file = filename
        self.song_name = os.path.basename(
            filename
        )

        self.start_analysis()

    # ========================================================
    # YOUTUBE
    # ========================================================

    def youtube_dialog(self):
        window = tk.Toplevel(self.root)

        window.title(
            "YouTube Song"
        )

        window.geometry(
            "600x190"
        )

        window.configure(
            bg="#170000"
        )

        tk.Label(
            window,
            text="Paste YouTube URL",
            font=(
                "Arial",
                18,
                "bold"
            ),
            fg="white",
            bg="#170000"
        ).pack(
            pady=20
        )

        entry = tk.Entry(
            window,
            font=(
                "Arial",
                13
            )
        )

        entry.pack(
            padx=30,
            fill="x"
        )

        def download():
            url = entry.get().strip()

            if not url:
                messagebox.showerror(
                    "Error",
                    "Paste a YouTube URL."
                )
                return

            try:
                import yt_dlp
            except ImportError:
                messagebox.showerror(
                    "yt-dlp missing",
                    "Install yt-dlp with:\n\n"
                    'py -3.14 -m pip install -U "yt-dlp[default]"'
                )
                return

            window.destroy()

            threading.Thread(
                target=self.download_youtube,
                args=(url,),
                daemon=True
            ).start()

        tk.Button(
            window,
            text="DOWNLOAD",
            command=download,
            bg="#700000",
            fg="white",
            activebackground="#b00000",
            activeforeground="white",
            relief="flat",
            font=(
                "Arial",
                12,
                "bold"
            )
        ).pack(
            pady=20,
            ipadx=30,
            ipady=5
        )

    def download_youtube(self, url):
        try:
            import yt_dlp

            folder = os.path.join(
                tempfile.gettempdir(),
                "ManiaTK"
            )

            os.makedirs(
                folder,
                exist_ok=True
            )

            output = os.path.join(
                folder,
                "youtube_audio.%(ext)s"
            )

            options = {
                "format":
                    "bestaudio[ext=m4a]/"
                    "bestaudio/best",

                "outtmpl":
                    output,

                "noplaylist":
                    True,

                "quiet":
                    True,

                "no_warnings":
                    True,

                "restrictfilenames":
                    True,
            }

            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(
                    url,
                    download=True
                )

                filename = ydl.prepare_filename(
                    info
                )

            self.root.after(
                0,
                lambda: self.youtube_finished(
                    filename,
                    info.get(
                        "title",
                        "YouTube Song"
                    )
                )
            )

        except Exception as e:
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "YouTube Error",
                    str(e)
                )
            )

    def youtube_finished(
        self,
        filename,
        title
    ):
        if not os.path.exists(filename):
            messagebox.showerror(
                "Error",
                "YouTube download failed."
            )
            return

        self.song_file = filename
        self.song_name = title

        self.start_analysis()

    # ========================================================
    # ANALYSIS
    # ========================================================

    def start_analysis(self):
        if not self.song_file:
            messagebox.showwarning(
                "No song",
                "Import a song or video first."
            )
            return

        self.set_screen("analysis")

        self.analysis_running = True
        self.analysis_status = (
            "Converting audio..."
        )

        threading.Thread(
            target=self.analysis_worker,
            daemon=True
        ).start()

    def analysis_worker(self):
        try:
            wav_file = self.convert_to_wav(
                self.song_file
            )

            samples, sample_rate, duration = (
                self.read_wav(wav_file)
            )

            self.analysis_status = (
                "Detecting rhythm..."
            )

            envelope, hop = (
                self.make_onset_envelope(
                    samples,
                    sample_rate
                )
            )

            self.analysis_status = (
                "Estimating BPM..."
            )

            bpm = self.estimate_bpm(
                envelope,
                hop,
                sample_rate
            )

            interval, bpm = (
                self.optimize_beat_interval(
                    envelope,
                    hop,
                    sample_rate,
                    bpm
                )
            )

            phase = self.find_beat_phase(
                envelope,
                hop,
                sample_rate,
                interval
            )

            self.duration = duration
            self.bpm = bpm
            self.beat_interval = interval
            self.beat_phase = phase

            self.onset_times = (
                np.arange(
                    len(envelope)
                ) *
                hop /
                sample_rate
            )

            self.onset_strengths = envelope

            self.wav_file = wav_file

            self.analysis_status = (
                "Building rhythm-locked chart..."
            )

            self.notes = (
                self.generate_rhythm_locked_chart(
                    envelope,
                    hop,
                    sample_rate,
                    duration
                )
            )

            self.analysis_running = False

            self.root.after(
                0,
                self.analysis_finished
            )

        except Exception as e:
            self.analysis_running = False

            self.root.after(
                0,
                lambda err=str(e):
                    messagebox.showerror(
                        "Analysis Error",
                        err
                    )
            )

            self.root.after(
                0,
                self.show_menu
            )

    def analysis_finished(self):
        self.show_difficulty()

    def draw_analysis(self):
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()

        self.canvas.create_text(
            width / 2,
            height * 0.38,
            text="ANALYZING SONG",
            fill="white",
            font=(
                "Arial",
                30,
                "bold"
            )
        )

        self.canvas.create_text(
            width / 2,
            height * 0.48,
            text=self.analysis_status,
            fill="#dddddd",
            font=(
                "Arial",
                16
            )
        )

        self.canvas.create_text(
            width / 2,
            height * 0.58,
            text="Please wait...",
            fill="#888888",
            font=(
                "Arial",
                13
            )
        )

    # ========================================================
    # FFMPEG
    # ========================================================

    def convert_to_wav(self, filename):
        ffmpeg = find_program([
            "ffmpeg.exe",
            "ffmpeg"
        ])

        if not ffmpeg:
            raise RuntimeError(
                "FFmpeg was not found.\n\n"
                "Install FFmpeg and make sure ffmpeg.exe "
                "is available."
            )

        temp_dir = os.path.join(
            tempfile.gettempdir(),
            "ManiaTK"
        )

        os.makedirs(
            temp_dir,
            exist_ok=True
        )

        output = os.path.join(
            temp_dir,
            "mania_audio.wav"
        )

        command = [
            ffmpeg,
            "-y",
            "-i",
            filename,
            "-vn",
            "-ac",
            "1",
            "-ar",
            "44100",
            "-sample_fmt",
            "s16",
            output,
        ]

        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=getattr(
                subprocess,
                "CREATE_NO_WINDOW",
                0
            )
        )

        if result.returncode != 0:
            error = result.stderr.decode(
                errors="ignore"
            )

            raise RuntimeError(
                "FFmpeg could not convert the file.\n\n"
                + error[-2000:]
            )

        return output

    def read_wav(self, filename):
        with wave.open(
            filename,
            "rb"
        ) as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            frames = wav.getnframes()

            raw = wav.readframes(
                frames
            )

        if sample_width == 1:
            data = np.frombuffer(
                raw,
                dtype=np.uint8
            ).astype(
                np.float32
            )

            data = (
                data - 128
            ) / 128.0

        elif sample_width == 2:
            data = np.frombuffer(
                raw,
                dtype=np.int16
            ).astype(
                np.float32
            ) / 32768.0

        elif sample_width == 4:
            data = np.frombuffer(
                raw,
                dtype=np.int32
            ).astype(
                np.float32
            ) / 2147483648.0

        else:
            raise RuntimeError(
                "Unsupported WAV sample format."
            )

        if channels > 1:
            data = data.reshape(
                -1,
                channels
            ).mean(
                axis=1
            )

        duration = len(data) / sample_rate

        return (
            data,
            sample_rate,
            duration
        )

    # ========================================================
    # AUDIO ANALYSIS
    # ========================================================

    def make_onset_envelope(
        self,
        samples,
        sample_rate
    ):
        frame_size = 2048
        hop = 256

        if len(samples) < frame_size:
            samples = np.pad(
                samples,
                (
                    0,
                    frame_size - len(samples)
                )
            )

        window = np.hanning(
            frame_size
        )

        count = (
            1 +
            (
                len(samples) -
                frame_size
            ) //
            hop
        )

        envelope = np.zeros(
            count,
            dtype=np.float32
        )

        previous = None

        for i in range(count):
            start = i * hop

            frame = samples[
                start:start + frame_size
            ]

            if len(frame) < frame_size:
                frame = np.pad(
                    frame,
                    (
                        0,
                        frame_size -
                        len(frame)
                    )
                )

            frame = frame * window

            spectrum = np.abs(
                np.fft.rfft(frame)
            )

            spectrum = np.log1p(
                spectrum
            )

            if previous is None:
                flux = 0.0
            else:
                difference = (
                    spectrum -
                    previous
                )

                flux = np.sum(
                    np.maximum(
                        difference,
                        0
                    )
                )

            previous = spectrum

            envelope[i] = flux

        # Smooth the envelope.
        kernel = np.ones(
            5,
            dtype=np.float32
        ) / 5.0

        envelope = np.convolve(
            envelope,
            kernel,
            mode="same"
        )

        low = np.percentile(
            envelope,
            5
        )

        high = np.percentile(
            envelope,
            95
        )

        envelope = (
            envelope - low
        ) / (
            high - low + 1e-9
        )

        envelope = np.clip(
            envelope,
            0,
            1
        )

        return (
            envelope,
            hop
        )

    def estimate_bpm(
        self,
        envelope,
        hop,
        sample_rate
    ):
        if len(envelope) < 10:
            return 120.0

        signal = (
            envelope -
            np.mean(envelope)
        )

        min_bpm = 65
        max_bpm = 190

        best_bpm = 120
        best_score = -1e30

        for bpm in np.linspace(
            min_bpm,
            max_bpm,
            251
        ):
            interval = (
                60.0 /
                bpm
            )

            lag = max(
                1,
                int(
                    interval *
                    sample_rate /
                    hop
                )
            )

            if lag >= len(signal):
                continue

            a = signal[:-lag]
            b = signal[lag:]

            score = float(
                np.dot(
                    a,
                    b
                )
            )

            if score > best_score:
                best_score = score
                best_bpm = bpm

        return float(best_bpm)

    def beat_grid_quality(
        self,
        envelope,
        hop,
        sample_rate,
        interval
    ):
        if interval <= 0:
            return -999999

        beat_frames = (
            interval *
            sample_rate /
            hop
        )

        if beat_frames < 1:
            return -999999

        positions = np.arange(
            0,
            len(envelope),
            beat_frames
        )

        indices = np.round(
            positions
        ).astype(int)

        indices = indices[
            indices < len(envelope)
        ]

        if len(indices) < 4:
            return -999999

        values = envelope[
            indices
        ]

        return float(
            np.mean(values) +
            0.25 *
            np.std(values)
        )

    def optimize_beat_interval(
        self,
        envelope,
        hop,
        sample_rate,
        bpm
    ):
        candidates = []

        for multiplier in (
            0.5,
            1.0,
            2.0
        ):
            candidate_bpm = (
                bpm *
                multiplier
            )

            if not (
                55 <= candidate_bpm <= 220
            ):
                continue

            for adjustment in np.linspace(
                0.97,
                1.03,
                13
            ):
                test_bpm = (
                    candidate_bpm *
                    adjustment
                )

                interval = (
                    60.0 /
                    test_bpm
                )

                quality = (
                    self.beat_grid_quality(
                        envelope,
                        hop,
                        sample_rate,
                        interval
                    )
                )

                candidates.append(
                    (
                        quality,
                        interval,
                        test_bpm
                    )
                )

        if not candidates:
            return (
                0.5,
                120.0
            )

        candidates.sort(
            reverse=True
        )

        _, interval, final_bpm = (
            candidates[0]
        )

        return (
            interval,
            final_bpm
        )

    def find_beat_phase(
        self,
        envelope,
        hop,
        sample_rate,
        interval
    ):
        beat_frames = (
            interval *
            sample_rate /
            hop
        )

        best_phase = 0.0
        best_score = -999999

        phase_count = 120

        for p in range(
            phase_count
        ):
            phase = (
                p /
                phase_count
            ) * interval

            start_frame = (
                phase *
                sample_rate /
                hop
            )

            positions = np.arange(
                start_frame,
                len(envelope),
                beat_frames
            )

            indices = np.round(
                positions
            ).astype(int)

            indices = indices[
                indices < len(envelope)
            ]

            if len(indices) < 4:
                continue

            values = envelope[
                indices
            ]

            score = (
                float(np.mean(values))
                +
                0.20 *
                float(np.std(values))
            )

            if score > best_score:
                best_score = score
                best_phase = phase

        return best_phase

    # ========================================================
    # RHYTHM-LOCKED CHART GENERATOR
    # ========================================================

    def generate_rhythm_locked_chart(
        self,
        envelope,
        hop,
        sample_rate,
        duration
    ):
        settings = DIFFICULTIES[
            self.selected_difficulty
        ]

        subdivision = settings[
            "subdivision"
        ]

        threshold = settings[
            "threshold"
        ]

        min_spacing = settings[
            "min_spacing"
        ]

        allow_chords = settings[
            "chords"
        ]

        beat = self.beat_interval
        step = beat / subdivision

        # ----------------------------------------------------
        # Normalize onset data.
        # ----------------------------------------------------

        energies = np.asarray(
            envelope,
            dtype=np.float32
        )

        if len(energies) == 0:
            return []

        # ----------------------------------------------------
        # Find strong local peaks.
        #
        # These peaks do NOT become note times directly.
        # Instead they are used to decide which positions
        # on the mathematical beat grid should contain notes.
        # ----------------------------------------------------

        peak_window = max(
            2,
            int(
                0.080 *
                sample_rate /
                hop
            )
        )

        peak_positions = []

        for i in range(
            peak_window,
            len(energies) -
            peak_window
        ):
            value = energies[i]

            left = energies[
                i - peak_window:i
            ]

            right = energies[
                i + 1:
                i + 1 + peak_window
            ]

            if (
                value >= np.max(left)
                and
                value >= np.max(right)
            ):
                peak_positions.append(
                    (
                        i *
                        hop /
                        sample_rate,
                        float(value)
                    )
                )

        # ----------------------------------------------------
        # Build exact grid.
        # ----------------------------------------------------

        grid = []

        t = self.beat_phase

        while t < duration:
            if t >= 0:
                grid.append(t)

            t += step

        # ----------------------------------------------------
        # For every grid point, find nearby audio energy.
        # This makes the chart rhythm-locked.
        # ----------------------------------------------------

        notes_by_time = {}

        last_note_time = -999.0

        for grid_time in grid:
            search_window = min(
                0.060,
                step * 0.30
            )

            best_strength = 0.0

            for peak_time, strength in peak_positions:
                difference = abs(
                    peak_time -
                    grid_time
                )

                if difference <= search_window:
                    if strength > best_strength:
                        best_strength = strength

            # Dynamic threshold depending on section energy.
            local_start = max(
                0,
                int(
                    (
                        grid_time -
                        0.50
                    ) *
                    sample_rate /
                    hop
                )
            )

            local_end = min(
                len(energies),
                int(
                    (
                        grid_time +
                        0.50
                    ) *
                    sample_rate /
                    hop
                )
            )

            if local_end > local_start:
                local = energies[
                    local_start:local_end
                ]

                local_average = float(
                    np.mean(local)
                )

                local_max = float(
                    np.max(local)
                )

                # The threshold is based on both the
                # global difficulty and local song energy.
                required = (
                    threshold *
                    (
                        0.55 +
                        0.45 *
                        local_average
                    )
                )

                required *= (
                    0.80 +
                    0.20 *
                    local_max
                )

            else:
                required = threshold

            # ------------------------------------------------
            # Strong peaks can activate a grid slot.
            # ------------------------------------------------

            if best_strength >= required:
                if (
                    grid_time -
                    last_note_time
                ) < min_spacing:
                    continue

                notes_by_time[
                    round(
                        grid_time,
                        6
                    )
                ] = best_strength

                last_note_time = grid_time

        # ----------------------------------------------------
        # Add stronger subdivisions in harder difficulties.
        # ----------------------------------------------------

        if subdivision >= 2:
            # Look at every grid slot and allow especially
            # strong audio peaks through.
            for grid_time in grid:
                if grid_time in notes_by_time:
                    continue

                best_strength = 0.0

                for peak_time, strength in peak_positions:
                    difference = abs(
                        peak_time -
                        grid_time
                    )

                    if difference <= (
                        step * 0.28
                    ):
                        best_strength = max(
                            best_strength,
                            strength
                        )

                if best_strength >= (
                    threshold * 1.30
                ):
                    notes_by_time[
                        round(
                            grid_time,
                            6
                        )
                    ] = best_strength

        # ----------------------------------------------------
        # Sort exact rhythm positions.
        # ----------------------------------------------------

        times = sorted(
            notes_by_time.keys()
        )

        # ----------------------------------------------------
        # Lane assignment.
        #
        # Deterministic patterns avoid random-looking charts.
        # ----------------------------------------------------

        chart = []

        previous_lane = -1

        for index, note_time in enumerate(
            times
        ):
            strength = notes_by_time[
                note_time
            ]

            if allow_chords:
                # Stronger beats can become chords.
                is_chord = (
                    strength >=
                    max(
                        0.80,
                        threshold + 0.25
                    )
                    and
                    index % 4 == 0
                )
            else:
                is_chord = False

            # Musical-ish repeating lane pattern.
            pattern = [
                0, 1, 2, 3,
                1, 3, 0, 2,
                3, 2, 1, 0,
            ]

            lane = pattern[
                index %
                len(pattern)
            ]

            if lane == previous_lane:
                lane = (
                    lane + 1
                ) % LANES

            lanes = [lane]

            if is_chord:
                second = (
                    lane + 2
                ) % LANES

                lanes.append(
                    second
                )

            for lane_number in lanes:
                chart.append({
                    "time": note_time,
                    "lane": lane_number,
                    "hit": False,
                    "missed": False,
                    "judgement": None,
                })

            previous_lane = lane

        chart.sort(
            key=lambda n: (
                n["time"],
                n["lane"]
            )
        )

        return chart

    # ========================================================
    # DIFFICULTY
    # ========================================================

    def show_difficulty(self):
        self.set_screen(
            "difficulty"
        )

        self.make_label(
            "SELECT DIFFICULTY",
            0.5,
            0.10,
            font=(
                "Arial",
                30,
                "bold"
            )
        )

        self.make_label(
            f"BPM: {self.bpm:.1f}",
            0.5,
            0.17,
            font=(
                "Arial",
                13
            ),
            fg="#bbbbbb"
        )

        names = list(
            DIFFICULTIES.keys()
        )

        y = 0.27

        for name in names:
            def choose(
                difficulty=name
            ):
                self.selected_difficulty = (
                    difficulty
                )

                if self.song_file:
                    self.rebuild_chart()
                else:
                    self.show_menu()

            self.make_button(
                name,
                choose,
                0.5,
                y,
                width=300,
                height=45
            )

            y += 0.09

        self.make_button(
            "BACK",
            self.show_menu,
            0.5,
            0.91,
            width=180,
            height=40
        )

    def rebuild_chart(self):
        self.set_screen(
            "analysis"
        )

        self.analysis_running = True
        self.analysis_status = (
            "Building chart..."
        )

        threading.Thread(
            target=self.rebuild_chart_worker,
            daemon=True
        ).start()

    def rebuild_chart_worker(self):
        try:
            samples, sample_rate, duration = (
                self.read_wav(
                    self.wav_file
                )
            )

            envelope, hop = (
                self.make_onset_envelope(
                    samples,
                    sample_rate
                )
            )

            self.notes = (
                self.generate_rhythm_locked_chart(
                    envelope,
                    hop,
                    sample_rate,
                    duration
                )
            )

            self.analysis_running = False

            self.root.after(
                0,
                self.start_game
            )

        except Exception as e:
            self.analysis_running = False

            self.root.after(
                0,
                lambda err=str(e):
                    messagebox.showerror(
                        "Chart Error",
                        err
                    )
            )

            self.root.after(
                0,
                self.show_menu
            )

    # ========================================================
    # NOTE SPEED
    # ========================================================

    def show_speed(self):
        self.set_screen(
            "speed"
        )

        self.make_label(
            "NOTE SPEED",
            0.5,
            0.15,
            font=(
                "Arial",
                30,
                "bold"
            )
        )

        value_label = self.make_label(
            str(self.note_speed),
            0.5,
            0.29,
            font=(
                "Arial",
                24,
                "bold"
            )
        )

        slider = tk.Scale(
            self.root,
            from_=MIN_NOTE_SPEED,
            to=MAX_NOTE_SPEED,
            orient="horizontal",
            length=500,
            bg="#170000",
            fg="white",
            troughcolor="#4a0000",
            highlightthickness=0,
            showvalue=False,
            command=lambda value:
                value_label.config(
                    text=str(
                        int(float(value))
                    )
                )
        )

        slider.set(
            self.note_speed
        )

        slider.place(
            relx=0.5,
            rely=0.42,
            anchor="center"
        )

        self.menu_widgets.append(
            slider
        )

        def save():
            self.note_speed = int(
                slider.get()
            )

            self.show_menu()

        self.make_button(
            "SAVE",
            save,
            0.5,
            0.57,
            width=200
        )

        self.make_button(
            "BACK",
            self.show_menu,
            0.5,
            0.67,
            width=200
        )

    # ========================================================
    # KEY SETTINGS
    # ========================================================

    def show_keys(self):
        self.set_screen(
            "keys"
        )

        self.make_label(
            "KEY SETTINGS",
            0.5,
            0.12,
            font=(
                "Arial",
                30,
                "bold"
            )
        )

        self.make_label(
            "Click a key and press the new keyboard key",
            0.5,
            0.20,
            font=(
                "Arial",
                13
            ),
            fg="#bbbbbb"
        )

        entries = []

        for lane in range(LANES):
            y = (
                0.32 +
                lane * 0.10
            )

            self.make_label(
                f"Lane {lane + 1}",
                0.37,
                y,
                font=(
                    "Arial",
                    14,
                    "bold"
                )
            )

            entry = tk.Entry(
                self.root,
                justify="center",
                font=(
                    "Arial",
                    14,
                    "bold"
                ),
                bg="#350000",
                fg="white",
                insertbackground="white",
                relief="flat"
            )

            entry.insert(
                0,
                self.keys[lane]
            )

            entry.place(
                relx=0.60,
                rely=y,
                anchor="center",
                width=100,
                height=35
            )

            entries.append(entry)
            self.menu_widgets.append(
                entry
            )

        def save():
            new_keys = []

            for entry in entries:
                key = entry.get().strip().lower()

                if len(key) != 1:
                    messagebox.showerror(
                        "Invalid key",
                        "Each lane must use exactly one key."
                    )
                    return

                new_keys.append(
                    key
                )

            if len(
                set(new_keys)
            ) != LANES:
                messagebox.showerror(
                    "Duplicate keys",
                    "Each lane must have a different key."
                )
                return

            if "escape" in new_keys:
                messagebox.showerror(
                    "Invalid key",
                    "ESC is reserved for pause."
                )
                return

            self.keys = new_keys

            self.show_menu()

        self.make_button(
            "SAVE",
            save,
            0.5,
            0.77,
            width=200
        )

        self.make_button(
            "RESET DEFAULTS",
            self.reset_keys,
            0.5,
            0.85,
            width=200
        )

        self.make_button(
            "BACK",
            self.show_menu,
            0.5,
            0.93,
            width=160,
            height=35
        )

    def reset_keys(self):
        self.keys = DEFAULT_KEYS.copy()
        self.show_keys()

    # ========================================================
    # TUTORIAL
    # ========================================================

    def show_tutorial(self):
        self.set_screen(
            "tutorial"
        )

        self.make_label(
            "HOW TO PLAY",
            0.5,
            0.10,
            font=(
                "Arial",
                30,
                "bold"
            )
        )

        text = (
            "Notes fall toward the hit line.\n\n"
            "Press the matching keyboard key "
            "when the note reaches the line.\n\n"
            f"Lane 1 = {self.keys[0].upper()}\n"
            f"Lane 2 = {self.keys[1].upper()}\n"
            f"Lane 3 = {self.keys[2].upper()}\n"
            f"Lane 4 = {self.keys[3].upper()}\n\n"
            "ESC = Pause\n\n"
            "Perfect = 300\n"
            "Great = 200\n"
            "Good = 100\n"
            "OK = 50\n\n"
            "Missing a note breaks your combo."
        )

        self.make_label(
            text,
            0.5,
            0.48,
            font=(
                "Arial",
                15
            )
        )

        self.make_button(
            "BACK",
            self.show_menu,
            0.5,
            0.88,
            width=200
        )

    # ========================================================
    # KEYBOARD INPUT
    # ========================================================

    def key_down(self, event):
        key = event.keysym.lower()

        if key == "escape":
            if self.screen == "game":
                self.pause_game()

            elif self.screen == "pause":
                self.resume_game()

            return

        if self.screen != "game":
            return

        for lane in range(LANES):
            if key == self.keys[lane]:
                if not self.pressed[lane]:
                    self.pressed[lane] = True
                    self.hit_lane(lane)

                return

    def key_up(self, event):
        key = event.keysym.lower()

        for lane in range(LANES):
            if key == self.keys[lane]:
                self.pressed[lane] = False

    # ========================================================
    # GAME START
    # ========================================================

    def start_game(self):
        if not self.wav_file:
            messagebox.showerror(
                "Error",
                "No analyzed audio."
            )
            self.show_menu()
            return

        if not self.audio.available():
            messagebox.showerror(
                "FFplay missing",
                "FFplay was not found."
            )
            self.show_menu()
            return

        self.score = 0
        self.combo = 0
        self.max_combo = 0

        self.perfects = 0
        self.greats = 0
        self.goods = 0
        self.okays = 0
        self.misses = 0

        for note in self.notes:
            note["hit"] = False
            note["missed"] = False
            note["judgement"] = None

        self.pressed = [
            False
        ] * LANES

        self.set_screen(
            "game"
        )

        try:
            self.audio.play(
                self.wav_file,
                0.0
            )
        except Exception as e:
            messagebox.showerror(
                "Audio Error",
                str(e)
            )
            self.show_menu()
            return

        self.game_start_time = (
            time.perf_counter()
        )

    # ========================================================
    # GAME LOOP
    # ========================================================

    def hit_lane(self, lane):
        position = self.audio.get_position()

        candidates = []

        for note in self.notes:
            if note["lane"] != lane:
                continue

            if note["hit"] or note["missed"]:
                continue

            difference = (
                note["time"] -
                position
            )

            if abs(difference) <= 0.16:
                candidates.append(
                    (
                        abs(difference),
                        note
                    )
                )

        if not candidates:
            # Pressing when no note is present does nothing.
            return

        candidates.sort(
            key=lambda item: item[0]
        )

        difference, note = (
            candidates[0]
        )

        error_ms = abs(
            difference
        ) * 1000.0

        if error_ms <= 25:
            judgement = "PERFECT"
            points = 300
            self.perfects += 1

        elif error_ms <= 60:
            judgement = "GREAT"
            points = 200
            self.greats += 1

        elif error_ms <= 100:
            judgement = "GOOD"
            points = 100
            self.goods += 1

        elif error_ms <= 150:
            judgement = "OK"
            points = 50
            self.okays += 1

        else:
            return

        note["hit"] = True
        note["judgement"] = judgement

        self.combo += 1

        self.max_combo = max(
            self.max_combo,
            self.combo
        )

        bonus = min(
            self.combo * 2,
            500
        )

        self.score += (
            points +
            bonus
        )

    def check_misses(self, position):
        for note in self.notes:
            if (
                note["hit"]
                or
                note["missed"]
            ):
                continue

            if (
                position -
                note["time"]
            ) > 0.15:

                note["missed"] = True
                note["judgement"] = "MISS"

                self.misses += 1
                self.combo = 0

    # ========================================================
    # GAME DRAWING
    # ========================================================

    def draw_game(self):
        if self.screen != "game":
            return

        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()

        if width <= 1:
            return

        position = self.audio.get_position()

        self.check_misses(
            position
        )

        if (
            self.duration > 0
            and
            position >= self.duration
        ):
            self.finish_game()
            return

        # Game area.
        game_width = min(
            560,
            width * 0.62
        )

        left = (
            width -
            game_width
        ) / 2

        right = (
            width +
            game_width
        ) / 2

        top = 80
        hit_y = height - 130

        lane_width = (
            game_width /
            LANES
        )

        # Header.
        self.canvas.create_text(
            30,
            25,
            anchor="w",
            text=f"Score: {self.score}",
            fill="white",
            font=(
                "Arial",
                16,
                "bold"
            )
        )

        self.canvas.create_text(
            width - 30,
            25,
            anchor="e",
            text=f"Combo: {self.combo}",
            fill="white",
            font=(
                "Arial",
                16,
                "bold"
            )
        )

        # Song title.
        self.canvas.create_text(
            width / 2,
            25,
            text=self.song_name,
            fill="#bbbbbb",
            font=(
                "Arial",
                11
            )
        )

        # Lanes.
        for lane in range(LANES):
            x1 = (
                left +
                lane *
                lane_width
            )

            x2 = (
                x1 +
                lane_width
            )

            lane_color = (
                "#260000"
                if not self.pressed[lane]
                else "#750000"
            )

            self.canvas.create_rectangle(
                x1,
                top,
                x2,
                hit_y + 45,
                fill=lane_color,
                outline="#4b0000"
            )

        # Hit line.
        self.canvas.create_rectangle(
            left,
            hit_y - 5,
            right,
            hit_y + 5,
            fill="white",
            outline=""
        )

        # Key labels.
        for lane in range(LANES):
            x = (
                left +
                lane *
                lane_width +
                lane_width / 2
            )

            self.canvas.create_text(
                x,
                hit_y + 28,
                text=self.keys[lane].upper(),
                fill="white",
                font=(
                    "Arial",
                    16,
                    "bold"
                )
            )

        # Notes.
        travel_time = (
            600 /
            self.note_speed
        )

        for note in self.notes:
            if (
                note["hit"]
                or
                note["missed"]
            ):
                continue

            time_until = (
                note["time"] -
                position
            )

            if time_until < -0.2:
                continue

            if time_until > travel_time:
                continue

            progress = (
                1.0 -
                max(
                    0.0,
                    time_until /
                    travel_time
                )
            )

            y = (
                top +
                progress *
                (
                    hit_y -
                    top
                )
            )

            x1 = (
                left +
                note["lane"] *
                lane_width +
                8
            )

            x2 = (
                left +
                (
                    note["lane"] +
                    1
                ) *
                lane_width -
                8
            )

            self.draw_arrow(
                x1,
                x2,
                y,
                22
            )

        # Progress.
        if self.duration > 0:
            progress = min(
                1.0,
                position /
                self.duration
            )

            self.canvas.create_rectangle(
                20,
                height - 25,
                width - 20,
                height - 20,
                fill="#350000",
                outline=""
            )

            self.canvas.create_rectangle(
                20,
                height - 25,
                20 +
                (
                    width -
                    40
                ) *
                progress,
                height - 20,
                fill="white",
                outline=""
            )

        # Pause hint.
        self.canvas.create_text(
            width / 2,
            height - 50,
            text="ESC = PAUSE",
            fill="#888888",
            font=(
                "Arial",
                10
            )
        )

    def draw_arrow(
        self,
        x1,
        x2,
        y,
        half_height
    ):
        center = (
            x1 + x2
        ) / 2

        width = (
            x2 - x1
        )

        points = [
            x1,
            y - half_height * 0.35,

            center,
            y + half_height,

            x2,
            y - half_height * 0.35,

            x2,
            y - half_height,

            center,
            y - half_height * 0.05,

            x1,
            y - half_height,
        ]

        self.canvas.create_polygon(
            points,
            fill="white",
            outline="#dddddd"
        )

    # ========================================================
    # PAUSE
    # ========================================================

    def pause_game(self):
        if self.screen != "game":
            return

        self.paused_position = (
            self.audio.get_position()
        )

        self.audio.pause()

        self.set_screen(
            "pause"
        )

        self.make_label(
            "PAUSED",
            0.5,
            0.25,
            font=(
                "Arial",
                40,
                "bold"
            )
        )

        self.make_button(
            "RESUME",
            self.resume_game,
            0.5,
            0.43
        )

        self.make_button(
            "QUIT BEATMAP",
            self.quit_beatmap,
            0.5,
            0.54
        )

        self.make_button(
            "MAIN MENU",
            self.quit_to_menu,
            0.5,
            0.65
        )

    def draw_pause(self):
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()

        self.canvas.create_rectangle(
            0,
            0,
            width,
            height,
            fill="#170000",
            stipple="gray50",
            outline=""
        )

    def resume_game(self):
        if self.screen != "pause":
            return

        self.set_screen(
            "game"
        )

        try:
            self.audio.resume()
        except Exception as e:
            messagebox.showerror(
                "Audio Error",
                str(e)
            )
            self.show_menu()

    def quit_beatmap(self):
        self.audio.stop()
        self.show_menu()

    def quit_to_menu(self):
        self.audio.stop()
        self.show_menu()

    # ========================================================
    # RESULTS
    # ========================================================

    def finish_game(self):
        if self.screen != "game":
            return

        self.audio.stop()

        self.screen = "results"

        self.clear_widgets()

        self.make_label(
            "RESULTS",
            0.5,
            0.10,
            font=(
                "Arial",
                36,
                "bold"
            )
        )

        total = (
            self.perfects +
            self.greats +
            self.goods +
            self.okays +
            self.misses
        )

        if total > 0:
            accuracy = (
                (
                    self.perfects * 100
                    +
                    self.greats * 66.6667
                    +
                    self.goods * 33.3333
                    +
                    self.okays * 16.6667
                )
                /
                total
            )
        else:
            accuracy = 0.0

        result_text = (
            f"Score: {self.score}\n\n"
            f"Accuracy: {accuracy:.2f}%\n\n"
            f"Max Combo: {self.max_combo}\n\n"
            f"Perfect: {self.perfects}\n"
            f"Great: {self.greats}\n"
            f"Good: {self.goods}\n"
            f"OK: {self.okays}\n"
            f"Miss: {self.misses}\n\n"
            f"BPM: {self.bpm:.1f}"
        )

        self.make_label(
            result_text,
            0.5,
            0.48,
            font=(
                "Arial",
                15
            )
        )

        self.make_button(
            "PLAY AGAIN",
            self.start_game,
            0.5,
            0.79,
            width=220
        )

        self.make_button(
            "MAIN MENU",
            self.show_menu,
            0.5,
            0.88,
            width=220
        )

    def draw_results(self):
        pass

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self):
        try:
            self.audio.stop()
        except Exception:
            pass

        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        self.root.mainloop()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    app = ManiaTK()
    app.run()
