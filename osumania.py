# ============================================================
# ManiaTK 1.0.2
# Python 3.14 compatible
# 4K osu!mania-inspired rhythm game
#
# NO PYGAME
#
# FEATURES
#   - MP3 / MP4 / WAV / OGG / M4A / WMA / FLAC / AVI / MKV
#   - YouTube URL importing
#   - Automatic YouTube audio download with yt-dlp
#   - Automatic BPM detection
#   - Automatic rhythm/onset detection
#   - Beat-grid chart generation
#   - 6 difficulties
#   - 4K D/F/J/K
#   - FNF-style arrows
#   - Adjustable note speed
#   - Key glow
#   - Hit glow
#   - PERFECT / GREAT / GOOD / MISS / NO NOTE
#   - Pause menu
#   - Results screen
#   - Tutorial
#   - Animated red background
#   - White particles
#   - GitHub version checking
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

import numpy as np

try:
    import yt_dlp
except ImportError:
    yt_dlp = None


# ============================================================
# GAME SETTINGS
# ============================================================

GAME_NAME = "ManiaTK"
GAME_VERSION = "1.0.2"

GITHUB_VERSION_URL = (
    "https://raw.githubusercontent.com/"
    "mendozathird8-svg/My-Project/main/version.txt"
)

DEFAULT_NOTE_SPEED = 420
MIN_NOTE_SPEED = 180
MAX_NOTE_SPEED = 900

KEYS = ["d", "f", "j", "k"]

KEY_LABELS = {
    "d": "D",
    "f": "F",
    "j": "J",
    "k": "K",
}


# ============================================================
# DIFFICULTIES
# ============================================================

DIFFICULTIES = {
    "EASY": {
        "threshold": 72,
        "min_spacing": 0.240,
        "subdivision": 1,
        "chords": False,
        "jumps": False,
    },

    "NORMAL": {
        "threshold": 63,
        "min_spacing": 0.155,
        "subdivision": 1,
        "chords": True,
        "jumps": False,
    },

    "HARD": {
        "threshold": 54,
        "min_spacing": 0.115,
        "subdivision": 2,
        "chords": True,
        "jumps": True,
    },

    "INSANE": {
        "threshold": 45,
        "min_spacing": 0.082,
        "subdivision": 2,
        "chords": True,
        "jumps": True,
    },

    "EXTREME": {
        "threshold": 38,
        "min_spacing": 0.060,
        "subdivision": 4,
        "chords": True,
        "jumps": True,
    },

    "OSU PRO (MY BROTHER)": {
        "threshold": 30,
        "min_spacing": 0.042,
        "subdivision": 4,
        "chords": True,
        "jumps": True,
    },
}


DIFFICULTY_DESCRIPTIONS = {
    "EASY": "Slow notes with simple patterns.",
    "NORMAL": "A normal 4K experience.",
    "HARD": "Faster notes and occasional jumps.",
    "INSANE": "Dense patterns and fast streams.",
    "EXTREME": "Very fast and difficult.",
    "OSU PRO (MY BROTHER)": "Absolutely ridiculous.",
}


# ============================================================
# PATH / PROGRAM HELPERS
# ============================================================

def resource_path(filename):
    base = os.path.dirname(
        os.path.abspath(__file__)
    )

    return os.path.join(
        base,
        filename
    )


def find_program(names):

    for name in names:

        path = shutil.which(name)

        if path:
            return path

    return None


# ============================================================
# FFMPEG
# ============================================================

def convert_to_wav(input_file):

    ffmpeg = find_program([
        "ffmpeg.exe",
        "ffmpeg",
    ])

    if not ffmpeg:

        raise RuntimeError(
            "FFmpeg was not found.\n\n"
            "Install FFmpeg and make sure "
            "ffmpeg.exe is in PATH."
        )

    temp_dir = tempfile.mkdtemp(
        prefix="maniatk_"
    )

    output_wav = os.path.join(
        temp_dir,
        "audio.wav"
    )

    command = [
        ffmpeg,
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
        output_wav,
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )

    if (
        result.returncode != 0
        or not os.path.exists(output_wav)
    ):

        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )

        raise RuntimeError(
            "FFmpeg could not convert the selected file.\n\n"
            + result.stderr[-1500:]
        )

    return output_wav, temp_dir


# ============================================================
# WAV READER
# ============================================================

def read_wav(filename):

    with wave.open(filename, "rb") as wf:

        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        frames = wf.getnframes()

        raw = wf.readframes(frames)

    if sample_width == 2:

        data = np.frombuffer(
            raw,
            dtype=np.int16
        ).astype(np.float32)

    elif sample_width == 1:

        data = (
            np.frombuffer(
                raw,
                dtype=np.uint8
            ).astype(np.float32)
            - 128.0
        )

    elif sample_width == 4:

        data = np.frombuffer(
            raw,
            dtype=np.int32
        ).astype(np.float32)

    else:

        raise RuntimeError(
            f"Unsupported WAV sample width: "
            f"{sample_width}"
        )

    if channels > 1:

        data = data.reshape(
            -1,
            channels
        )

        data = np.mean(
            data,
            axis=1
        )

    max_value = (
        float(np.max(np.abs(data)))
        if len(data)
        else 1
    )

    if max_value > 0:
        data /= max_value

    return (
        data.astype(np.float32),
        sample_rate
    )


# ============================================================
# BPM ESTIMATION
# ============================================================

def estimate_bpm(
    samples,
    sample_rate
):

    if len(samples) < sample_rate:
        return 120.0

    frame_size = 2048
    hop = 512

    count = (
        1
        + (len(samples) - frame_size)
        // hop
    )

    if count < 10:
        return 120.0

    window = np.hanning(
        frame_size
    )

    previous = None

    energy = []

    for i in range(count):

        start = i * hop

        frame = samples[
            start:start + frame_size
        ]

        if len(frame) != frame_size:
            break

        spectrum = np.abs(
            np.fft.rfft(
                frame * window
            )
        )

        spectrum = np.log1p(
            spectrum
        )

        if previous is None:

            flux = 0.0

        else:

            diff = (
                spectrum
                - previous
            )

            diff[diff < 0] = 0

            flux = float(
                np.sum(diff)
            )

        previous = spectrum

        rms = float(
            np.sqrt(
                np.mean(
                    frame * frame
                )
            )
        )

        energy.append(
            flux * 0.8
            + rms * 0.2
        )

    if len(energy) < 20:
        return 120.0

    env = np.asarray(
        energy,
        dtype=np.float64
    )

    env -= np.mean(env)

    std = np.std(env)

    if std > 0:
        env /= std

    kernel = np.ones(3) / 3

    env = np.convolve(
        env,
        kernel,
        mode="same"
    )

    min_bpm = 70
    max_bpm = 190

    fps = sample_rate / hop

    min_lag = int(
        fps * 60 / max_bpm
    )

    max_lag = int(
        fps * 60 / min_bpm
    )

    if max_lag >= len(env):
        max_lag = len(env) - 1

    best_bpm = 120.0
    best_score = -float("inf")

    for lag in range(
        min_lag,
        max_lag + 1
    ):

        score = float(
            np.dot(
                env[:-lag],
                env[lag:]
            )
        )

        bpm = (
            60.0 * fps / lag
        )

        if 85 <= bpm <= 175:
            score *= 1.03

        if score > best_score:

            best_score = score
            best_bpm = bpm

    candidates = [
        80,
        90,
        100,
        110,
        120,
        128,
        130,
        135,
        140,
        145,
        150,
        160,
        170,
        180,
    ]

    for candidate in candidates:

        if abs(
            best_bpm - candidate
        ) < 2.5:

            best_bpm = float(
                candidate
            )

            break

    return float(
        np.clip(
            best_bpm,
            60,
            220
        )
    )


# ============================================================
# ONSET DETECTION
# ============================================================

def calculate_onsets(
    samples,
    sample_rate
):

    frame_size = 2048
    hop = 256

    if len(samples) < frame_size:
        return []

    window = np.hanning(
        frame_size
    )

    previous = None

    strengths = []
    times = []

    count = (
        1
        + (len(samples) - frame_size)
        // hop
    )

    for i in range(count):

        start = i * hop

        frame = samples[
            start:start + frame_size
        ]

        spectrum = np.abs(
            np.fft.rfft(
                frame * window
            )
        )

        spectrum = np.log1p(
            spectrum
        )

        if previous is None:

            strength = 0.0

        else:

            difference = (
                spectrum
                - previous
            )

            difference[
                difference < 0
            ] = 0

            strength = float(
                np.sum(difference)
            )

        previous = spectrum

        strengths.append(
            strength
        )

        times.append(
            start / sample_rate
        )

    strengths = np.asarray(
        strengths
    )

    if len(strengths) < 5:
        return []

    low = np.percentile(
        strengths,
        10
    )

    high = np.percentile(
        strengths,
        95
    )

    strengths = (
        (strengths - low)
        / max(
            high - low,
            1e-9
        )
    )

    strengths = np.clip(
        strengths,
        0,
        1
    )

    onsets = []

    for i in range(
        2,
        len(strengths) - 2
    ):

        value = strengths[i]

        if value < 0.08:
            continue

        if (
            value >= strengths[i - 1]
            and value >= strengths[i + 1]
        ):

            onsets.append(
                (
                    times[i],
                    float(value)
                )
            )

    result = []

    last_time = -999

    for timestamp, strength in onsets:

        spacing = (
            timestamp
            - last_time
        )

        if spacing < 0.045:
            continue

        result.append(
            (
                timestamp,
                strength
            )
        )

        last_time = timestamp

    return result


# ============================================================
# LANE SELECTION
# ============================================================

def choose_lane(
    last_lane=None
):

    lanes = [0, 1, 2, 3]

    if (
        last_lane is not None
        and len(lanes) > 1
    ):

        lanes.remove(
            last_lane
        )

    return random.choice(
        lanes
    )


# ============================================================
# CHART GENERATION
# ============================================================

def generate_chart(
    samples,
    sample_rate,
    difficulty_name
):

    settings = DIFFICULTIES[
        difficulty_name
    ]

    bpm = estimate_bpm(
        samples,
        sample_rate
    )

    onsets = calculate_onsets(
        samples,
        sample_rate
    )

    if not onsets:
        return [], bpm

    beat = 60.0 / bpm

    quantized = []

    for timestamp, strength in onsets:

        beat_index = round(
            timestamp / beat
        )

        snapped = (
            beat_index * beat
        )

        error = abs(
            timestamp - snapped
        )

        if error <= beat * 0.22:
            timestamp = snapped

        quantized.append(
            (
                timestamp,
                strength
            )
        )

    unique = {}

    for timestamp, strength in quantized:

        key = round(
            timestamp,
            4
        )

        if key not in unique:

            unique[key] = strength

        else:

            unique[key] = max(
                unique[key],
                strength
            )

    events = sorted(
        unique.items(),
        key=lambda x: x[0]
    )

    notes = []

    last_time = -999
    last_lane = None

    for timestamp, strength in events:

        if timestamp < 0.15:
            continue

        if (
            timestamp - last_time
            < settings["min_spacing"]
        ):
            continue

        threshold = (
            settings["threshold"]
            / 100.0
        )

        if strength < threshold:
            continue

        lane = choose_lane(
            last_lane
        )

        notes.append({
            "time": float(timestamp),
            "lane": lane,
            "hit": False,
            "judgement": None,
        })

        last_lane = lane
        last_time = timestamp

    # --------------------------------------------------------
    # CHORDS
    # --------------------------------------------------------

    if settings["chords"]:

        chord_chance = {
            "NORMAL": 0.06,
            "HARD": 0.10,
            "INSANE": 0.15,
            "EXTREME": 0.20,
            "OSU PRO (MY BROTHER)": 0.28,
        }.get(
            difficulty_name,
            0.05
        )

        extra = []

        for note in notes:

            if random.random() > chord_chance:
                continue

            other_lanes = [
                x
                for x in range(4)
                if x != note["lane"]
            ]

            if not other_lanes:
                continue

            lane = random.choice(
                other_lanes
            )

            extra.append({
                "time": note["time"],
                "lane": lane,
                "hit": False,
                "judgement": None,
            })

        notes.extend(extra)

    # --------------------------------------------------------
    # JUMPS
    # --------------------------------------------------------

    if settings["jumps"]:

        jump_chance = {
            "HARD": 0.035,
            "INSANE": 0.07,
            "EXTREME": 0.12,
            "OSU PRO (MY BROTHER)": 0.18,
        }.get(
            difficulty_name,
            0.02
        )

        extra = []

        for note in notes:

            if random.random() > jump_chance:
                continue

            lane = (
                note["lane"]
                + random.choice(
                    [1, 2, 3]
                )
            ) % 4

            extra.append({
                "time": (
                    note["time"]
                    + random.choice(
                        [
                            -0.015,
                            0.0,
                            0.015
                        ]
                    )
                ),
                "lane": lane,
                "hit": False,
                "judgement": None,
            })

        notes.extend(extra)

    notes.sort(
        key=lambda n: (
            n["time"],
            n["lane"]
        )
    )

    final = []
    seen = set()

    for note in notes:

        key = (
            round(
                note["time"],
                4
            ),
            note["lane"]
        )

        if key in seen:
            continue

        seen.add(key)
        final.append(note)

    return final, bpm


# ============================================================
# AUDIO PLAYER
# ============================================================

class AudioPlayer:

    def __init__(self):

        self.process = None
        self.file = None

        self.started_at = 0.0
        self.pause_position = 0.0

        self.playing = False

    def play(
        self,
        filename,
        position=0.0
    ):

        self.stop()

        ffplay = find_program([
            "ffplay.exe",
            "ffplay",
        ])

        if not ffplay:

            raise RuntimeError(
                "ffplay.exe was not found.\n\n"
                "Install FFmpeg and make sure "
                "ffplay.exe is available."
            )

        self.file = filename

        self.pause_position = position

        command = [
            ffplay,
            "-nodisp",
            "-autoexit",
            "-loglevel",
            "quiet",
            "-ss",
            str(max(0, position)),
            filename,
        ]

        self.process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        self.started_at = (
            time.perf_counter()
            - position
        )

        self.playing = True

    def get_position(self):

        if not self.playing:
            return self.pause_position

        return (
            time.perf_counter()
            - self.started_at
        )

    def pause(self):

        if not self.playing:
            return

        self.pause_position = (
            self.get_position()
        )

        if self.process:

            try:
                self.process.terminate()
            except Exception:
                pass

        self.process = None
        self.playing = False

    def resume(self):

        if self.file:

            self.play(
                self.file,
                self.pause_position
            )

    def stop(self):

        if self.process:

            try:
                self.process.terminate()
            except Exception:
                pass

        self.process = None
        self.playing = False

    def close(self):
        self.stop()


# ============================================================
# PARTICLES
# ============================================================

class Particle:

    def __init__(
        self,
        width,
        height
    ):

        self.x = random.uniform(
            0,
            width
        )

        self.y = random.uniform(
            0,
            height
        )

        self.speed = random.uniform(
            10,
            45
        )

        self.size = random.uniform(
            1,
            3
        )

    def update(
        self,
        width,
        height,
        dt
    ):

        self.y -= (
            self.speed * dt
        )

        if self.y < -10:

            self.y = (
                height + 10
            )

            self.x = random.uniform(
                0,
                width
            )

    def draw(self, canvas):

        canvas.create_oval(
            self.x - self.size,
            self.y - self.size,
            self.x + self.size,
            self.y + self.size,
            fill="white",
            outline=""
        )


# ============================================================
# MAIN GAME
# ============================================================

class ManiaTK:

    def __init__(self, root):

        self.root = root

        self.root.title(
            f"{GAME_NAME} {GAME_VERSION}"
        )

        self.root.geometry(
            "1100x760"
        )

        self.root.minsize(
            900,
            650
        )

        self.root.configure(
            bg="#080000"
        )

        self.canvas = tk.Canvas(
            root,
            bg="#080000",
            highlightthickness=0
        )

        self.canvas.pack(
            fill="both",
            expand=True
        )

        self.width = 1100
        self.height = 760

        self.state = "menu"

        self.audio = AudioPlayer()

        self.audio_file = None
        self.wav_file = None
        self.temp_audio_dir = None
        self.youtube_temp_dir = None

        self.notes = []

        self.difficulty = "NORMAL"

        self.note_speed = (
            DEFAULT_NOTE_SPEED
        )

        self.score = 0
        self.combo = 0
        self.max_combo = 0

        self.perfects = 0
        self.greats = 0
        self.goods = 0
        self.misses = 0
        self.no_notes = 0

        self.song_position = 0.0
        self.song_length = 0.0
        self.bpm = 120.0

        self.last_frame = (
            time.perf_counter()
        )

        self.key_down = {
            key: False
            for key in KEYS
        }

        self.key_glow = {
            key: 0.0
            for key in KEYS
        }

        self.hit_flash = [
            0.0
            for _ in range(4)
        ]

        self.judgement_text = ""
        self.judgement_timer = 0.0

        self.menu_buttons = []

        self.particles = [
            Particle(
                self.width,
                self.height
            )
            for _ in range(45)
        ]

        self.root.bind(
            "<KeyPress>",
            self.on_key_press
        )

        self.root.bind(
            "<KeyRelease>",
            self.on_key_release
        )

        self.root.bind(
            "<Escape>",
            self.escape
        )

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.close
        )

        self.root.after(
            16,
            self.loop
        )

        self.show_menu()

    # ========================================================
    # DRAWING
    # ========================================================

    def clear(self):

        self.canvas.delete(
            "all"
        )

        self.menu_buttons.clear()

    def background(self):

        self.canvas.create_rectangle(
            0,
            0,
            self.width,
            self.height,
            fill="#080000",
            outline=""
        )

        for i in range(12):

            y = (
                i
                * self.height
                / 12
            )

            brightness = (
                8 + i * 2
            )

            self.canvas.create_rectangle(
                0,
                y,
                self.width,
                y
                + self.height / 12
                + 2,
                fill=(
                    f"#{brightness:02x}"
                    f"0000"
                ),
                outline=""
            )

        for particle in self.particles:

            particle.draw(
                self.canvas
            )

    def title(
        self,
        text,
        y=80,
        size=42
    ):

        self.canvas.create_text(
            self.width / 2,
            y,
            text=text,
            fill="white",
            font=(
                "Arial",
                size,
                "bold"
            )
        )

    # ========================================================
    # BUTTON
    #
    # FIXED:
    # The text is NOT part of the rectangle's tag.
    # Hover therefore never changes the text color.
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

        tag = (
            f"button_"
            f"{len(self.menu_buttons)}"
        )

        rect = self.canvas.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            fill="#210000",
            outline="#ff2020",
            width=2,
            tags=tag
        )

        text_id = self.canvas.create_text(
            (x1 + x2) / 2,
            (y1 + y2) / 2,
            text=text,
            fill="white",
            font=font
        )

        self.canvas.tag_bind(
            tag,
            "<Button-1>",
            lambda e: command()
        )

        self.canvas.tag_bind(
            tag,
            "<Enter>",
            lambda e, r=rect:
            self.canvas.itemconfigure(
                r,
                fill="#4a0000"
            )
        )

        self.canvas.tag_bind(
            tag,
            "<Leave>",
            lambda e, r=rect:
            self.canvas.itemconfigure(
                r,
                fill="#210000"
            )
        )

        self.canvas.tag_bind(
            text_id,
            "<Button-1>",
            lambda e: command()
        )

        self.canvas.tag_bind(
            text_id,
            "<Enter>",
            lambda e, r=rect:
            self.canvas.itemconfigure(
                r,
                fill="#4a0000"
            )
        )

        self.canvas.tag_bind(
            text_id,
            "<Leave>",
            lambda e, r=rect:
            self.canvas.itemconfigure(
                r,
                fill="#210000"
            )
        )

        self.menu_buttons.append(
            tag
        )

    # ========================================================
    # MENU
    # ========================================================

    def show_menu(self):

        self.state = "menu"

        self.clear()
        self.background()

        self.title(
            "MANIATK",
            75,
            56
        )

        self.canvas.create_text(
            self.width / 2,
            125,
            text="4K RHYTHM GAME",
            fill="#ff4040",
            font=(
                "Arial",
                17,
                "bold"
            )
        )

        if self.audio_file:

            self.canvas.create_text(
                self.width / 2,
                155,
                text=os.path.basename(
                    self.audio_file
                ),
                fill="#aaaaaa",
                font=(
                    "Arial",
                    11
                )
            )

        # ----------------------------------------------------
        # IMPORT SONG
        # ----------------------------------------------------

        self.button(
            370,
            190,
            730,
            240,
            "IMPORT SONG",
            self.import_song
        )

        # ----------------------------------------------------
        # YOUTUBE
        # ----------------------------------------------------

        self.button(
            370,
            255,
            730,
            305,
            "PASTE YOUTUBE LINK",
            self.import_youtube
        )

        # ----------------------------------------------------
        # DIFFICULTY
        # ----------------------------------------------------

        self.button(
            370,
            320,
            730,
            370,
            f"DIFFICULTY: {self.difficulty}",
            self.show_difficulty
        )

        # ----------------------------------------------------
        # SPEED
        # ----------------------------------------------------

        self.button(
            370,
            385,
            730,
            435,
            f"NOTE SPEED: {self.note_speed}",
            self.show_speed
        )

        # ----------------------------------------------------
        # KEYS
        # ----------------------------------------------------

        self.button(
            370,
            450,
            730,
            500,
            "KEY SETTINGS",
            self.key_settings
        )

        # ----------------------------------------------------
        # TUTORIAL
        # ----------------------------------------------------

        self.button(
            370,
            515,
            730,
            565,
            "TUTORIAL",
            self.show_tutorial
        )

        # ----------------------------------------------------
        # EXIT
        # ----------------------------------------------------

        self.button(
            370,
            580,
            730,
            630,
            "EXIT",
            self.close
        )

        self.canvas.create_text(
            self.width / 2,
            690,
            text=(
                f"ManiaTK {GAME_VERSION}"
                "  •  D F J K"
            ),
            fill="#777777",
            font=(
                "Arial",
                11
            )
        )

    # ========================================================
    # LOCAL FILE IMPORT
    # ========================================================

    def import_song(self):

        filename = (
            filedialog.askopenfilename(
                title="Import Music",
                filetypes=[
                    (
                        "Music / Video",
                        (
                            "*.mp3 "
                            "*.mp4 "
                            "*.wav "
                            "*.ogg "
                            "*.m4a "
                            "*.wma "
                            "*.flac "
                            "*.avi "
                            "*.mkv"
                        )
                    ),
                    (
                        "All Files",
                        "*.*"
                    ),
                ]
            )
        )

        if not filename:
            return

        self.audio_file = filename

        self.begin_loading(
            "LOADING SONG...",
            "Analyzing rhythm and generating chart..."
        )

        threading.Thread(
            target=self.process_local_song,
            daemon=True
        ).start()

    # ========================================================
    # LOCAL SONG PROCESSING
    # ========================================================

    def process_local_song(self):

        try:

            wav_file, temp_dir = (
                convert_to_wav(
                    self.audio_file
                )
            )

            samples, sample_rate = (
                read_wav(
                    wav_file
                )
            )

            song_length = (
                len(samples)
                / sample_rate
            )

            notes, bpm = (
                generate_chart(
                    samples,
                    sample_rate,
                    self.difficulty
                )
            )

            if not notes:

                raise RuntimeError(
                    "No rhythm could be detected "
                    "from this song."
                )

            self.root.after(
                0,
                lambda: self.finish_song_load(
                    wav_file,
                    temp_dir,
                    song_length,
                    notes,
                    bpm
                )
            )

        except Exception as exc:

            self.root.after(
                0,
                lambda e=exc:
                self.song_load_error(e)
            )

    # ========================================================
    # YOUTUBE URL WINDOW
    # ========================================================

    def import_youtube(self):

        if yt_dlp is None:

            messagebox.showerror(
                "yt-dlp is missing",
                "YouTube importing needs yt-dlp.\n\n"
                "Open PowerShell and run:\n\n"
                "py -3.14 -m pip install -U "
                "\"yt-dlp[default]\""
            )

            return

        window = tk.Toplevel(
            self.root
        )

        window.title(
            "ManiaTK - YouTube"
        )

        window.geometry(
            "650x245"
        )

        window.resizable(
            False,
            False
        )

        window.configure(
            bg="#080000"
        )

        window.transient(
            self.root
        )

        window.grab_set()

        tk.Label(
            window,
            text="PASTE YOUTUBE LINK",
            fg="white",
            bg="#080000",
            font=(
                "Arial",
                20,
                "bold"
            )
        ).pack(
            pady=(
                25,
                15
            )
        )

        url_var = tk.StringVar()

        entry = tk.Entry(
            window,
            textvariable=url_var,
            bg="#210000",
            fg="white",
            insertbackground="white",
            selectbackground="#800000",
            relief="flat",
            font=(
                "Arial",
                13
            )
        )

        entry.pack(
            padx=40,
            fill="x",
            ipady=10
        )

        entry.focus_set()

        def download():

            url = (
                url_var.get()
                .strip()
            )

            if not url:

                messagebox.showwarning(
                    "ManiaTK",
                    "Paste a YouTube link first.",
                    parent=window
                )

                return

            if (
                "youtube.com" not in url
                and "youtu.be" not in url
                and "youtube-nocookie.com"
                not in url
            ):

                messagebox.showwarning(
                    "ManiaTK",
                    "That does not look like "
                    "a YouTube link.",
                    parent=window
                )

                return

            window.destroy()

            self.download_youtube(
                url
            )

        tk.Button(
            window,
            text="DOWNLOAD & PLAY",
            command=download,
            bg="#210000",
            fg="white",
            activebackground="#4a0000",
            activeforeground="white",
            relief="flat",
            font=(
                "Arial",
                12,
                "bold"
            ),
            cursor="hand2"
        ).pack(
            pady=20,
            ipadx=25,
            ipady=8
        )

        entry.bind(
            "<Return>",
            lambda e: download()
        )

    # ========================================================
    # YOUTUBE DOWNLOAD
    # ========================================================

    def download_youtube(
        self,
        url
    ):

        if yt_dlp is None:

            messagebox.showerror(
                "ManiaTK",
                "yt-dlp is not installed."
            )

            return

        self.state = "loading"

        self.clear()
        self.background()

        self.canvas.create_text(
            self.width / 2,
            self.height / 2 - 55,
            text="DOWNLOADING YOUTUBE VIDEO...",
            fill="white",
            font=(
                "Arial",
                25,
                "bold"
            )
        )

        self.youtube_status_id = (
            self.canvas.create_text(
                self.width / 2,
                self.height / 2 - 5,
                text="Connecting to YouTube...",
                fill="#ff4040",
                font=(
                    "Arial",
                    14
                )
            )
        )

        self.youtube_progress_id = (
            self.canvas.create_rectangle(
                self.width / 2 - 250,
                self.height / 2 + 35,
                self.width / 2 + 250,
                self.height / 2 + 55,
                fill="#210000",
                outline="#ff2020",
                width=2
            )
        )

        self.youtube_progress_fill_id = (
            self.canvas.create_rectangle(
                self.width / 2 - 250,
                self.height / 2 + 35,
                self.width / 2 - 250,
                self.height / 2 + 55,
                fill="#ff2020",
                outline=""
            )
        )

        self.root.update_idletasks()

        threading.Thread(
            target=self.youtube_worker,
            args=(url,),
            daemon=True
        ).start()

    # ========================================================
    # YOUTUBE PROGRESS
    # ========================================================

    def youtube_hook(self, data):

        try:

            status = data.get(
                "status"
            )

            if status == "downloading":

                downloaded = (
                    data.get(
                        "downloaded_bytes",
                        0
                    )
                )

                total = (
                    data.get(
                        "total_bytes"
                    )
                    or data.get(
                        "total_bytes_estimate"
                    )
                    or 0
                )

                if total:

                    percentage = (
                        downloaded
                        / total
                    )

                    percentage = max(
                        0,
                        min(
                            percentage,
                            1
                        )
                    )

                    self.root.after(
                        0,
                        lambda p=percentage:
                        self.update_youtube_progress(
                            p
                        )
                    )

            elif status == "finished":

                self.root.after(
                    0,
                    lambda:
                    self.update_youtube_status(
                        "Download complete. Processing audio..."
                    )
                )

        except Exception:
            pass

    def update_youtube_progress(
        self,
        percentage
    ):

        if not hasattr(
            self,
            "youtube_progress_fill_id"
        ):
            return

        left = (
            self.width / 2 - 250
        )

        right = (
            left
            + 500 * percentage
        )

        try:

            self.canvas.coords(
                self.youtube_progress_fill_id,
                left,
                self.height / 2 + 35,
                right,
                self.height / 2 + 55
            )

            self.canvas.itemconfigure(
                self.youtube_status_id,
                text=(
                    f"Downloading..."
                    f" {percentage * 100:.1f}%"
                )
            )

        except Exception:
            pass

    def update_youtube_status(
        self,
        text
    ):

        try:

            self.canvas.itemconfigure(
                self.youtube_status_id,
                text=text
            )

        except Exception:
            pass

    # ========================================================
    # YOUTUBE WORKER
    # ========================================================

    def youtube_worker(
        self,
        url
    ):

        download_dir = None

        try:

            download_dir = (
                tempfile.mkdtemp(
                    prefix="maniatk_youtube_"
                )
            )

            output_template = os.path.join(
                download_dir,
                "youtube.%(ext)s"
            )

            options = {
                "format": (
                    "bestaudio[ext=m4a]/"
                    "bestaudio/best"
                ),

                "outtmpl": output_template,

                "noplaylist": True,

                "quiet": True,

                "no_warnings": True,

                "progress_hooks": [
                    self.youtube_hook
                ],

                "restrictfilenames": True,
            }

            self.root.after(
                0,
                lambda:
                self.update_youtube_status(
                    "Getting video information..."
                )
            )

            with yt_dlp.YoutubeDL(
                options
            ) as ydl:

                info = (
                    ydl.extract_info(
                        url,
                        download=True
                    )
                )

                title = info.get(
                    "title",
                    "YouTube Song"
                )

                downloaded_file = (
                    ydl.prepare_filename(
                        info
                    )
                )

            # ------------------------------------------------
            # Locate downloaded file.
            # ------------------------------------------------

            if not os.path.exists(
                downloaded_file
            ):

                candidates = []

                for filename in os.listdir(
                    download_dir
                ):

                    full_path = os.path.join(
                        download_dir,
                        filename
                    )

                    if os.path.isfile(
                        full_path
                    ):

                        candidates.append(
                            full_path
                        )

                if not candidates:

                    raise RuntimeError(
                        "yt-dlp finished downloading "
                        "but no file was found."
                    )

                downloaded_file = max(
                    candidates,
                    key=os.path.getsize
                )

            self.root.after(
                0,
                lambda t=title:
                self.update_youtube_status(
                    f"Downloaded: {t}"
                )
            )

            # ------------------------------------------------
            # Convert YouTube audio to WAV.
            # ------------------------------------------------

            wav_file, temp_dir = (
                convert_to_wav(
                    downloaded_file
                )
            )

            self.root.after(
                0,
                lambda:
                self.update_youtube_status(
                    "Analyzing BPM and rhythm..."
                )
            )

            samples, sample_rate = (
                read_wav(
                    wav_file
                )
            )

            song_length = (
                len(samples)
                / sample_rate
            )

            notes, bpm = (
                generate_chart(
                    samples,
                    sample_rate,
                    self.difficulty
                )
            )

            if not notes:

                raise RuntimeError(
                    "No rhythm could be detected "
                    "from this YouTube video."
                )

            self.root.after(
                0,
                lambda:
                self.finish_youtube_load(
                    downloaded_file,
                    download_dir,
                    wav_file,
                    temp_dir,
                    song_length,
                    notes,
                    bpm,
                    title
                )
            )

        except Exception as exc:

            if download_dir:

                # The directory is only deleted on error.
                try:
                    shutil.rmtree(
                        download_dir,
                        ignore_errors=True
                    )
                except Exception:
                    pass

            self.root.after(
                0,
                lambda e=exc:
                self.youtube_error(e)
            )

    # ========================================================
    # YOUTUBE SUCCESS
    # ========================================================

    def finish_youtube_load(
        self,
        downloaded_file,
        download_dir,
        wav_file,
        temp_dir,
        song_length,
        notes,
        bpm,
        title
    ):

        self.youtube_temp_dir = (
            download_dir
        )

        self.audio_file = (
            downloaded_file
        )

        self.wav_file = (
            wav_file
        )

        self.temp_audio_dir = (
            temp_dir
        )

        self.song_length = (
            song_length
        )

        self.notes = notes

        self.bpm = bpm

        self.start_game()

    # ========================================================
    # GENERIC LOADING
    # ========================================================

    def begin_loading(
        self,
        title_text,
        subtitle
    ):

        self.state = "loading"

        self.clear()
        self.background()

        self.canvas.create_text(
            self.width / 2,
            self.height / 2 - 35,
            text=title_text,
            fill="white",
            font=(
                "Arial",
                28,
                "bold"
            )
        )

        self.canvas.create_text(
            self.width / 2,
            self.height / 2 + 15,
            text=subtitle,
            fill="#ff5555",
            font=(
                "Arial",
                14
            )
        )

        self.root.update_idletasks()

    # ========================================================
    # FINISH LOCAL SONG
    # ========================================================

    def finish_song_load(
        self,
        wav_file,
        temp_dir,
        song_length,
        notes,
        bpm
    ):

        self.wav_file = wav_file

        self.temp_audio_dir = temp_dir

        self.song_length = song_length

        self.notes = notes

        self.bpm = bpm

        self.start_game()

    # ========================================================
    # LOADING ERROR
    # ========================================================

    def song_load_error(
        self,
        exc
    ):

        self.state = "menu"

        messagebox.showerror(
            "ManiaTK",
            str(exc)
        )

        self.show_menu()

    def youtube_error(
        self,
        exc
    ):

        self.state = "menu"

        messagebox.showerror(
            "YouTube Import Failed",
            str(exc)
        )

        self.show_menu()

    # ========================================================
    # START GAME
    # ========================================================

    def start_game(self):

        self.score = 0
        self.combo = 0
        self.max_combo = 0

        self.perfects = 0
        self.greats = 0
        self.goods = 0
        self.misses = 0
        self.no_notes = 0

        for note in self.notes:

            note["hit"] = False
            note["judgement"] = None

        self.judgement_text = ""

        self.judgement_timer = 0

        self.song_position = 0

        self.state = "playing"

        self.audio.play(
            self.wav_file
        )

        self.draw_game()

    # ========================================================
    # INPUT
    # ========================================================

    def on_key_press(
        self,
        event
    ):

        key = event.keysym.lower()

        if key == "escape":
            return

        if key in KEYS:

            if self.key_down[key]:
                return

            self.key_down[key] = True

            self.key_glow[key] = 1.0

            if self.state == "playing":

                lane = KEYS.index(
                    key
                )

                self.hit_lane(
                    lane
                )

    def on_key_release(
        self,
        event
    ):

        key = event.keysym.lower()

        if key in KEYS:

            self.key_down[key] = False

    # ========================================================
    # HIT DETECTION
    # ========================================================

    def hit_lane(
        self,
        lane
    ):

        position = (
            self.audio.get_position()
        )

        closest = None

        closest_difference = (
            float("inf")
        )

        for note in self.notes:

            if note["hit"]:
                continue

            if note["lane"] != lane:
                continue

            difference = abs(
                note["time"]
                - position
            )

            if (
                difference
                < closest_difference
            ):

                closest_difference = (
                    difference
                )

                closest = note

        if closest is None:

            self.judgement(
                "NO NOTE"
            )

            self.no_notes += 1

            return

        difference_ms = (
            closest_difference
            * 1000
        )

        if difference_ms <= 25:

            result = "PERFECT"
            points = 300

            self.perfects += 1

        elif difference_ms <= 60:

            result = "GREAT"
            points = 200

            self.greats += 1

        elif difference_ms <= 100:

            result = "GOOD"
            points = 100

            self.goods += 1

        elif difference_ms <= 150:

            result = "GOOD"
            points = 50

            self.goods += 1

        else:

            return

        closest["hit"] = True

        closest["judgement"] = (
            result
        )

        self.combo += 1

        self.max_combo = max(
            self.max_combo,
            self.combo
        )

        multiplier = min(
            4,
            1 + self.combo // 10
        )

        self.score += (
            points
            * multiplier
        )

        self.hit_flash[lane] = 1.0

        self.judgement(
            result
        )

    # ========================================================
    # JUDGEMENT
    # ========================================================

    def judgement(
        self,
        text
    ):

        self.judgement_text = text

        self.judgement_timer = (
            0.65
        )

    # ========================================================
    # MISSES
    # ========================================================

    def update_misses(self):

        position = (
            self.audio.get_position()
        )

        for note in self.notes:

            if note["hit"]:
                continue

            if (
                position
                - note["time"]
                > 0.150
            ):

                note["hit"] = True

                note["judgement"] = (
                    "MISS"
                )

                self.misses += 1

                self.combo = 0

                self.judgement(
                    "MISS"
                )

    # ========================================================
    # GAME DRAW
    # ========================================================

    def draw_game(self):

        self.clear()

        self.background()

        w = self.width
        h = self.height

        field_width = 440

        left = (
            w / 2
            - field_width / 2
        )

        right = (
            w / 2
            + field_width / 2
        )

        top = 80

        bottom = (
            h - 100
        )

        lane_width = (
            field_width / 4
        )

        # ----------------------------------------------------
        # PLAYFIELD
        # ----------------------------------------------------

        self.canvas.create_rectangle(
            left,
            top,
            right,
            bottom,
            fill="#110000",
            outline="#ff2020",
            width=3
        )

        # ----------------------------------------------------
        # LANES
        # ----------------------------------------------------

        for lane in range(5):

            x = (
                left
                + lane
                * lane_width
            )

            self.canvas.create_line(
                x,
                top,
                x,
                bottom,
                fill="#440000",
                width=2
            )

        # ----------------------------------------------------
        # HIT LINE
        # ----------------------------------------------------

        hit_y = (
            bottom - 80
        )

        self.canvas.create_line(
            left,
            hit_y,
            right,
            hit_y,
            fill="#ff3030",
            width=5
        )

        # ----------------------------------------------------
        # KEY BOXES
        # ----------------------------------------------------

        for lane, key in enumerate(
            KEYS
        ):

            x1 = (
                left
                + lane
                * lane_width
                + 5
            )

            x2 = (
                left
                + (lane + 1)
                * lane_width
                - 5
            )

            glow = (
                self.key_glow[key]
            )

            if glow > 0:
                fill = "#ff3030"
            else:
                fill = "#210000"

            self.canvas.create_rectangle(
                x1,
                hit_y + 12,
                x2,
                hit_y + 65,
                fill=fill,
                outline="#ff4040",
                width=2
            )

            self.canvas.create_text(
                (x1 + x2) / 2,
                hit_y + 38,
                text=KEY_LABELS[key],
                fill="white",
                font=(
                    "Arial",
                    19,
                    "bold"
                )
            )

        # ----------------------------------------------------
        # NOTES
        # ----------------------------------------------------

        position = (
            self.song_position
        )

        for note in self.notes:

            if note["hit"]:
                continue

            delta = (
                note["time"]
                - position
            )

            y = (
                hit_y
                - delta
                * self.note_speed
            )

            if y < top - 80:
                continue

            if y > bottom + 80:
                continue

            lane = note["lane"]

            cx = (
                left
                + lane
                * lane_width
                + lane_width / 2
            )

            self.draw_arrow(
                cx,
                y,
                lane
            )

        # ----------------------------------------------------
        # HUD
        # ----------------------------------------------------

        self.canvas.create_text(
            30,
            30,
            anchor="w",
            text=(
                f"SCORE  "
                f"{self.score:,}"
            ),
            fill="white",
            font=(
                "Arial",
                17,
                "bold"
            )
        )

        self.canvas.create_text(
            w - 30,
            30,
            anchor="e",
            text=(
                f"COMBO  "
                f"{self.combo}x"
            ),
            fill="#ff5555",
            font=(
                "Arial",
                17,
                "bold"
            )
        )

        self.canvas.create_text(
            w / 2,
            30,
            text=(
                f"{self.bpm:.0f} BPM"
            ),
            fill="#aaaaaa",
            font=(
                "Arial",
                12,
                "bold"
            )
        )

        if self.judgement_timer > 0:

            self.canvas.create_text(
                w / 2,
                h - 42,
                text=(
                    self.judgement_text
                ),
                fill=(
                    "#ffffff"
                    if self.judgement_text
                    != "MISS"
                    else "#ff3030"
                ),
                font=(
                    "Arial",
                    22,
                    "bold"
                )
            )

    # ========================================================
    # ARROWS
    # ========================================================

    def draw_arrow(
        self,
        x,
        y,
        lane
    ):

        size = 25

        if lane == 0:

            points = [
                x - size,
                y,

                x,
                y - size,

                x,
                y - size * 0.45,

                x + size,
                y - size * 0.45,

                x + size,
                y + size * 0.45,

                x,
                y + size * 0.45,

                x,
                y + size,
            ]

        elif lane == 1:

            points = [
                x,
                y - size,

                x + size,
                y,

                x + size * 0.45,
                y,

                x + size * 0.45,
                y + size,

                x - size * 0.45,
                y + size,

                x - size * 0.45,
                y,

                x - size,
                y,
            ]

        elif lane == 2:

            points = [
                x,
                y + size,

                x - size,
                y,

                x - size * 0.45,
                y,

                x - size * 0.45,
                y - size,

                x + size * 0.45,
                y - size,

                x + size * 0.45,
                y,

                x + size,
                y,
            ]

        else:

            points = [
                x + size,
                y,

                x,
                y - size,

                x,
                y - size * 0.45,

                x - size,
                y - size * 0.45,

                x - size,
                y + size * 0.45,

                x,
                y + size * 0.45,

                x,
                y + size,
            ]

        self.canvas.create_polygon(
            points,
            fill="#ff3030",
            outline="white",
            width=2
        )

    # ========================================================
    # DIFFICULTY
    # ========================================================

    def show_difficulty(self):

        self.state = "difficulty"

        self.clear()
        self.background()

        self.title(
            "SELECT DIFFICULTY",
            65,
            36
        )

        names = list(
            DIFFICULTIES.keys()
        )

        start_y = 125

        for i, name in enumerate(
            names
        ):

            y1 = (
                start_y
                + i * 78
            )

            y2 = y1 + 58

            self.button(
                300,
                y1,
                800,
                y2,
                name,
                lambda n=name:
                self.set_difficulty(n),
                font=(
                    "Arial",
                    14,
                    "bold"
                )
            )

        self.canvas.create_text(
            self.width / 2,
            615,
            text=(
                DIFFICULTY_DESCRIPTIONS[
                    self.difficulty
                ]
            ),
            fill="#aaaaaa",
            font=(
                "Arial",
                12
            )
        )

        self.button(
            430,
            665,
            670,
            715,
            "BACK",
            self.show_menu,
            font=(
                "Arial",
                13,
                "bold"
            )
        )

    def set_difficulty(
        self,
        name
    ):

        self.difficulty = name

        if (
            self.audio_file
            and self.wav_file
            and os.path.exists(
                self.wav_file
            )
        ):

            try:

                samples, sample_rate = (
                    read_wav(
                        self.wav_file
                    )
                )

                (
                    self.notes,
                    self.bpm
                ) = generate_chart(
                    samples,
                    sample_rate,
                    self.difficulty
                )

            except Exception:
                pass

        self.show_menu()

    # ========================================================
    # SPEED
    # ========================================================

    def show_speed(self):

        self.state = "speed"

        self.clear()
        self.background()

        self.title(
            "NOTE SPEED",
            90,
            40
        )

        speeds = [
            ("SLOW", 250),
            ("NORMAL", 420),
            ("FAST", 600),
            ("INSANE", 800),
        ]

        for i, (
            name,
            value
        ) in enumerate(speeds):

            y = (
                180
                + i * 85
            )

            self.button(
                350,
                y,
                750,
                y + 58,
                f"{name}  —  {value}",
                lambda v=value:
                self.set_speed(v)
            )

        self.canvas.create_text(
            self.width / 2,
            545,
            text=(
                f"Current speed: "
                f"{self.note_speed}"
            ),
            fill="#ff5555",
            font=(
                "Arial",
                16,
                "bold"
            )
        )

        self.button(
            430,
            620,
            670,
            675,
            "BACK",
            self.show_menu
        )

    def set_speed(
        self,
        speed
    ):

        self.note_speed = int(
            np.clip(
                speed,
                MIN_NOTE_SPEED,
                MAX_NOTE_SPEED
            )
        )

        self.show_menu()

    # ========================================================
    # KEY SETTINGS
    # ========================================================

    def key_settings(self):

        self.state = "keys"

        self.clear()
        self.background()

        self.title(
            "KEY SETTINGS",
            80,
            38
        )

        for i, key in enumerate(
            KEYS
        ):

            y = (
                180
                + i * 90
            )

            self.canvas.create_rectangle(
                360,
                y,
                740,
                y + 60,
                fill="#150000",
                outline="#ff2020",
                width=2
            )

            self.canvas.create_text(
                450,
                y + 30,
                text=(
                    f"LANE {i + 1}"
                ),
                fill="#aaaaaa",
                font=(
                    "Arial",
                    13,
                    "bold"
                )
            )

            self.canvas.create_text(
                620,
                y + 30,
                text=KEY_LABELS[key],
                fill="white",
                font=(
                    "Arial",
                    22,
                    "bold"
                )
            )

        self.canvas.create_text(
            self.width / 2,
            555,
            text="Default keys: D F J K",
            fill="#777777",
            font=(
                "Arial",
                12
            )
        )

        self.button(
            350,
            600,
            750,
            655,
            "RESET D F J K",
            self.reset_keys
        )

        self.button(
            430,
            680,
            670,
            730,
            "BACK",
            self.show_menu
        )

    def reset_keys(self):

        self.show_menu()

    # ========================================================
    # TUTORIAL
    # ========================================================

    def show_tutorial(self):

        self.state = "tutorial"

        self.clear()
        self.background()

        self.title(
            "HOW TO PLAY",
            80,
            40
        )

        lines = [
            "ManiaTK is a 4-key rhythm game.",
            "",
            "Press D / F / J / K when the arrows reach",
            "the red hit line.",
            "",
            "PERFECT  = within 25 ms",
            "GREAT    = within 60 ms",
            "GOOD     = within 100 ms",
            "MISS     = more than 150 ms late",
            "",
            "Keep your combo going for a higher score.",
            "",
            "You can also paste a YouTube link from the menu.",
            "",
            "Press ESC during gameplay to pause.",
        ]

        y = 145

        for line in lines:

            self.canvas.create_text(
                self.width / 2,
                y,
                text=line,
                fill=(
                    "white"
                    if line
                    else "#555555"
                ),
                font=(
                    "Arial",
                    15,
                    "bold"
                    if line
                    else "normal"
                )
            )

            y += 30

        self.button(
            430,
            650,
            670,
            705,
            "BACK",
            self.show_menu
        )

    # ========================================================
    # PAUSE
    # ========================================================

    def escape(
        self,
        event=None
    ):

        if self.state == "playing":

            self.pause_game()

        elif self.state == "paused":

            self.resume_game()

    def pause_game(self):

        self.state = "paused"

        self.audio.pause()

        self.clear()
        self.background()

        self.title(
            "PAUSED",
            160,
            50
        )

        self.button(
            380,
            270,
            720,
            330,
            "RESUME",
            self.resume_game
        )

        self.button(
            380,
            350,
            720,
            410,
            "QUIT BEATMAP",
            self.quit_beatmap
        )

        self.button(
            380,
            430,
            720,
            490,
            "EXIT GAME",
            self.close
        )

    def resume_game(self):

        self.state = "playing"

        self.audio.resume()

        self.draw_game()

    def quit_beatmap(self):

        self.audio.stop()

        self.state = "menu"

        self.show_menu()

    # ========================================================
    # RESULTS
    # ========================================================

    def show_results(self):

        self.state = "results"

        self.audio.stop()

        self.clear()
        self.background()

        self.title(
            "RESULTS",
            80,
            45
        )

        total = (
            self.perfects
            + self.greats
            + self.goods
            + self.misses
        )

        if total:

            accuracy = (
                (
                    self.perfects * 1.0
                    + self.greats * 0.8
                    + self.goods * 0.5
                )
                / total
                * 100
            )

        else:

            accuracy = 0

        results = [
            f"SCORE     {self.score:,}",
            f"ACCURACY  {accuracy:.2f}%",
            f"MAX COMBO {self.max_combo}x",
            "",
            f"PERFECT   {self.perfects}",
            f"GREAT     {self.greats}",
            f"GOOD      {self.goods}",
            f"MISS      {self.misses}",
            f"NO NOTE   {self.no_notes}",
        ]

        y = 175

        for line in results:

            self.canvas.create_text(
                self.width / 2,
                y,
                text=line,
                fill=(
                    "#ff5555"
                    if line.startswith(
                        (
                            "SCORE",
                            "ACCURACY"
                        )
                    )
                    else "white"
                ),
                font=(
                    "Arial",
                    18,
                    "bold"
                )
            )

            y += 42

        self.button(
            400,
            610,
            700,
            665,
            "BACK TO MENU",
            self.show_menu
        )

    # ========================================================
    # MAIN LOOP
    # ========================================================

    def loop(self):

        now = (
            time.perf_counter()
        )

        dt = (
            now
            - self.last_frame
        )

        self.last_frame = now

        dt = min(
            dt,
            0.1
        )

        for particle in self.particles:

            particle.update(
                self.width,
                self.height,
                dt
            )

        for key in KEYS:

            self.key_glow[key] = max(
                0,
                self.key_glow[key]
                - dt * 5
            )

        for i in range(4):

            self.hit_flash[i] = max(
                0,
                self.hit_flash[i]
                - dt * 4
            )

        if self.judgement_timer > 0:

            self.judgement_timer -= dt

        if self.state == "playing":

            self.song_position = (
                self.audio.get_position()
            )

            self.update_misses()

            self.draw_game()

            if (
                self.song_length > 0
                and self.song_position
                >= self.song_length + 0.5
            ):

                self.show_results()

        elif self.state == "menu":

            # Only redraw the menu periodically.
            # This keeps the particles moving.
            self.show_menu()

        elif self.state == "loading":

            # Keep particles moving while loading.
            pass

        self.root.after(
            16,
            self.loop
        )

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self):

        try:
            self.audio.close()
        except Exception:
            pass

        if self.temp_audio_dir:

            try:

                shutil.rmtree(
                    self.temp_audio_dir,
                    ignore_errors=True
                )

            except Exception:
                pass

        if self.youtube_temp_dir:

            try:

                shutil.rmtree(
                    self.youtube_temp_dir,
                    ignore_errors=True
                )

            except Exception:
                pass

        self.root.destroy()


# ============================================================
# MAIN
# ============================================================

def main():

    root = tk.Tk()

    app = ManiaTK(
        root
    )

    root.mainloop()


if __name__ == "__main__":
    main()
