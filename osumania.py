# ============================================================
# ManiaTK - 4K Rhythm Game
# Python 3.14 compatible
# No pygame
#
# Features:
#   - 4K gameplay
#   - FNF-style arrow notes
#   - D/F/J/K controls
#   - Adjustable note speed
#   - BPM / beat-grid based chart generation
#   - Audio onset detection
#   - Key press glow
#   - Hit glow / hit effects
#   - 6 difficulties
#   - MP3 / MP4 / WAV / OGG / M4A / WMA / FLAC / AVI / MKV
#   - FFmpeg conversion
#   - Pause menu
#   - Results screen
#   - Tutorial
#   - Animated background + particles
#
# Install:
#   pip install numpy
#
# FFmpeg:
#   Put ffmpeg.exe and ffplay.exe in PATH,
#   or place them beside this .py file.
# ============================================================

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


try:
    import numpy as np
except ImportError:
    raise SystemExit(
        "NumPy is required.\n\n"
        "Install it with:\n"
        "pip install numpy"
    )


# ============================================================
# SETTINGS
# ============================================================

APP_NAME = "ManiaTK"
GAME_VERSION = "1.0.1"

GITHUB_VERSION_URL = (
    "https://raw.githubusercontent.com/"
    "mendozathird8-svg/My-Project/main/version.txt"
)

LANES = 4
DEFAULT_KEYS = ["d", "f", "j", "k"]

WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 700

LANE_WIDTH = 105
LANE_GAP = 5

JUDGEMENT_Y = 610

# Default falling speed.
# Higher = faster notes.
DEFAULT_NOTE_SPEED = 420

MIN_NOTE_SPEED = 180
MAX_NOTE_SPEED = 900

# Timing windows
PERFECT_WINDOW = 0.025
GREAT_WINDOW = 0.060
GOOD_WINDOW = 0.100
MISS_WINDOW = 0.150


# ============================================================
# DIFFICULTIES
# ============================================================

DIFFICULTIES = {
    "EASY": {
        "description": "Slow patterns with mostly full beats.",
        "subdivision": 1,
        "density": 0.45,
        "chords": False,
    },

    "NORMAL": {
        "description": "More notes with occasional chords.",
        "subdivision": 1,
        "density": 0.65,
        "chords": True,
    },

    "HARD": {
        "description": "Beat subdivisions and frequent chords.",
        "subdivision": 2,
        "density": 0.78,
        "chords": True,
    },

    "INSANE": {
        "description": "Fast patterns with dense subdivisions.",
        "subdivision": 2,
        "density": 0.90,
        "chords": True,
    },

    "EXTREME": {
        "description": "Very dense rhythm patterns.",
        "subdivision": 4,
        "density": 0.95,
        "chords": True,
    },

    "OSU PRO (MY BROTHER)": {
        "description": "Maximum density and aggressive patterns.",
        "subdivision": 4,
        "density": 1.0,
        "chords": True,
    },
}


# ============================================================
# UTILITY
# ============================================================

def resource_path(filename):
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base, filename)


def find_program(name):
    local = resource_path(name)

    if os.path.isfile(local):
        return local

    found = shutil.which(name)

    if found:
        return found

    return None


FFMPEG = find_program("ffmpeg.exe")
FFPLAY = find_program("ffplay.exe")


# ============================================================
# AUDIO PLAYER
# ============================================================

class AudioPlayer:
    def __init__(self):
        self.process = None
        self.start_time = 0.0
        self.pause_position = 0.0
        self.path = None
        self.playing = False
        self.paused = False

    def play(self, path, start_position=0.0):
        self.stop()

        self.path = path
        self.pause_position = start_position

        if not FFPLAY:
            messagebox.showerror(
                "FFplay missing",
                "ffplay.exe could not be found.\n\n"
                "Put ffplay.exe beside osumania.py "
                "or add FFmpeg to PATH."
            )
            return False

        cmd = [
            FFPLAY,
            "-nodisp",
            "-autoexit",
            "-loglevel",
            "quiet",
        ]

        if start_position > 0:
            cmd += [
                "-ss",
                str(start_position)
            ]

        cmd.append(path)

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            self.start_time = time.perf_counter()
            self.playing = True
            self.paused = False

            return True

        except Exception as e:
            messagebox.showerror(
                "Audio error",
                str(e)
            )

            return False

    def pause(self):
        if not self.playing:
            return self.pause_position

        self.pause_position = self.get_position()

        self.stop_process_only()

        self.playing = False
        self.paused = True

        return self.pause_position

    def resume(self):
        if not self.path:
            return False

        return self.play(
            self.path,
            self.pause_position
        )

    def get_position(self):
        if not self.playing:
            return self.pause_position

        return (
            self.pause_position
            + (time.perf_counter() - self.start_time)
        )

    def stop_process_only(self):
        if self.process:

            try:
                self.process.kill()
            except Exception:
                pass

            self.process = None

    def stop(self):
        self.stop_process_only()

        self.playing = False
        self.paused = False
        self.pause_position = 0.0

    def finished(self):
        if not self.playing:
            return False

        if self.process is None:
            return False

        return self.process.poll() is not None


# ============================================================
# AUDIO ANALYSIS
# ============================================================

def convert_to_wav(input_file):
    """
    Converts any FFmpeg-supported audio/video file to WAV.
    """

    global FFMPEG

    if not FFMPEG:
        raise RuntimeError(
            "ffmpeg.exe was not found.\n\n"
            "Put ffmpeg.exe beside osumania.py "
            "or add FFmpeg to PATH."
        )

    temp_dir = tempfile.mkdtemp(
        prefix="maniatk_audio_"
    )

    wav_path = os.path.join(
        temp_dir,
        "audio.wav"
    )

    cmd = [
        FFMPEG,
        "-y",
        "-i",
        input_file,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "44100",
        "-sample_fmt",
        "s16",
        wav_path,
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    if result.returncode != 0:
        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )

        raise RuntimeError(
            "FFmpeg could not convert the audio.\n\n"
            + result.stderr.decode(
                errors="ignore"
            )[-1500:]
        )

    return wav_path, temp_dir


def read_wav(path):
    with wave.open(path, "rb") as wf:

        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        frames = wf.getnframes()

        raw = wf.readframes(frames)

    if sample_width == 2:

        audio = np.frombuffer(
            raw,
            dtype=np.int16
        ).astype(np.float32) / 32768.0

    elif sample_width == 1:

        audio = (
            np.frombuffer(
                raw,
                dtype=np.uint8
            ).astype(np.float32)
            - 128
        ) / 128.0

    elif sample_width == 4:

        audio = np.frombuffer(
            raw,
            dtype=np.int32
        ).astype(np.float32) / 2147483648.0

    else:
        raise RuntimeError(
            "Unsupported WAV sample width."
        )

    if channels > 1:

        audio = audio.reshape(
            -1,
            channels
        )

        audio = np.mean(
            audio,
            axis=1
        )

    return audio, sample_rate


# ============================================================
# BPM DETECTION
# ============================================================

def estimate_bpm(audio, sample_rate):
    """
    Estimates BPM using an onset-strength autocorrelation.

    This is deliberately lightweight so it can run without
    librosa or other large audio libraries.
    """

    if len(audio) < sample_rate * 2:
        return 120.0

    # Work at approximately 100 Hz.
    hop = max(
        1,
        int(sample_rate / 100)
    )

    frame = max(
        256,
        int(sample_rate * 0.040)
    )

    count = max(
        1,
        (len(audio) - frame) // hop
    )

    energy = np.zeros(count)

    window = np.hanning(frame)

    for i in range(count):

        start = i * hop
        chunk = audio[
            start:start + frame
        ]

        if len(chunk) < frame:
            break

        energy[i] = np.sqrt(
            np.mean(
                (chunk * window) ** 2
            )
        )

    if len(energy) < 20:
        return 120.0

    # Onset strength = positive energy changes.
    onset = np.maximum(
        0,
        np.diff(energy)
    )

    onset = onset - np.mean(onset)

    # BPM search.
    #
    # 50-200 BPM.
    candidates = np.arange(
        50.0,
        201.0,
        1.0
    )

    best_bpm = 120.0
    best_score = -np.inf

    for bpm in candidates:

        period_seconds = 60.0 / bpm

        lag = int(
            period_seconds * 100
        )

        if lag <= 0 or lag >= len(onset):
            continue

        score = float(
            np.dot(
                onset[:-lag],
                onset[lag:]
            )
        )

        if score > best_score:

            best_score = score
            best_bpm = bpm

    # Prefer musical BPM range.
    while best_bpm < 75:
        best_bpm *= 2

    while best_bpm > 180:
        best_bpm /= 2

    return float(best_bpm)


# ============================================================
# ONSET DETECTION
# ============================================================

def calculate_onsets(audio, sample_rate):
    """
    Creates a normalized onset-strength envelope.
    """

    hop = max(
        1,
        int(sample_rate * 0.010)
    )

    frame = max(
        512,
        int(sample_rate * 0.040)
    )

    count = max(
        1,
        (len(audio) - frame) // hop
    )

    energy = np.zeros(count)

    window = np.hanning(frame)

    for i in range(count):

        start = i * hop

        chunk = audio[
            start:start + frame
        ]

        if len(chunk) < frame:
            break

        energy[i] = np.sqrt(
            np.mean(
                (chunk * window) ** 2
            )
        )

    if len(energy) < 4:
        return np.array([])

    onset = np.maximum(
        0,
        np.diff(energy)
    )

    # Smooth slightly.
    smooth_size = 3

    kernel = np.ones(
        smooth_size
    ) / smooth_size

    onset = np.convolve(
        onset,
        kernel,
        mode="same"
    )

    max_value = np.max(onset)

    if max_value > 0:
        onset /= max_value

    return onset


# ============================================================
# CHART GENERATOR
# ============================================================

def choose_lane(previous_lane):
    possible = [
        0,
        1,
        2,
        3,
    ]

    if previous_lane in possible:
        possible.remove(previous_lane)

    return random.choice(
        possible
    )


def generate_chart(
    audio,
    sample_rate,
    difficulty_name
):
    """
    Generates a beat-grid chart.

    Important difference from the old generator:
    Notes are NOT placed at arbitrary waveform peaks.

    Instead:
      1. Estimate BPM.
      2. Build a musical beat grid.
      3. Check onset strength around each beat.
      4. Place notes ON the grid.
      5. Add subdivisions for harder difficulties.
    """

    difficulty = DIFFICULTIES[
        difficulty_name
    ]

    bpm = estimate_bpm(
        audio,
        sample_rate
    )

    beat = 60.0 / bpm

    duration = (
        len(audio) / sample_rate
    )

    onset = calculate_onsets(
        audio,
        sample_rate
    )

    if len(onset) == 0:
        return [], bpm

    # Onset samples represent 10 ms-ish intervals.
    onset_step = 0.010

    def onset_at(t):
        index = int(
            t / onset_step
        )

        if index < 0:
            return 0.0

        if index >= len(onset):
            return 0.0

        return float(
            onset[index]
        )

    # --------------------------------------------------------
    # Find a sensible song offset.
    #
    # This avoids forcing the first note exactly at 0.0.
    # --------------------------------------------------------

    search_end = min(
        duration,
        8.0
    )

    offset_candidates = np.arange(
        0.0,
        search_end,
        0.010
    )

    if len(offset_candidates):

        strengths = [
            onset_at(float(x))
            for x in offset_candidates
        ]

        strongest = max(
            range(len(strengths)),
            key=lambda i: strengths[i]
        )

        first_onset = float(
            offset_candidates[strongest]
        )

        # Don't make a huge offset.
        first_onset = min(
            first_onset,
            beat * 2
        )

    else:
        first_onset = 0.0

    # Snap starting point to beat.
    grid_offset = first_onset

    # --------------------------------------------------------
    # Determine onset threshold adaptively.
    # --------------------------------------------------------

    valid_onsets = onset[
        onset > 0.02
    ]

    if len(valid_onsets):

        threshold = float(
            np.percentile(
                valid_onsets,
                45
            )
        )

        threshold = max(
            0.08,
            min(
                threshold,
                0.45
            )
        )

    else:
        threshold = 0.12

    notes = []

    previous_lane = random.randrange(4)

    previous_time = -999.0

    subdivision = difficulty[
        "subdivision"
    ]

    density = difficulty[
        "density"
    ]

    allow_chords = difficulty[
        "chords"
    ]

    # --------------------------------------------------------
    # Build grid.
    # --------------------------------------------------------

    step = beat / subdivision

    # Safety limit.
    max_notes = 5000

    t = grid_offset

    while (
        t < duration
        and len(notes) < max_notes
    ):

        strength = onset_at(t)

        # Look around the grid point.
        nearby = max(
            onset_at(t - 0.020),
            onset_at(t),
            onset_at(t + 0.020),
            onset_at(t + 0.040),
        )

        strength = max(
            strength,
            nearby
        )

        # Stronger probability on real onsets.
        beat_number = int(
            round(
                (t - grid_offset) / beat
            )
        )

        is_downbeat = (
            beat_number % 4 == 0
        )

        # Full beats are more likely than subdivisions.
        on_full_beat = (
            abs(
                ((t - grid_offset) / beat)
                - round(
                    (t - grid_offset) / beat
                )
            ) < 0.001
        )

        probability = 0.0

        if strength >= threshold:
            probability = 0.85

        elif strength >= threshold * 0.65:
            probability = 0.55

        elif on_full_beat:
            probability = 0.24

        # Downbeats get priority.
        if is_downbeat:
            probability += 0.12

        # Difficulty density.
        probability *= density

        # Easy mode mostly uses actual strong beats.
        if difficulty_name == "EASY":
            if not on_full_beat:
                probability *= 0.25

        # Normal allows occasional subdivisions.
        elif difficulty_name == "NORMAL":
            if not on_full_beat:
                probability *= 0.55

        # Higher difficulties use subdivisions.
        if random.random() < probability:

            # Don't put notes absurdly close together.
            if (
                t - previous_time
                >= max(
                    0.045,
                    step * 0.55
                )
            ):

                lane = choose_lane(
                    previous_lane
                )

                notes.append({
                    "time": float(t),
                    "lane": lane,
                    "hit": False,
                    "missed": False,
                })

                previous_lane = lane
                previous_time = t

                # ------------------------------------------------
                # Chords.
                #
                # Chords only happen on stronger beats.
                # ------------------------------------------------

                if (
                    allow_chords
                    and strength >= threshold * 0.9
                    and random.random() < (
                        0.12
                        + density * 0.16
                    )
                ):

                    other_lanes = [
                        x for x in range(4)
                        if x != lane
                    ]

                    # Usually one extra arrow.
                    second_lane = random.choice(
                        other_lanes
                    )

                    notes.append({
                        "time": float(t),
                        "lane": second_lane,
                        "hit": False,
                        "missed": False,
                    })

                    # Very high difficulty occasionally gets
                    # a three-note chord.
                    if (
                        difficulty_name in (
                            "EXTREME",
                            "OSU PRO (MY BROTHER)"
                        )
                        and random.random() < 0.08
                    ):

                        remaining = [
                            x for x in other_lanes
                            if x != second_lane
                        ]

                        third_lane = random.choice(
                            remaining
                        )

                        notes.append({
                            "time": float(t),
                            "lane": third_lane,
                            "hit": False,
                            "missed": False,
                        })

        t += step

    # --------------------------------------------------------
    # Guarantee some notes for very quiet songs.
    # --------------------------------------------------------

    if not notes and duration > 2:

        t = beat

        while (
            t < duration
            and len(notes) < 100
        ):

            lane = (
                len(notes) % 4
            )

            notes.append({
                "time": float(t),
                "lane": lane,
                "hit": False,
                "missed": False,
            })

            t += beat

    notes.sort(
        key=lambda n: (
            n["time"],
            n["lane"]
        )
    )

    return notes, bpm


# ============================================================
# PARTICLES
# ============================================================

class Particle:
    def __init__(self, width, height):
        self.x = random.uniform(
            0,
            width
        )

        self.y = random.uniform(
            0,
            height
        )

        self.vx = random.uniform(
            -0.25,
            0.25
        )

        self.vy = random.uniform(
            -0.65,
            -0.15
        )

        self.size = random.uniform(
            1,
            3
        )

        self.life = random.uniform(
            3,
            8
        )

    def update(self):
        self.x += self.vx
        self.y += self.vy

        self.life -= 0.016

        if self.y < -10:
            self.y = 710
            self.x = random.uniform(
                0,
                1100
            )

        if self.life <= 0:
            self.y = 710
            self.x = random.uniform(
                0,
                1100
            )

            self.life = random.uniform(
                3,
                8
            )


# ============================================================
# MAIN GAME
# ============================================================

class ManiaTK:

    def __init__(self):

        self.root = tk.Tk()

        self.root.title(
            f"{APP_NAME} {GAME_VERSION}"
        )

        self.root.geometry(
            f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}"
        )

        self.root.resizable(
            False,
            False
        )

        self.root.configure(
            bg="#080808"
        )

        self.canvas = tk.Canvas(
            self.root,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            bg="#080808",
            highlightthickness=0
        )

        self.canvas.pack()

        self.keys = DEFAULT_KEYS.copy()

        self.note_speed = DEFAULT_NOTE_SPEED

        self.audio = AudioPlayer()

        self.song_file = None
        self.wav_file = None
        self.temp_dir = None

        self.notes = []

        self.bpm = 120.0

        self.screen = "menu"

        self.difficulty = "NORMAL"

        self.song_time = 0.0

        self.score = 0
        self.combo = 0
        self.max_combo = 0

        self.perfects = 0
        self.greats = 0
        self.goods = 0
        self.misses = 0
        self.empty_hits = 0

        self.accuracy_total = 0.0
        self.accuracy_count = 0

        self.last_judgement = ""
        self.last_judgement_time = 0

        self.key_glow = [
            0.0
            for _ in range(4)
        ]

        self.hit_flash = [
            0.0
            for _ in range(4)
        ]

        self.hit_particles = []

        self.paused_position = 0.0

        self.selected_difficulty_index = 1

        self.difficulty_names = list(
            DIFFICULTIES.keys()
        )

        self.menu_buttons = []

        self.particles = [
            Particle(
                WINDOW_WIDTH,
                WINDOW_HEIGHT
            )
            for _ in range(90)
        ]

        self.keys_down = set()

        self.bind_keys()

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.close
        )

        self.draw_menu()

        self.animation_loop()

    # ========================================================
    # INPUT
    # ========================================================

    def bind_keys(self):

        self.root.bind(
            "<KeyPress>",
            self.key_press
        )

        self.root.bind(
            "<KeyRelease>",
            self.key_release
        )

    def key_press(self, event):

        key = event.keysym.lower()

        if key == "escape":

            if self.screen == "game":
                self.pause_game()

            elif self.screen == "pause":
                self.resume_game()

            return

        if key in self.keys_down:
            return

        self.keys_down.add(key)

        if self.screen != "game":
            return

        if key not in self.keys:
            return

        lane = self.keys.index(
            key
        )

        self.key_glow[lane] = 1.0

        self.try_hit_lane(
            lane
        )

    def key_release(self, event):

        key = event.keysym.lower()

        self.keys_down.discard(
            key
        )

    # ========================================================
    # BUTTON
    # ========================================================

    def button(
        self,
        x1,
        y1,
        x2,
        y2,
        text,
        command,
        font=("Arial", 15, "bold")
    ):

        tag = f"button_{len(self.menu_buttons)}"

        self.canvas.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            fill="#210000",
            outline="#ff2020",
            width=2,
            tags=tag
        )

        self.canvas.create_text(
            (x1 + x2) / 2,
            (y1 + y2) / 2,
            text=text,
            fill="white",
            font=font,
            tags=tag
        )

        self.canvas.tag_bind(
            tag,
            "<Button-1>",
            lambda e: command()
        )

        self.canvas.tag_bind(
            tag,
            "<Enter>",
            lambda e: self.canvas.itemconfigure(
                tag,
                fill="#4a0000"
            )
        )

        self.canvas.tag_bind(
            tag,
            "<Leave>",
            lambda e: self.canvas.itemconfigure(
                tag,
                fill="#210000"
            )
        )

        self.menu_buttons.append(
            tag
        )

    def clear(self):

        self.canvas.delete(
            "all"
        )

        self.menu_buttons.clear()

    # ========================================================
    # BACKGROUND
    # ========================================================

    def draw_background(self):

        self.canvas.create_rectangle(
            0,
            0,
            WINDOW_WIDTH,
            WINDOW_HEIGHT,
            fill="#080808",
            outline=""
        )

        # Red glow bars.
        for i in range(8):

            y = (
                i * 100
                + math.sin(
                    time.perf_counter()
                    * 0.8
                    + i
                ) * 15
            )

            self.canvas.create_rectangle(
                0,
                y,
                WINDOW_WIDTH,
                y + 1,
                fill="#260000",
                outline=""
            )

        for p in self.particles:

            self.canvas.create_oval(
                p.x - p.size,
                p.y - p.size,
                p.x + p.size,
                p.y + p.size,
                fill="white",
                outline=""
            )

    # ========================================================
    # MENU
    # ========================================================

    def draw_menu(self):

        self.screen = "menu"

        self.clear()

        self.draw_background()

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            85,
            text="MANIATK",
            fill="#ff3030",
            font=(
                "Arial",
                54,
                "bold"
            )
        )

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            135,
            text="4K RHYTHM GAME",
            fill="white",
            font=(
                "Arial",
                16,
                "bold"
            )
        )

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            190,
            text=(
                "Automatic BPM + beat-grid chart generation"
            ),
            fill="#aaaaaa",
            font=("Arial", 12)
        )

        self.button(
            375,
            235,
            725,
            295,
            "IMPORT MUSIC",
            self.import_song
        )

        self.button(
            375,
            310,
            725,
            370,
            "DIFFICULTY",
            self.choose_difficulty
        )

        self.button(
            375,
            385,
            725,
            445,
            f"NOTE SPEED: {self.note_speed}",
            self.choose_speed
        )

        self.button(
            375,
            460,
            725,
            520,
            "KEY SETTINGS",
            self.key_settings
        )

        self.button(
            375,
            535,
            475,
            595,
            "TUTORIAL",
            self.tutorial
        )

        self.button(
            625,
            535,
            725,
            595,
            "EXIT",
            self.close
        )

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            640,
            text=(
                "D   F   J   K"
            ),
            fill="#ff4040",
            font=(
                "Arial",
                20,
                "bold"
            )
        )

    # ========================================================
    # IMPORT
    # ========================================================

    def import_song(self):

        path = filedialog.askopenfilename(
            title="Choose Music",
            filetypes=[
                (
                    "Music / Video",
                    "*.mp3 *.wav *.ogg *.m4a *.wma "
                    "*.flac *.mp4 *.avi *.mkv"
                ),
                (
                    "All files",
                    "*.*"
                )
            ]
        )

        if not path:
            return

        try:

            if self.temp_dir:

                shutil.rmtree(
                    self.temp_dir,
                    ignore_errors=True
                )

                self.temp_dir = None

            self.canvas.delete(
                "all"
            )

            self.canvas.create_text(
                WINDOW_WIDTH / 2,
                WINDOW_HEIGHT / 2 - 30,
                text="ANALYZING MUSIC...",
                fill="white",
                font=(
                    "Arial",
                    28,
                    "bold"
                )
            )

            self.canvas.create_text(
                WINDOW_WIDTH / 2,
                WINDOW_HEIGHT / 2 + 20,
                text=(
                    "Detecting BPM and building beat grid..."
                ),
                fill="#ff3030",
                font=("Arial", 14)
            )

            self.root.update()

            wav_path, temp_dir = convert_to_wav(
                path
            )

            audio, sample_rate = read_wav(
                wav_path
            )

            notes, bpm = generate_chart(
                audio,
                sample_rate,
                self.difficulty
            )

            self.song_file = path
            self.wav_file = wav_path
            self.temp_dir = temp_dir

            self.notes = notes
            self.bpm = bpm

            self.reset_stats()

            messagebox.showinfo(
                "Chart Ready",
                f"Song loaded!\n\n"
                f"Estimated BPM: {bpm:.1f}\n"
                f"Notes: {len(notes)}\n"
                f"Difficulty: {self.difficulty}\n"
                f"Note Speed: {self.note_speed}"
            )

            self.start_game()

        except Exception as e:

            messagebox.showerror(
                "Import failed",
                str(e)
            )

            self.draw_menu()

    # ========================================================
    # START
    # ========================================================

    def start_game(self):

        if not self.song_file:
            return

        if not self.notes:

            messagebox.showerror(
                "No notes",
                "The chart generator did not create any notes."
            )

            return

        self.reset_stats()

        self.screen = "game"

        self.song_time = 0.0

        self.paused_position = 0.0

        self.audio.stop()

        if not self.audio.play(
            self.wav_file
        ):
            self.screen = "menu"
            self.draw_menu()
            return

    # ========================================================
    # RESET STATS
    # ========================================================

    def reset_stats(self):

        for note in self.notes:
            note["hit"] = False
            note["missed"] = False

        self.score = 0
        self.combo = 0
        self.max_combo = 0

        self.perfects = 0
        self.greats = 0
        self.goods = 0
        self.misses = 0
        self.empty_hits = 0

        self.accuracy_total = 0.0
        self.accuracy_count = 0

        self.last_judgement = ""
        self.last_judgement_time = 0

    # ========================================================
    # HIT DETECTION
    # ========================================================

    def try_hit_lane(self, lane):

        if self.screen != "game":
            return

        current = self.audio.get_position()

        candidates = []

        for note in self.notes:

            if note["lane"] != lane:
                continue

            if note["hit"] or note["missed"]:
                continue

            difference = (
                current
                - note["time"]
            )

            absolute = abs(
                difference
            )

            if absolute <= MISS_WINDOW:

                candidates.append(
                    (
                        absolute,
                        note,
                        difference
                    )
                )

        if not candidates:

            self.empty_hits += 1

            self.last_judgement = "EMPTY"
            self.last_judgement_time = time.perf_counter()

            self.hit_flash[lane] = 0.35

            return

        candidates.sort(
            key=lambda x: x[0]
        )

        _, note, difference = candidates[0]

        absolute = abs(
            difference
        )

        note["hit"] = True

        self.hit_flash[lane] = 1.0

        if absolute <= PERFECT_WINDOW:

            judgement = "PERFECT"
            points = 300
            accuracy = 1.0

            self.perfects += 1

        elif absolute <= GREAT_WINDOW:

            judgement = "GREAT"
            points = 200
            accuracy = 0.80

            self.greats += 1

        else:

            judgement = "GOOD"
            points = 100
            accuracy = 0.50

            self.goods += 1

        self.combo += 1

        self.max_combo = max(
            self.max_combo,
            self.combo
        )

        combo_bonus = min(
            self.combo * 2,
            500
        )

        self.score += (
            points
            + combo_bonus
        )

        self.accuracy_total += accuracy
        self.accuracy_count += 1

        self.last_judgement = judgement
        self.last_judgement_time = time.perf_counter()

        # Create hit particles.
        x = self.lane_center(
            lane
        )

        for _ in range(12):

            self.hit_particles.append({
                "x": x,
                "y": JUDGEMENT_Y,
                "vx": random.uniform(
                    -2.5,
                    2.5
                ),
                "vy": random.uniform(
                    -3.5,
                    -0.5
                ),
                "life": 1.0,
            })

    # ========================================================
    # MISS CHECK
    # ========================================================

    def update_misses(self):

        current = self.audio.get_position()

        for note in self.notes:

            if note["hit"] or note["missed"]:
                continue

            if (
                current
                - note["time"]
                > MISS_WINDOW
            ):

                note["missed"] = True

                self.misses += 1
                self.combo = 0

                self.last_judgement = "MISS"
                self.last_judgement_time = time.perf_counter()

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

        self.screen = "pause"

        self.draw_pause()

    def draw_pause(self):

        self.clear()

        self.draw_background()

        self.canvas.create_rectangle(
            270,
            150,
            830,
            550,
            fill="#100000",
            outline="#ff2020",
            width=3
        )

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            215,
            text="PAUSED",
            fill="#ff3030",
            font=(
                "Arial",
                42,
                "bold"
            )
        )

        self.button(
            390,
            285,
            710,
            345,
            "RESUME",
            self.resume_game
        )

        self.button(
            390,
            360,
            710,
            420,
            "QUIT BEATMAP",
            self.quit_to_menu
        )

        self.button(
            390,
            435,
            710,
            495,
            "EXIT GAME",
            self.close
        )

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            525,
            text="Press ESC to resume",
            fill="#aaaaaa",
            font=("Arial", 12)
        )

    def resume_game(self):

        if self.screen != "pause":
            return

        self.screen = "game"

        self.audio.resume()

    def quit_to_menu(self):

        self.audio.stop()

        self.screen = "menu"

        self.draw_menu()

    # ========================================================
    # GAME DRAWING
    # ========================================================

    def lane_center(self, lane):

        total_width = (
            LANES * LANE_WIDTH
            + (LANES - 1) * LANE_GAP
        )

        start = (
            WINDOW_WIDTH
            - total_width
        ) / 2

        return (
            start
            + lane * (
                LANE_WIDTH
                + LANE_GAP
            )
            + LANE_WIDTH / 2
        )

    def draw_arrow(
        self,
        cx,
        cy,
        size,
        direction,
        fill,
        outline=None,
        width=2
    ):

        if outline is None:
            outline = fill

        # Arrow polygon.
        #
        # This is deliberately drawn instead of using emoji,
        # because emoji appearance differs between Windows
        # systems.

        half = size * 0.45
        shaft = size * 0.17

        if direction == 0:
            # LEFT
            points = [
                cx - half,
                cy,
                cx - half * 0.20,
                cy - half,
                cx - half * 0.20,
                cy - shaft,
                cx + half,
                cy - shaft,
                cx + half,
                cy + shaft,
                cx - half * 0.20,
                cy + shaft,
                cx - half * 0.20,
                cy + half,
            ]

        elif direction == 1:
            # DOWN
            points = [
                cx,
                cy + half,
                cx - half,
                cy + half * 0.20,
                cx - shaft,
                cy + half * 0.20,
                cx - shaft,
                cy - half,
                cx + shaft,
                cy - half,
                cx + shaft,
                cy + half * 0.20,
                cx + half,
                cy + half * 0.20,
            ]

        elif direction == 2:
            # UP
            points = [
                cx,
                cy - half,
                cx - half,
                cy - half * 0.20,
                cx - shaft,
                cy - half * 0.20,
                cx - shaft,
                cy + half,
                cx + shaft,
                cy + half,
                cx + shaft,
                cy - half * 0.20,
                cx + half,
                cy - half * 0.20,
            ]

        else:
            # RIGHT
            points = [
                cx + half,
                cy,
                cx + half * 0.20,
                cy - half,
                cx + half * 0.20,
                cy - shaft,
                cx - half,
                cy - shaft,
                cx - half,
                cy + shaft,
                cx + half * 0.20,
                cy + shaft,
                cx + half * 0.20,
                cy + half,
            ]

        self.canvas.create_polygon(
            points,
            fill=fill,
            outline=outline,
            width=width
        )

    def draw_lane_receptors(self):

        for lane in range(4):

            cx = self.lane_center(
                lane
            )

            # Lane background.
            left = cx - LANE_WIDTH / 2
            right = cx + LANE_WIDTH / 2

            self.canvas.create_rectangle(
                left,
                95,
                right,
                650,
                fill="#0e0e0e",
                outline="#2a2a2a",
                width=2
            )

            # Glow when key pressed.
            glow = self.key_glow[lane]

            if glow > 0:

                self.canvas.create_rectangle(
                    left + 3,
                    98,
                    right - 3,
                    648,
                    fill="#180000",
                    outline=""
                )

                self.canvas.create_rectangle(
                    left + 3,
                    98,
                    right - 3,
                    648,
                    outline="#ff3030",
                    width=int(
                        2 + glow * 5
                    )
                )

            # Receptor glow.
            flash = self.hit_flash[lane]

            if flash > 0:

                self.draw_arrow(
                    cx,
                    JUDGEMENT_Y,
                    72 + flash * 10,
                    lane,
                    "#ff3030",
                    "#ffffff",
                    3
                )

            else:

                self.draw_arrow(
                    cx,
                    JUDGEMENT_Y,
                    68,
                    lane,
                    "#2b0000",
                    "#ff3030",
                    3
                )

            # Key text.
            self.canvas.create_text(
                cx,
                665,
                text=self.keys[lane].upper(),
                fill="white",
                font=(
                    "Arial",
                    16,
                    "bold"
                )
            )

    def draw_notes(self):

        current = self.song_time

        # Notes should take this many seconds to travel
        # from the top to the judgement line.
        travel_time = (
            500.0
            / self.note_speed
        )

        for note in self.notes:

            if note["hit"]:
                continue

            if note["missed"]:
                continue

            delta = (
                note["time"]
                - current
            )

            # Note appears before judgement.
            if delta > travel_time:
                continue

            if delta < -MISS_WINDOW:
                continue

            progress = (
                1.0
                - delta / travel_time
            )

            y = (
                110
                + progress
                * (
                    JUDGEMENT_Y
                    - 110
                )
            )

            cx = self.lane_center(
                note["lane"]
            )

            # Fade very old notes.
            if delta < 0:
                fill = "#ff5555"
            else:
                fill = "#ff2020"

            # Glow outline.
            self.draw_arrow(
                cx,
                y,
                60,
                note["lane"],
                fill,
                "#ffffff",
                2
            )

            # Inner arrow.
            self.draw_arrow(
                cx,
                y,
                42,
                note["lane"],
                "#ffffff",
                "#ffffff",
                1
            )

    # ========================================================
    # GAME SCREEN
    # ========================================================

    def draw_game(self):

        self.clear()

        self.draw_background()

        self.draw_lane_receptors()

        self.draw_notes()

        # Top information.
        self.canvas.create_text(
            35,
            25,
            anchor="w",
            text=(
                f"{self.difficulty}"
            ),
            fill="#ff3030",
            font=(
                "Arial",
                17,
                "bold"
            )
        )

        self.canvas.create_text(
            WINDOW_WIDTH - 35,
            25,
            anchor="e",
            text=(
                f"BPM {self.bpm:.1f}   "
                f"SPEED {self.note_speed}"
            ),
            fill="white",
            font=(
                "Arial",
                13,
                "bold"
            )
        )

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            30,
            text=str(
                self.score
            ),
            fill="white",
            font=(
                "Arial",
                18,
                "bold"
            )
        )

        # Combo.
        if self.combo > 0:

            self.canvas.create_text(
                WINDOW_WIDTH / 2,
                68,
                text=f"{self.combo} COMBO",
                fill="#ff3030",
                font=(
                    "Arial",
                    22,
                    "bold"
                )
            )

        # Judgement.
        if (
            time.perf_counter()
            - self.last_judgement_time
            < 0.65
        ):

            judgement = (
                self.last_judgement
            )

            if judgement == "PERFECT":
                text = "PERFECT!"
            elif judgement == "GREAT":
                text = "GREAT!"
            elif judgement == "GOOD":
                text = "GOOD"
            elif judgement == "MISS":
                text = "MISS"
            else:
                text = "NO NOTE"

            self.canvas.create_text(
                WINDOW_WIDTH / 2,
                120,
                text=text,
                fill="white",
                font=(
                    "Arial",
                    24,
                    "bold"
                )
            )

        # Bottom accuracy.
        accuracy = self.get_accuracy()

        self.canvas.create_text(
            35,
            675,
            anchor="w",
            text=f"ACC {accuracy:.2f}%",
            fill="#aaaaaa",
            font=(
                "Arial",
                11
            )
        )

        self.canvas.create_text(
            WINDOW_WIDTH - 35,
            675,
            anchor="e",
            text="ESC = PAUSE",
            fill="#aaaaaa",
            font=(
                "Arial",
                11
            )
        )

    # ========================================================
    # HIT PARTICLES
    # ========================================================

    def update_hit_particles(self):

        alive = []

        for p in self.hit_particles:

            p["x"] += p["vx"]
            p["y"] += p["vy"]

            p["vy"] += 0.08

            p["life"] -= 0.035

            if p["life"] > 0:

                alive.append(p)

                size = 2 + p["life"] * 3

                self.canvas.create_oval(
                    p["x"] - size,
                    p["y"] - size,
                    p["x"] + size,
                    p["y"] + size,
                    fill="white",
                    outline=""
                )

        self.hit_particles = alive

    # ========================================================
    # RESULTS
    # ========================================================

    def get_accuracy(self):

        if self.accuracy_count <= 0:
            return 100.0

        return (
            self.accuracy_total
            / self.accuracy_count
            * 100.0
        )

    def show_results(self):

        self.audio.stop()

        self.screen = "results"

        self.clear()

        self.draw_background()

        accuracy = self.get_accuracy()

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            80,
            text="RESULTS",
            fill="#ff3030",
            font=(
                "Arial",
                45,
                "bold"
            )
        )

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            150,
            text=f"{accuracy:.2f}%",
            fill="white",
            font=(
                "Arial",
                40,
                "bold"
            )
        )

        lines = [
            f"Score: {self.score}",
            f"Max Combo: {self.max_combo}",
            "",
            f"Perfect: {self.perfects}",
            f"Great: {self.greats}",
            f"Good: {self.goods}",
            f"Miss: {self.misses}",
            f"Empty Presses: {self.empty_hits}",
        ]

        y = 230

        for line in lines:

            self.canvas.create_text(
                WINDOW_WIDTH / 2,
                y,
                text=line,
                fill="white",
                font=(
                    "Arial",
                    16,
                    "bold"
                )
            )

            y += 30

        self.button(
            390,
            540,
            710,
            600,
            "BACK TO MENU",
            self.draw_menu
        )

    # ========================================================
    # DIFFICULTY
    # ========================================================

    def choose_difficulty(self):

        self.screen = "difficulty"

        self.clear()

        self.draw_background()

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            70,
            text="SELECT DIFFICULTY",
            fill="#ff3030",
            font=(
                "Arial",
                32,
                "bold"
            )
        )

        y = 125

        for i, name in enumerate(
            self.difficulty_names
        ):

            selected = (
                i
                == self.selected_difficulty_index
            )

            fill = (
                "#520000"
                if selected
                else "#210000"
            )

            tag = f"diff_{i}"

            self.canvas.create_rectangle(
                260,
                y,
                840,
                y + 65,
                fill=fill,
                outline="#ff2020",
                width=2,
                tags=tag
            )

            self.canvas.create_text(
                285,
                y + 20,
                anchor="w",
                text=name,
                fill="white",
                font=(
                    "Arial",
                    15,
                    "bold"
                ),
                tags=tag
            )

            self.canvas.create_text(
                285,
                y + 44,
                anchor="w",
                text=DIFFICULTIES[
                    name
                ]["description"],
                fill="#aaaaaa",
                font=(
                    "Arial",
                    10
                ),
                tags=tag
            )

            self.canvas.tag_bind(
                tag,
                "<Button-1>",
                lambda e, idx=i:
                self.select_difficulty(idx)
            )

            y += 72

        self.button(
            430,
            600,
            670,
            650,
            "BACK",
            self.draw_menu
        )

    def select_difficulty(self, index):

        self.selected_difficulty_index = index

        self.difficulty = (
            self.difficulty_names[index]
        )

        self.draw_menu()

    # ========================================================
    # NOTE SPEED
    # ========================================================

    def choose_speed(self):

        self.screen = "speed"

        self.clear()

        self.draw_background()

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            80,
            text="NOTE SPEED",
            fill="#ff3030",
            font=(
                "Arial",
                35,
                "bold"
            )
        )

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            150,
            text=str(
                self.note_speed
            ),
            fill="white",
            font=(
                "Arial",
                35,
                "bold"
            )
        )

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            195,
            text="Higher = faster arrows",
            fill="#aaaaaa",
            font=(
                "Arial",
                13
            )
        )

        # Slider.
        x1 = 280
        x2 = 820
        y = 285

        self.canvas.create_line(
            x1,
            y,
            x2,
            y,
            fill="#ff2020",
            width=5
        )

        ratio = (
            self.note_speed
            - MIN_NOTE_SPEED
        ) / (
            MAX_NOTE_SPEED
            - MIN_NOTE_SPEED
        )

        knob_x = (
            x1
            + ratio
            * (x2 - x1)
        )

        self.canvas.create_oval(
            knob_x - 14,
            y - 14,
            knob_x + 14,
            y + 14,
            fill="#ff3030",
            outline="white",
            width=2
        )

        # Presets.
        speeds = [
            ("SLOW", 250),
            ("NORMAL", 420),
            ("FAST", 600),
            ("INSANE", 800),
        ]

        y2 = 360

        for label, value in speeds:

            self.button(
                350,
                y2,
                750,
                y2 + 55,
                f"{label}  ({value})",
                lambda v=value:
                self.set_speed(v)
            )

            y2 += 65

        self.button(
            430,
            625,
            670,
            675,
            "BACK",
            self.draw_menu
        )

    def set_speed(self, value):

        self.note_speed = max(
            MIN_NOTE_SPEED,
            min(
                MAX_NOTE_SPEED,
                value
            )
        )

        self.draw_menu()

    # ========================================================
    # KEY SETTINGS
    # ========================================================

    def key_settings(self):

        self.screen = "keys"

        self.clear()

        self.draw_background()

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            70,
            text="KEY SETTINGS",
            fill="#ff3030",
            font=(
                "Arial",
                32,
                "bold"
            )
        )

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            120,
            text="Click a lane, then press a key",
            fill="#aaaaaa",
            font=("Arial", 13)
        )

        y = 190

        for lane in range(4):

            self.canvas.create_rectangle(
                300,
                y,
                800,
                y + 70,
                fill="#210000",
                outline="#ff2020",
                width=2
            )

            self.canvas.create_text(
                370,
                y + 35,
                text=(
                    ["LEFT", "DOWN", "UP", "RIGHT"][lane]
                ),
                fill="white",
                font=(
                    "Arial",
                    14,
                    "bold"
                )
            )

            self.canvas.create_text(
                650,
                y + 35,
                text=self.keys[lane].upper(),
                fill="#ff3030",
                font=(
                    "Arial",
                    20,
                    "bold"
                )
            )

            self.canvas.tag_bind(
                f"none_{lane}",
                "<Button-1>",
                lambda e: None
            )

            y += 80

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            535,
            text=(
                "Default: D F J K"
            ),
            fill="#aaaaaa",
            font=(
                "Arial",
                12
            )
        )

        self.button(
            350,
            565,
            750,
            620,
            "RESET TO D F J K",
            self.reset_keys
        )

        self.button(
            430,
            635,
            670,
            680,
            "BACK",
            self.draw_menu
        )

        # Bind clickable lane areas directly.
        y = 190

        for lane in range(4):

            tag = f"keylane_{lane}"

            self.canvas.addtag_overlapping(
                tag,
                300,
                y,
                800,
                y + 70
            )

            # Easier: bind by coordinates using a transparent
            # rectangle.
            self.canvas.create_rectangle(
                300,
                y,
                800,
                y + 70,
                outline="",
                fill="",
                tags=tag
            )

            self.canvas.tag_bind(
                tag,
                "<Button-1>",
                lambda e, l=lane:
                self.rebind_key(l)
            )

            y += 80

    def rebind_key(self, lane):

        messagebox.showinfo(
            "Rebind key",
            (
                f"Press the new key for lane "
                f"{lane + 1}.\n\n"
                "ESC cannot be used."
            )
        )

        self.pending_lane = lane

        self.root.bind(
            "<KeyPress>",
            self.receive_new_key
        )

    def receive_new_key(self, event):

        key = event.keysym.lower()

        if key == "escape":
            return

        if key in self.keys:
            messagebox.showwarning(
                "Already used",
                "That key is already assigned."
            )
            return

        self.keys[
            self.pending_lane
        ] = key

        self.root.bind(
            "<KeyPress>",
            self.key_press
        )

        self.key_settings()

    def reset_keys(self):

        self.keys = DEFAULT_KEYS.copy()

        self.key_settings()

    # ========================================================
    # TUTORIAL
    # ========================================================

    def tutorial(self):

        self.screen = "tutorial"

        self.clear()

        self.draw_background()

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            65,
            text="HOW TO PLAY",
            fill="#ff3030",
            font=(
                "Arial",
                34,
                "bold"
            )
        )

        tutorial_lines = [
            "ManiaTK is a 4-key rhythm game.",
            "",
            "Press the matching key when an arrow",
            "reaches the glowing receptor.",
            "",
            "D = LEFT     F = DOWN",
            "J = UP       K = RIGHT",
            "",
            "PERFECT = ±25 ms",
            "GREAT   = ±60 ms",
            "GOOD    = ±100 ms",
            "MISS    = over 150 ms",
            "",
            "Pressing a key when no note is nearby",
            "shows NO NOTE and does not add score.",
            "",
            "ESC = PAUSE",
            "",
            "Note Speed controls how quickly arrows",
            "travel toward the receptors.",
            "",
            "Higher difficulties add beat subdivisions",
            "and more chords.",
        ]

        y = 120

        for line in tutorial_lines:

            self.canvas.create_text(
                WINDOW_WIDTH / 2,
                y,
                text=line,
                fill=(
                    "white"
                    if line
                    else "#333333"
                ),
                font=(
                    "Arial",
                    13,
                    "bold"
                    if (
                        "PERFECT" in line
                        or "GREAT" in line
                        or "GOOD" in line
                        or "MISS" in line
                    )
                    else "normal"
                )
            )

            y += 21

        self.button(
            430,
            630,
            670,
            680,
            "BACK",
            self.draw_menu
        )

    # ========================================================
    # ANIMATION LOOP
    # ========================================================

    def animation_loop(self):

        # Particles.
        for p in self.particles:
            p.update()

        # Glow decay.
        for i in range(4):

            self.key_glow[i] *= 0.82
            self.hit_flash[i] *= 0.88

            if self.key_glow[i] < 0.01:
                self.key_glow[i] = 0

            if self.hit_flash[i] < 0.01:
                self.hit_flash[i] = 0

        # Gameplay.
        if self.screen == "game":

            self.song_time = (
                self.audio.get_position()
            )

            self.update_misses()

            # Check if audio finished.
            if (
                self.audio.finished()
                or self.song_time >= self.get_song_duration()
            ):

                self.show_results()

            else:

                self.draw_game()

                self.update_hit_particles()

        elif self.screen == "pause":
            pass

        elif self.screen == "results":
            pass

        # Keep animation running.
        self.root.after(
            16,
            self.animation_loop
        )

    # ========================================================
    # SONG LENGTH
    # ========================================================

    def get_song_duration(self):

        if not self.wav_file:
            return 0.0

        try:

            with wave.open(
                self.wav_file,
                "rb"
            ) as wf:

                frames = wf.getnframes()
                rate = wf.getframerate()

                if rate <= 0:
                    return 0.0

                return (
                    frames / rate
                )

        except Exception:
            return 0.0

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self):

        try:
            self.audio.stop()
        except Exception:
            pass

        if self.temp_dir:

            try:
                shutil.rmtree(
                    self.temp_dir,
                    ignore_errors=True
                )
            except Exception:
                pass

        try:
            self.root.destroy()
        except Exception:
            pass


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    app = ManiaTK()

    app.root.mainloop()
