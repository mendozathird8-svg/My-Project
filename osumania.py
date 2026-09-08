import os
import sys
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
# Python 3.14 compatible
# 4K osu!mania-inspired rhythm game
#
# NO PYGAME
#
# Features:
#   MP3 / MP4 / WAV / OGG / M4A / WMA importing
#   Automatic beatmap generation
#   6 difficulties
#   D/F/J/K controls
#   Key rebinding
#   Duplicate-key prevention
#   Perfect / Great / Good / Miss
#   Score / Combo / Accuracy
#   Pause menu
#   Results screen
#   Animated red background
#   White particles
#   Built-in tutorial
#   GitHub update checker
# ============================================================


# ============================================================
# SETTINGS
# ============================================================

APP_NAME = "ManiaTK"

GAME_VERSION = "1.0.0"

VERSION_URL = (
    "https://raw.githubusercontent.com/"
    "mendozathird8-svg/My-Project/main/version.txt"
)

WINDOW_WIDTH = 720
WINDOW_HEIGHT = 820

LANES = 4

DEFAULT_KEYS = ["d", "f", "j", "k"]

LANE_WIDTH = 130
LANE_GAP = 4

PLAYFIELD_WIDTH = (
    LANE_WIDTH * LANES
    + LANE_GAP * (LANES - 1)
)

PLAYFIELD_X = (
    WINDOW_WIDTH - PLAYFIELD_WIDTH
) // 2

RECEPTOR_Y = 700

NOTE_HEIGHT = 25

NOTE_SPEED = 520.0

PERFECT_WINDOW = 0.025
GREAT_WINDOW = 0.060
GOOD_WINDOW = 0.100
MISS_WINDOW = 0.150

NOTE_COLORS = [
    "#ff4f81",
    "#4f9cff",
    "#4fff88",
    "#ffd84f",
]

BACKGROUND = "#b40000"
BACKGROUND_DARK = "#850000"

WHITE = "#ffffff"

# GitHub files
SCRIPT_URL = (
    "https://raw.githubusercontent.com/"
    "mendozathird8-svg/My-Project/main/osumania.py"
)

ICON_URL = (
    "https://raw.githubusercontent.com/"
    "mendozathird8-svg/My-Project/main/icon..ico"
)


# ============================================================
# DIFFICULTIES
# ============================================================

DIFFICULTIES = {
    "EASY": {
        "threshold": 72,
        "min_spacing": 0.240,
        "chords": False,
        "jumps": False,
        "description": "Fewer notes • slower patterns",
    },

    "NORMAL": {
        "threshold": 63,
        "min_spacing": 0.155,
        "chords": True,
        "jumps": False,
        "description": "Balanced chart • occasional chords",
    },

    "HARD": {
        "threshold": 54,
        "min_spacing": 0.115,
        "chords": True,
        "jumps": True,
        "description": "Fast patterns • more chords",
    },

    "INSANE": {
        "threshold": 45,
        "min_spacing": 0.082,
        "chords": True,
        "jumps": True,
        "description": "Very dense • fast lane changes",
    },

    "EXTREME": {
        "threshold": 38,
        "min_spacing": 0.060,
        "chords": True,
        "jumps": True,
        "description": "Extremely dense • rapid patterns • lots of chords",
    },

    "OSU PRO (MY BROTHER)": {
        "threshold": 30,
        "min_spacing": 0.042,
        "chords": True,
        "jumps": True,
        "description": "Brother mode • brutal density • very fast patterns",
    },
}


# ============================================================
# AUDIO PLAYER
# ============================================================

class AudioPlayer:
    """
    Simple audio player.

    Preferred:
        ffplay

    Fallback:
        Windows PowerShell WPF MediaPlayer
    """

    def __init__(self):
        self.process = None
        self.ps_process = None

        self.duration = 0.0

        self.start_time = 0.0
        self.pause_time = 0.0

        self.playing = False
        self.paused = False

        self.current_position = 0.0

        self.file_path = None

    def _find_program(self, name):
        return shutil.which(name)

    def get_duration(self, path):
        """
        Gets WAV duration directly.

        For other formats, tries ffprobe.
        """

        try:
            if path.lower().endswith(".wav"):
                with wave.open(path, "rb") as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()

                    if rate:
                        return frames / rate
        except Exception:
            pass

        ffprobe = self._find_program("ffprobe")

        if ffprobe:
            try:
                result = subprocess.run(
                    [
                        ffprobe,
                        "-v",
                        "error",
                        "-show_entries",
                        "format=duration",
                        "-of",
                        "default=noprint_wrappers=1:nokey=1",
                        path,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                value = result.stdout.strip()

                if value:
                    return float(value)

            except Exception:
                pass

        return 0.0

    def play(self, path, start=0.0):
        self.stop()

        self.file_path = path

        self.duration = self.get_duration(path)

        self.start_time = time.perf_counter() - start
        self.pause_time = start

        self.current_position = start

        ffplay = self._find_program("ffplay")

        if ffplay:
            try:
                self.process = subprocess.Popen(
                    [
                        ffplay,
                        "-nodisp",
                        "-autoexit",
                        "-loglevel",
                        "quiet",
                        "-ss",
                        str(start),
                        path,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

                self.playing = True
                self.paused = False
                return True

            except Exception:
                self.process = None

        # PowerShell fallback
        try:
            safe_path = path.replace("'", "''")

            ps_code = f"""
Add-Type -AssemblyName presentationCore
$player = New-Object System.Windows.Media.MediaPlayer
$player.Open([Uri]::new('{safe_path}'))
Start-Sleep -Milliseconds 700
$player.Position = [TimeSpan]::FromSeconds({start})
$player.Play()

while ($true) {{
    Start-Sleep -Milliseconds 100
}}
"""

            self.ps_process = subprocess.Popen(
                [
                    "powershell",
                    "-NoProfile",
                    "-WindowStyle",
                    "Hidden",
                    "-Command",
                    ps_code,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            self.playing = True
            self.paused = False

            return True

        except Exception:
            self.ps_process = None

        return False

    def pause(self):
        if not self.playing or self.paused:
            return

        self.current_position = self.position()

        self.paused = True

        self._terminate_audio()

    def resume(self):
        if not self.playing or not self.paused:
            return

        position = self.current_position

        self.play(
            self.file_path,
            position,
        )

    def stop(self):
        self._terminate_audio()

        self.playing = False
        self.paused = False

        self.current_position = 0.0

    def _terminate_audio(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=0.5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass

            self.process = None

        if self.ps_process:
            try:
                self.ps_process.terminate()
                self.ps_process.wait(timeout=0.5)
            except Exception:
                try:
                    self.ps_process.kill()
                except Exception:
                    pass

            self.ps_process = None

    def position(self):
        if not self.playing:
            return self.current_position

        if self.paused:
            return self.current_position

        self.current_position = (
            time.perf_counter() - self.start_time
        )

        return self.current_position

    def is_finished(self):
        if self.duration <= 0:
            return False

        return self.position() >= self.duration

    def close(self):
        self.stop()


# ============================================================
# AUDIO CONVERSION
# ============================================================

def find_program(name):
    return shutil.which(name)


def convert_to_wav(source):
    """
    Converts unsupported audio/video into WAV.

    Requires ffmpeg.
    """

    if source.lower().endswith(".wav"):
        return source, False

    ffmpeg = find_program("ffmpeg")

    if not ffmpeg:
        raise RuntimeError(
            "FFmpeg was not found.\n\n"
            "Install FFmpeg and make sure ffmpeg.exe "
            "is available in PATH."
        )

    temp_dir = tempfile.mkdtemp(
        prefix="mani atk_audio_".replace(" ", "")
    )

    wav_path = os.path.join(
        temp_dir,
        "audio.wav",
    )

    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            source,
            "-vn",
            "-ac",
            "1",
            "-ar",
            "44100",
            "-sample_fmt",
            "s16",
            wav_path,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    if result.returncode != 0:
        shutil.rmtree(
            temp_dir,
            ignore_errors=True,
        )

        raise RuntimeError(
            "FFmpeg could not convert the selected file."
        )

    return wav_path, True


# ============================================================
# AUDIO ANALYSIS
# ============================================================

def analyze_audio(path):
    """
    Reads a WAV file and creates an energy envelope.

    This is used for automatic beatmap generation.
    """

    with wave.open(path, "rb") as wf:
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        frames = wf.getnframes()

        raw = wf.readframes(frames)

    if sample_width == 1:
        data = np.frombuffer(
            raw,
            dtype=np.uint8,
        ).astype(np.float32)

        data -= 128.0

    elif sample_width == 2:
        data = np.frombuffer(
            raw,
            dtype=np.int16,
        ).astype(np.float32)

    elif sample_width == 4:
        data = np.frombuffer(
            raw,
            dtype=np.int32,
        ).astype(np.float32)

    else:
        raise RuntimeError(
            "Unsupported WAV sample format."
        )

    if channels > 1:
        data = data.reshape(
            -1,
            channels,
        ).mean(axis=1)

    if len(data) == 0:
        return np.array([]), sample_rate

    # Normalize
    peak = np.max(np.abs(data))

    if peak > 0:
        data = data / peak

    # Window size around 35 ms
    window = max(
        256,
        int(sample_rate * 0.035),
    )

    hop = max(
        128,
        int(sample_rate * 0.015),
    )

    count = max(
        0,
        (len(data) - window) // hop,
    )

    if count <= 0:
        return np.array([]), sample_rate

    energies = np.empty(
        count,
        dtype=np.float32,
    )

    for i in range(count):
        start = i * hop
        chunk = data[
            start:start + window
        ]

        energies[i] = np.sqrt(
            np.mean(chunk * chunk)
        )

    # Smooth energy
    kernel_size = 5

    if len(energies) >= kernel_size:
        kernel = np.ones(
            kernel_size,
            dtype=np.float32,
        ) / kernel_size

        smooth = np.convolve(
            energies,
            kernel,
            mode="same",
        )
    else:
        smooth = energies

    return smooth, sample_rate


# ============================================================
# BEATMAP GENERATION
# ============================================================

def generate_beatmap(
    wav_path,
    difficulty_name,
):
    """
    Creates an automatic 4K beatmap.

    Returns a list of dictionaries:

        {
            "time": seconds,
            "lane": 0-3,
            "hit": False,
            "judgement": None
        }
    """

    difficulty = DIFFICULTIES[
        difficulty_name
    ]

    energies, sample_rate = analyze_audio(
        wav_path
    )

    if len(energies) == 0:
        return []

    # --------------------------------------------------------
    # Normalize
    # --------------------------------------------------------

    low = float(np.percentile(
        energies,
        15,
    ))

    high = float(np.percentile(
        energies,
        98,
    ))

    if high <= low:
        normalized = np.zeros_like(
            energies
        )
    else:
        normalized = (
            energies - low
        ) / (high - low)

    normalized = np.clip(
        normalized,
        0.0,
        1.0,
    )

    # --------------------------------------------------------
    # Find peaks
    # --------------------------------------------------------

    threshold = (
        difficulty["threshold"]
        / 100.0
    )

    min_spacing = difficulty[
        "min_spacing"
    ]

    # Estimate timing for each energy frame
    hop = max(
        128,
        int(sample_rate * 0.015),
    )

    frame_seconds = (
        hop / sample_rate
    )

    candidates = []

    radius = 2

    for i in range(
        radius,
        len(normalized) - radius,
    ):
        value = normalized[i]

        if value < threshold:
            continue

        local = normalized[
            i - radius:i + radius + 1
        ]

        if value >= np.max(local):
            candidates.append(
                (
                    i * frame_seconds,
                    float(value),
                )
            )

    # --------------------------------------------------------
    # Select events while respecting spacing
    # --------------------------------------------------------

    notes = []

    last_time = -999.0

    for event_time, strength in candidates:

        if event_time - last_time < min_spacing:
            continue

        # Ignore the first tiny moment
        if event_time < 0.10:
            continue

        notes.append(
            {
                "time": event_time,
                "lane": random.randrange(
                    LANES
                ),
                "hit": False,
                "judgement": None,
            }
        )

        last_time = event_time

    # --------------------------------------------------------
    # Add chords
    # --------------------------------------------------------

    if difficulty["chords"]:

        chord_probability = {
            "NORMAL": 0.12,
            "HARD": 0.20,
            "INSANE": 0.30,
            "EXTREME": 0.40,
            "OSU PRO (MY BROTHER)": 0.50,
        }.get(
            difficulty_name,
            0.0,
        )

        original_notes = list(notes)

        for note in original_notes:

            if random.random() > chord_probability:
                continue

            # Don't create too many chords
            if random.random() > 0.75:
                continue

            used_lane = note["lane"]

            possible = [
                x for x in range(LANES)
                if x != used_lane
            ]

            if not possible:
                continue

            second_lane = random.choice(
                possible
            )

            notes.append(
                {
                    "time": note["time"],
                    "lane": second_lane,
                    "hit": False,
                    "judgement": None,
                }
            )

        # Prevent absurd same-time duplicates
        unique = {}

        for note in notes:
            key = (
                round(note["time"], 4),
                note["lane"],
            )

            unique[key] = note

        notes = list(
            unique.values()
        )

    # --------------------------------------------------------
    # Add jump patterns
    # --------------------------------------------------------

    if difficulty["jumps"]:

        extra = []

        jump_probability = {
            "HARD": 0.10,
            "INSANE": 0.18,
            "EXTREME": 0.25,
            "OSU PRO (MY BROTHER)": 0.32,
        }.get(
            difficulty_name,
            0.0,
        )

        for note in notes:

            if random.random() > jump_probability:
                continue

            if random.random() > 0.45:
                continue

            new_time = (
                note["time"]
                + min_spacing * 1.05
            )

            lane = random.choice(
                [
                    x for x in range(LANES)
                    if x != note["lane"]
                ]
            )

            extra.append(
                {
                    "time": new_time,
                    "lane": lane,
                    "hit": False,
                    "judgement": None,
                }
            )

        notes.extend(extra)

    # --------------------------------------------------------
    # Sort
    # --------------------------------------------------------

    notes.sort(
        key=lambda n: (
            n["time"],
            n["lane"],
        )
    )

    # --------------------------------------------------------
    # Remove notes too close together in same lane
    # --------------------------------------------------------

    final = []

    last_by_lane = [
        -999.0
        for _ in range(LANES)
    ]

    for note in notes:

        lane = note["lane"]
        t = note["time"]

        if (
            t - last_by_lane[lane]
            < min_spacing * 0.72
        ):
            continue

        final.append(note)
        last_by_lane[lane] = t

    return final


# ============================================================
# PARTICLES
# ============================================================

class Particle:
    def __init__(self):
        self.reset(
            random_y=True
        )

    def reset(self, random_y=False):
        self.x = random.uniform(
            0,
            WINDOW_WIDTH,
        )

        if random_y:
            self.y = random.uniform(
                0,
                WINDOW_HEIGHT,
            )
        else:
            self.y = WINDOW_HEIGHT + random.uniform(
                5,
                50,
            )

        self.size = random.uniform(
            1.5,
            4.5,
        )

        self.speed = random.uniform(
            12,
            42,
        )

        self.drift = random.uniform(
            -9,
            9,
        )

        self.alpha = random.uniform(
            0.35,
            0.95,
        )

    def update(self, dt):
        self.y -= self.speed * dt
        self.x += self.drift * dt

        if self.y < -10:
            self.reset()

        if self.x < -20:
            self.x = WINDOW_WIDTH + 20

        if self.x > WINDOW_WIDTH + 20:
            self.x = -20


# ============================================================
# MAIN GAME
# ============================================================

class ManiaTK:
    def __init__(self):

        self.root = tk.Tk()

        self.root.title(
            f"{APP_NAME} v{GAME_VERSION}"
        )

        self.root.geometry(
            f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}"
        )

        self.root.resizable(
            False,
            False,
        )

        self.root.configure(
            bg=BACKGROUND
        )

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.exit_game,
        )

        self.canvas = tk.Canvas(
            self.root,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            bg=BACKGROUND,
            highlightthickness=0,
        )

        self.canvas.pack()

        # ----------------------------------------------------
        # State
        # ----------------------------------------------------

        self.screen = "menu"

        self.running = True

        self.song_path = None
        self.song_display_name = None

        self.converted_audio = None
        self.converted_temp_dir = None

        self.difficulty = "NORMAL"

        self.notes = []

        self.score = 0
        self.combo = 0
        self.max_combo = 0

        self.perfects = 0
        self.greats = 0
        self.goods = 0
        self.misses = 0

        self.judgement_text = ""
        self.judgement_until = 0

        self.key_bindings = DEFAULT_KEYS.copy()

        self.rebinding_lane = None

        self.last_frame = time.perf_counter()

        self.menu_particle_count = 70

        self.particles = [
            Particle()
            for _ in range(
                self.menu_particle_count
            )
        ]

        self.audio = AudioPlayer()

        self.last_empty_judgement = 0

        self.tutorial_scroll = 0

        self.bind_keys()

        self.build_menu()

        self.root.after(
            16,
            self.animation_loop,
        )

        self.root.after(
            1500,
            self.check_for_updates,
        )

    # ========================================================
    # KEYBOARD
    # ========================================================

    def bind_keys(self):

        self.root.bind(
            "<KeyPress>",
            self.on_key_press,
        )

    def on_key_press(self, event):

        key = event.keysym.lower()

        # Rebinding screen
        if self.screen == "keybinds":

            if self.rebinding_lane is not None:

                if key == "escape":
                    self.rebinding_lane = None
                    self.build_keybinds()
                    return

                # ESC is reserved for pause
                if key == "escape":
                    return

                # Prevent duplicate keys
                if key in self.key_bindings:
                    messagebox.showwarning(
                        "Key already used",
                        "That key is already assigned "
                        "to another lane.",
                    )
                    return

                self.key_bindings[
                    self.rebinding_lane
                ] = key

                self.rebinding_lane = None

                self.build_keybinds()

                return

            return

        # Tutorial
        if self.screen == "tutorial":

            if key == "escape":
                self.build_menu()

            return

        # Pause
        if self.screen == "game":

            if key == "escape":
                self.toggle_pause()
                return

            if self.paused:
                return

            if key in self.key_bindings:

                lane = self.key_bindings.index(
                    key
                )

                self.hit_lane(lane)

    # ========================================================
    # BACKGROUND
    # ========================================================

    def draw_background(self):

        self.canvas.delete(
            "background"
        )

        # Base red
        self.canvas.create_rectangle(
            0,
            0,
            WINDOW_WIDTH,
            WINDOW_HEIGHT,
            fill=BACKGROUND,
            outline="",
            tags="background",
        )

        # Dark red bottom
        self.canvas.create_rectangle(
            0,
            WINDOW_HEIGHT * 0.70,
            WINDOW_WIDTH,
            WINDOW_HEIGHT,
            fill=BACKGROUND_DARK,
            outline="",
            tags="background",
        )

        # Subtle center glow
        self.canvas.create_oval(
            -180,
            -150,
            WINDOW_WIDTH + 180,
            WINDOW_HEIGHT * 0.75,
            fill="#c00000",
            outline="",
            tags="background",
        )

        self.canvas.tag_lower(
            "background"
        )

    def draw_particles(self):

        for particle in self.particles:

            size = particle.size

            x = particle.x
            y = particle.y

            self.canvas.create_oval(
                x - size,
                y - size,
                x + size,
                y + size,
                fill=WHITE,
                outline="",
                tags="particle",
            )

    def update_particles(self, dt):

        for particle in self.particles:
            particle.update(dt)

    # ========================================================
    # ANIMATION
    # ========================================================

    def animation_loop(self):

        if not self.running:
            return

        now = time.perf_counter()

        dt = now - self.last_frame

        self.last_frame = now

        dt = min(
            dt,
            0.05,
        )

        self.update_particles(dt)

        if self.screen in (
            "menu",
            "tutorial",
            "keybinds",
            "difficulty",
            "results",
        ):
            self.redraw_current_screen()

        elif self.screen == "game":
            self.draw_game()

        self.root.after(
            16,
            self.animation_loop,
        )

    def redraw_current_screen(self):

        if self.screen == "menu":
            self.draw_menu()

        elif self.screen == "tutorial":
            self.draw_tutorial()

        elif self.screen == "keybinds":
            self.draw_keybinds()

        elif self.screen == "difficulty":
            self.draw_difficulty()

        elif self.screen == "results":
            self.draw_results()

    # ========================================================
    # BUTTON
    # ========================================================

    def button(
        self,
        text,
        x1,
        y1,
        x2,
        y2,
        command,
        font=("Arial", 16, "bold"),
    ):

        self.canvas.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            fill="#7e0000",
            outline="#ffffff",
            width=2,
            tags="ui",
        )

        self.canvas.create_text(
            (x1 + x2) / 2,
            (y1 + y2) / 2,
            text=text,
            fill=WHITE,
            font=font,
            tags="ui",
        )

        self.canvas.tag_bind(
            "ui",
            "<Button-1>",
            lambda e: None,
        )

        # Use a unique rectangle/text group
        tag = f"button_{id(command)}_{random.random()}"

        self.canvas.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            fill="#7e0000",
            outline="#ffffff",
            width=2,
            tags=(tag,),
        )

        self.canvas.create_text(
            (x1 + x2) / 2,
            (y1 + y2) / 2,
            text=text,
            fill=WHITE,
            font=font,
            tags=(tag,),
        )

        self.canvas.tag_bind(
            tag,
            "<Button-1>",
            lambda event: command(),
        )

        self.canvas.tag_bind(
            tag,
            "<Enter>",
            lambda event: self.canvas.itemconfigure(
                tag,
                fill="#a80000",
            ),
        )

        self.canvas.tag_bind(
            tag,
            "<Leave>",
            lambda event: self.canvas.itemconfigure(
                tag,
                fill="#7e0000",
            ),
        )

    # ========================================================
    # MENU
    # ========================================================

    def build_menu(self):
        self.screen = "menu"
        self.canvas.delete("all")

        self.draw_menu()

    def draw_menu(self):

        self.canvas.delete("all")

        self.draw_background()
        self.draw_particles()

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            75,
            text="MANIATK",
            fill=WHITE,
            font=("Arial", 42, "bold"),
        )

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            118,
            text="4K RHYTHM GAME",
            fill=WHITE,
            font=("Arial", 14, "bold"),
        )

        song_text = (
            self.song_display_name
            if self.song_display_name
            else "No song imported"
        )

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            165,
            text=f"Song: {song_text}",
            fill=WHITE,
            font=("Arial", 13),
        )

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            190,
            text=f"Difficulty: {self.difficulty}",
            fill=WHITE,
            font=("Arial", 13, "bold"),
        )

        # Buttons
        self.button(
            "IMPORT MP3 / MP4",
            170,
            225,
            550,
            275,
            self.import_song,
        )

        self.button(
            "SELECT DIFFICULTY",
            170,
            290,
            550,
            340,
            self.open_difficulty,
        )

        self.button(
            "KEYBINDS",
            170,
            355,
            550,
            405,
            self.open_keybinds,
        )

        self.button(
            "GENERATE BEATMAP",
            170,
            420,
            550,
            470,
            self.generate_chart,
        )

        self.button(
            "PLAY",
            170,
            485,
            550,
            540,
            self.start_game,
        )

        self.button(
            "TUTORIAL",
            170,
            555,
            550,
            605,
            self.open_tutorial,
        )

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            650,
            text=(
                "Controls: "
                + "  ".join(
                    x.upper()
                    for x in self.key_bindings
                )
            ),
            fill=WHITE,
            font=("Arial", 12, "bold"),
        )

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            680,
            text=(
                "ESC = Pause during gameplay"
            ),
            fill=WHITE,
            font=("Arial", 11),
        )

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            750,
            text=f"Version {GAME_VERSION}",
            fill=WHITE,
            font=("Arial", 10),
        )

    # ========================================================
    # IMPORT
    # ========================================================

    def import_song(self):

        path = filedialog.askopenfilename(
            title="Select a song or video",
            filetypes=[
                (
                    "Audio / Video",
                    "*.mp3 *.mp4 *.wav *.ogg "
                    "*.m4a *.wma *.flac *.avi *.mkv",
                ),
                (
                    "All files",
                    "*.*",
                ),
            ],
        )

        if not path:
            return

        self.song_path = path

        self.song_display_name = os.path.basename(
            path
        )

        self.notes = []

        messagebox.showinfo(
            "Song imported",
            "Song imported successfully.\n\n"
            "Now select a difficulty and "
            "generate the beatmap.",
        )

        self.build_menu()

    # ========================================================
    # DIFFICULTY
    # ========================================================

    def open_difficulty(self):

        self.screen = "difficulty"

        self.canvas.delete("all")

        self.draw_difficulty()

    def draw_difficulty(self):

        self.canvas.delete("all")

        self.draw_background()
        self.draw_particles()

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            55,
            text="SELECT DIFFICULTY",
            fill=WHITE,
            font=("Arial", 30, "bold"),
        )

        names = list(
            DIFFICULTIES.keys()
        )

        start_y = 105

        for index, name in enumerate(names):

            y = (
                start_y
                + index * 90
            )

            selected = (
                name == self.difficulty
            )

            fill = (
                "#c00000"
                if selected
                else "#760000"
            )

            tag = (
                f"difficulty_{index}"
            )

            self.canvas.create_rectangle(
                70,
                y,
                650,
                y + 72,
                fill=fill,
                outline=WHITE,
                width=2,
                tags=tag,
            )

            self.canvas.create_text(
                105,
                y + 25,
                text=name,
                anchor="w",
                fill=WHITE,
                font=("Arial", 16, "bold"),
                tags=tag,
            )

            self.canvas.create_text(
                105,
                y + 50,
                text=DIFFICULTIES[name][
                    "description"
                ],
                anchor="w",
                fill=WHITE,
                font=("Arial", 10),
                tags=tag,
            )

            self.canvas.tag_bind(
                tag,
                "<Button-1>",
                lambda event, n=name:
                self.select_difficulty(n),
            )

        self.button(
            "BACK",
            250,
            675,
            470,
            725,
            self.build_menu,
        )

    def select_difficulty(self, name):

        self.difficulty = name

        self.build_menu()

    # ========================================================
    # KEYBINDS
    # ========================================================

    def open_keybinds(self):

        self.screen = "keybinds"
        self.rebinding_lane = None

        self.build_keybinds()

    def build_keybinds(self):

        self.canvas.delete("all")

        self.draw_background()
        self.draw_particles()

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            60,
            text="KEYBINDS",
            fill=WHITE,
            font=("Arial", 32, "bold"),
        )

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            95,
            text="Click a lane, then press the key you want.",
            fill=WHITE,
            font=("Arial", 11),
        )

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            120,
            text="ESC cancels a rebinding.",
            fill=WHITE,
            font=("Arial", 11),
        )

        labels = [
            "LANE 1",
            "LANE 2",
            "LANE 3",
            "LANE 4",
        ]

        for i in range(LANES):

            y = 160 + i * 105

            if (
                self.rebinding_lane
                == i
            ):
                fill = "#ff3333"
                key_text = "PRESS A KEY..."
            else:
                fill = "#760000"
                key_text = (
                    self.key_bindings[i]
                    .upper()
                )

            tag = (
                f"bind_{i}"
            )

            self.canvas.create_rectangle(
                150,
                y,
                570,
                y + 78,
                fill=fill,
                outline=WHITE,
                width=2,
                tags=tag,
            )

            self.canvas.create_text(
                175,
                y + 25,
                text=labels[i],
                anchor="w",
                fill=WHITE,
                font=("Arial", 15, "bold"),
                tags=tag,
            )

            self.canvas.create_text(
                530,
                y + 25,
                text=key_text,
                anchor="e",
                fill=WHITE,
                font=("Arial", 18, "bold"),
                tags=tag,
            )

            self.canvas.create_text(
                175,
                y + 53,
                text=(
                    "Click to rebind"
                    if self.rebinding_lane != i
                    else "Waiting for key..."
                ),
                anchor="w",
                fill=WHITE,
                font=("Arial", 10),
                tags=tag,
            )

            self.canvas.tag_bind(
                tag,
                "<Button-1>",
                lambda event, lane=i:
                self.start_rebind(lane),
            )

        self.button(
            "RESET D/F/J/K",
            150,
            595,
            570,
            645,
            self.reset_keybinds,
        )

        self.button(
            "BACK",
            250,
            670,
            470,
            720,
            self.build_menu,
        )

    def start_rebind(self, lane):

        self.rebinding_lane = lane

        self.build_keybinds()

    def reset_keybinds(self):

        self.key_bindings = (
            DEFAULT_KEYS.copy()
        )

        self.rebinding_lane = None

        self.build_keybinds()

    # ========================================================
    # BEATMAP
    # ========================================================

    def generate_chart(self):

        if not self.song_path:

            messagebox.showwarning(
                "No song",
                "Import a song first.",
            )

            return

        try:

            self.canvas.delete("all")

            self.draw_background()
            self.draw_particles()

            self.canvas.create_text(
                WINDOW_WIDTH / 2,
                WINDOW_HEIGHT / 2 - 30,
                text="GENERATING BEATMAP...",
                fill=WHITE,
                font=("Arial", 24, "bold"),
            )

            self.root.update()

            wav_path, converted = (
                convert_to_wav(
                    self.song_path
                )
            )

            if converted:
                self.converted_audio = wav_path
                self.converted_temp_dir = (
                    os.path.dirname(wav_path)
                )
            else:
                self.converted_audio = None
                self.converted_temp_dir = None

            self.notes = generate_beatmap(
                wav_path,
                self.difficulty,
            )

            if not self.notes:
                raise RuntimeError(
                    "No notes could be generated "
                    "from this audio."
                )

            messagebox.showinfo(
                "Beatmap generated",
                f"Generated {len(self.notes)} notes.\n\n"
                f"Difficulty: {self.difficulty}",
            )

            self.build_menu()

        except Exception as exc:

            messagebox.showerror(
                "Beatmap generation failed",
                str(exc),
            )

            self.build_menu()

    # ========================================================
    # GAME START
    # ========================================================

    def start_game(self):

        if not self.song_path:

            messagebox.showwarning(
                "No song",
                "Import a song first.",
            )

            return

        if not self.notes:

            answer = messagebox.askyesno(
                "No beatmap",
                "There is no generated beatmap.\n\n"
                "Generate one automatically now?",
            )

            if not answer:
                return

            self.generate_chart()

            if not self.notes:
                return

        # Reset stats
        self.score = 0
        self.combo = 0
        self.max_combo = 0

        self.perfects = 0
        self.greats = 0
        self.goods = 0
        self.misses = 0

        self.judgement_text = ""
        self.judgement_until = 0

        # Reset note state
        for note in self.notes:
            note["hit"] = False
            note["judgement"] = None

        self.paused = False

        self.screen = "game"

        audio_file = (
            self.converted_audio
            if self.converted_audio
            else self.song_path
        )

        if not os.path.exists(
            audio_file
        ):
            messagebox.showerror(
                "Audio missing",
                "The audio file could not be found.",
            )

            self.build_menu()
            return

        success = self.audio.play(
            audio_file,
            0.0,
        )

        if not success:

            messagebox.showerror(
                "Audio error",
                "Could not play the selected audio.\n\n"
                "Install FFmpeg and make sure "
                "ffplay.exe is available in PATH.",
            )

            self.build_menu()

    # ========================================================
    # GAME INPUT
    # ========================================================

    def hit_lane(self, lane):

        if self.screen != "game":
            return

        current_time = (
            self.audio.position()
        )

        candidates = []

        for note in self.notes:

            if note["hit"]:
                continue

            if note["lane"] != lane:
                continue

            difference = (
                current_time
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
                        difference,
                    )
                )

        if not candidates:

            self.judgement_text = "EMPTY"
            self.judgement_until = (
                time.perf_counter()
                + 0.18
            )

            return

        candidates.sort(
            key=lambda x: x[0]
        )

        _, note, difference = (
            candidates[0]
        )

        absolute = abs(
            difference
        )

        if absolute <= PERFECT_WINDOW:

            judgement = "PERFECT"
            points = 300

            self.perfects += 1

        elif absolute <= GREAT_WINDOW:

            judgement = "GREAT"
            points = 200

            self.greats += 1

        elif absolute <= GOOD_WINDOW:

            judgement = "GOOD"
            points = 100

            self.goods += 1

        else:

            judgement = "GOOD"
            points = 50

            self.goods += 1

        note["hit"] = True
        note["judgement"] = judgement

        self.score += points

        self.combo += 1

        self.max_combo = max(
            self.max_combo,
            self.combo,
        )

        self.judgement_text = (
            judgement
        )

        self.judgement_until = (
            time.perf_counter()
            + 0.45
        )

    # ========================================================
    # MISS CHECK
    # ========================================================

    def check_misses(self):

        current_time = (
            self.audio.position()
        )

        for note in self.notes:

            if note["hit"]:
                continue

            if (
                current_time
                - note["time"]
                > MISS_WINDOW
            ):

                note["hit"] = True
                note["judgement"] = "MISS"

                self.misses += 1
                self.combo = 0

                self.judgement_text = "MISS"

                self.judgement_until = (
                    time.perf_counter()
                    + 0.45
                )

    # ========================================================
    # GAME DRAW
    # ========================================================

    def draw_game(self):

        self.canvas.delete("all")

        # Background
        self.draw_background()
        self.draw_particles()

        # Game playfield
        playfield_bottom = (
            WINDOW_HEIGHT
        )

        for lane in range(LANES):

            x1 = (
                PLAYFIELD_X
                + lane
                * (
                    LANE_WIDTH
                    + LANE_GAP
                )
            )

            x2 = x1 + LANE_WIDTH

            self.canvas.create_rectangle(
                x1,
                0,
                x2,
                playfield_bottom,
                fill="#190000",
                outline="#440000",
                width=2,
            )

            # Lane stripe
            self.canvas.create_rectangle(
                x1,
                0,
                x1 + 2,
                playfield_bottom,
                fill="#600000",
                outline="",
            )

            key = (
                self.key_bindings[lane]
                .upper()
            )

            self.canvas.create_text(
                (x1 + x2) / 2,
                770,
                text=key,
                fill=WHITE,
                font=("Arial", 20, "bold"),
            )

        # Receptors
        for lane in range(LANES):

            x1 = (
                PLAYFIELD_X
                + lane
                * (
                    LANE_WIDTH
                    + LANE_GAP
                )
            )

            x2 = x1 + LANE_WIDTH

            self.canvas.create_rectangle(
                x1,
                RECEPTOR_Y,
                x2,
                RECEPTOR_Y + 12,
                fill=NOTE_COLORS[lane],
                outline=WHITE,
                width=2,
            )

        current_time = (
            self.audio.position()
        )

        # Notes
        for note in self.notes:

            if note["hit"]:
                continue

            delta = (
                note["time"]
                - current_time
            )

            y = (
                RECEPTOR_Y
                - delta * NOTE_SPEED
            )

            if (
                y < -NOTE_HEIGHT
                or y > WINDOW_HEIGHT + 30
            ):
                continue

            lane = note["lane"]

            x1 = (
                PLAYFIELD_X
                + lane
                * (
                    LANE_WIDTH
                    + LANE_GAP
                )
                + 4
            )

            x2 = (
                x1
                + LANE_WIDTH
                - 8
            )

            self.canvas.create_rectangle(
                x1,
                y,
                x2,
                y + NOTE_HEIGHT,
                fill=NOTE_COLORS[lane],
                outline=WHITE,
                width=2,
            )

        # HUD
        self.canvas.create_text(
            15,
            15,
            text=f"SCORE  {self.score}",
            anchor="nw",
            fill=WHITE,
            font=("Arial", 16, "bold"),
        )

        self.canvas.create_text(
            15,
            42,
            text=f"COMBO  {self.combo}",
            anchor="nw",
            fill=WHITE,
            font=("Arial", 14, "bold"),
        )

        self.canvas.create_text(
            WINDOW_WIDTH - 15,
            15,
            text=f"{self.difficulty}",
            anchor="ne",
            fill=WHITE,
            font=("Arial", 13, "bold"),
        )

        accuracy = self.get_accuracy()

        self.canvas.create_text(
            WINDOW_WIDTH - 15,
            42,
            text=f"ACC  {accuracy:.2f}%",
            anchor="ne",
            fill=WHITE,
            font=("Arial", 13, "bold"),
        )

        # Judgement
        if (
            time.perf_counter()
            < self.judgement_until
        ):

            self.canvas.create_text(
                WINDOW_WIDTH / 2,
                625,
                text=self.judgement_text,
                fill=WHITE,
                font=("Arial", 24, "bold"),
            )

        # Pause overlay
        if self.paused:
            self.draw_pause_overlay()

        # Finished
        self.check_song_finished()

    # ========================================================
    # PAUSE
    # ========================================================

    def draw_pause_overlay(self):

        self.canvas.create_rectangle(
            0,
            0,
            WINDOW_WIDTH,
            WINDOW_HEIGHT,
            fill="#000000",
            stipple="gray50",
            outline="",
        )

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            150,
            text="PAUSED",
            fill=WHITE,
            font=("Arial", 38, "bold"),
        )

        self.button(
            "RESUME",
            210,
            250,
            510,
            300,
            self.resume_game,
        )

        self.button(
            "QUIT BEATMAP",
            210,
            325,
            510,
            375,
            self.quit_beatmap,
        )

        self.button(
            "EXIT GAME",
            210,
            400,
            510,
            450,
            self.exit_game,
        )

    def toggle_pause(self):

        if self.screen != "game":
            return

        if self.paused:
            self.resume_game()
        else:
            self.pause_game()

    def pause_game(self):

        if self.paused:
            return

        self.paused = True

        self.audio.pause()

    def resume_game(self):

        if not self.paused:
            return

        self.paused = False

        self.audio.resume()

    def quit_beatmap(self):

        self.audio.stop()

        self.paused = False

        self.build_menu()

    # ========================================================
    # FINISH
    # ========================================================

    def check_song_finished(self):

        if self.paused:
            return

        if not self.audio.playing:
            return

        if not self.audio.is_finished():
            return

        self.audio.stop()

        self.screen = "results"

    # ========================================================
    # ACCURACY
    # ========================================================

    def get_accuracy(self):

        total = (
            self.perfects
            + self.greats
            + self.goods
            + self.misses
        )

        if total == 0:
            return 100.0

        weighted = (
            self.perfects * 100
            + self.greats * 70
            + self.goods * 40
        )

        return weighted / total

    # ========================================================
    # RESULTS
    # ========================================================

    def draw_results(self):

        self.canvas.delete("all")

        self.draw_background()
        self.draw_particles()

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            70,
            text="RESULTS",
            fill=WHITE,
            font=("Arial", 38, "bold"),
        )

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            125,
            text=self.difficulty,
            fill=WHITE,
            font=("Arial", 18, "bold"),
        )

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            175,
            text=f"SCORE  {self.score}",
            fill=WHITE,
            font=("Arial", 25, "bold"),
        )

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            215,
            text=f"ACCURACY  {self.get_accuracy():.2f}%",
            fill=WHITE,
            font=("Arial", 20),
        )

        stats = (
            f"PERFECT   {self.perfects}\n\n"
            f"GREAT     {self.greats}\n\n"
            f"GOOD      {self.goods}\n\n"
            f"MISS      {self.misses}\n\n"
            f"MAX COMBO {self.max_combo}"
        )

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            390,
            text=stats,
            fill=WHITE,
            font=("Arial", 15, "bold"),
            justify="center",
        )

        self.button(
            "PLAY AGAIN",
            180,
            610,
            540,
            660,
            self.start_game,
        )

        self.button(
            "MAIN MENU",
            180,
            680,
            540,
            730,
            self.build_menu,
        )

    # ========================================================
    # TUTORIAL
    # ========================================================

    def open_tutorial(self):

        self.screen = "tutorial"

        self.tutorial_scroll = 0

        self.draw_tutorial()

    def draw_tutorial(self):

        self.canvas.delete("all")

        self.draw_background()
        self.draw_particles()

        self.canvas.create_text(
            WINDOW_WIDTH / 2,
            45,
            text="HOW TO PLAY",
            fill=WHITE,
            font=("Arial", 32, "bold"),
        )

        # Tutorial panel
        self.canvas.create_rectangle(
            45,
            85,
            675,
            690,
            fill="#650000",
            outline=WHITE,
            width=2,
        )

        tutorial_text = (
            "MANIATK TUTORIAL\n\n"

            "1. IMPORT A SONG\n"
            "Click IMPORT MP3 / MP4 and select "
            "an audio or video file.\n\n"

            "2. SELECT YOUR DIFFICULTY\n"
            "Choose from EASY, NORMAL, HARD, "
            "INSANE, EXTREME, or OSU PRO.\n\n"

            "3. GENERATE THE BEATMAP\n"
            "ManiaTK analyzes the audio and "
            "automatically creates notes.\n\n"

            "4. PLAY\n"
            "Notes fall toward the four receptors.\n"
            "Press the matching lane key when "
            "the note reaches the receptor.\n\n"

            "DEFAULT CONTROLS\n"
            "D       F       J       K\n"
            "Lane 1  Lane 2  Lane 3  Lane 4\n\n"

            "KEYBINDS\n"
            "Open KEYBINDS from the main menu "
            "to change the controls.\n"
            "Each key can only be assigned once.\n\n"

            "JUDGEMENTS\n"
            "PERFECT = extremely accurate hit\n"
            "GREAT   = very accurate hit\n"
            "GOOD    = acceptable hit\n"
            "MISS    = note was not hit in time\n\n"

            "EMPTY\n"
            "Pressing a lane when no note is nearby "
            "does not hurt your score or combo.\n\n"

            "PAUSE\n"
            "Press ESC during gameplay.\n"
            "Resume continues the song from the "
            "same position.\n\n"

            "QUIT BEATMAP\n"
            "Stops the music and returns to the menu.\n\n"

            "UPDATE\n"
            "If ManiaTK detects a newer version, "
            "run the ManiaTK installer again.\n"
        )

        self.canvas.create_text(
            70,
            110,
            text=tutorial_text,
            anchor="nw",
            fill=WHITE,
            font=("Arial", 11),
            width=670,
            justify="left",
        )

        self.button(
            "BACK TO MENU",
            220,
            715,
            500,
            765,
            self.build_menu,
        )

    # ========================================================
    # UPDATE CHECK
    # ========================================================

    def check_for_updates(self):

        if not self.running:
            return

        def worker():

            try:

                with urllib.request.urlopen(
                    VERSION_URL,
                    timeout=5,
                ) as response:

                    remote = (
                        response.read()
                        .decode(
                            "utf-8",
                            errors="ignore",
                        )
                        .strip()
                    )

                if not remote:
                    return

                if self.version_is_newer(
                    remote,
                    GAME_VERSION,
                ):

                    self.root.after(
                        0,
                        lambda: messagebox.showinfo(
                            "ManiaTK update available",
                            "A newer version of ManiaTK "
                            "is available.\n\n"
                            f"Installed version: {GAME_VERSION}\n"
                            f"Latest version: {remote}\n\n"
                            "Please run the ManiaTK installer "
                            "again to update the game.",
                        ),
                    )

            except Exception:
                # Update checks should never stop the game.
                pass

        threading.Thread(
            target=worker,
            daemon=True,
        ).start()

    @staticmethod
    def version_is_newer(
        remote,
        current,
    ):

        def parse(version):

            parts = []

            for item in version.split("."):

                digits = ""

                for char in item:

                    if char.isdigit():
                        digits += char
                    else:
                        break

                if digits:
                    parts.append(
                        int(digits)
                    )
                else:
                    parts.append(0)

            while len(parts) < 4:
                parts.append(0)

            return tuple(parts[:4])

        try:
            return parse(remote) > parse(current)

        except Exception:
            return False

    # ========================================================
    # EXIT
    # ========================================================

    def exit_game(self):

        if not self.running:
            return

        self.running = False

        try:
            self.audio.close()
        except Exception:
            pass

        if self.converted_temp_dir:
            try:
                shutil.rmtree(
                    self.converted_temp_dir,
                    ignore_errors=True,
                )
            except Exception:
                pass

        try:
            self.root.destroy()
        except Exception:
            pass

    # ========================================================
    # RUN
    # ========================================================

    def run(self):

        self.root.mainloop()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    try:
        app = ManiaTK()
        app.run()

    except KeyboardInterrupt:
        pass

    except Exception as exc:

        try:
            root = tk.Tk()
            root.withdraw()

            messagebox.showerror(
                "ManiaTK Error",
                str(exc),
            )

            root.destroy()

        except Exception:
            print(
                "ManiaTK Error:",
                exc,
            )
