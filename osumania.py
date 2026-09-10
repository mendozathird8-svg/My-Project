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


APP_NAME = "ManiaTK"
GAME_VERSION = "1.0.3"

DEFAULT_NOTE_SPEED = 420
MIN_NOTE_SPEED = 180
MAX_NOTE_SPEED = 900

DEFAULT_KEYS = ["d", "f", "j", "k"]

FFMPEG_NAMES = [
    "ffmpeg.exe",
    "ffmpeg",
]

FFPLAY_NAMES = [
    "ffplay.exe",
    "ffplay",
]

GITHUB_VERSION_URL = (
    "https://raw.githubusercontent.com/"
    "mendozathird8-svg/My-Project/main/version.txt"
)


DIFFICULTIES = {
    "EASY": {
        "threshold": 78,
        "subdivision": 1,
        "min_spacing": 0.50,
        "chords": False,
        "jumps": False,
    },
    "NORMAL": {
        "threshold": 64,
        "subdivision": 1,
        "min_spacing": 0.25,
        "chords": True,
        "jumps": False,
    },
    "HARD": {
        "threshold": 52,
        "subdivision": 2,
        "min_spacing": 0.125,
        "chords": True,
        "jumps": True,
    },
    "INSANE": {
        "threshold": 42,
        "subdivision": 2,
        "min_spacing": 0.125,
        "chords": True,
        "jumps": True,
    },
    "EXTREME": {
        "threshold": 31,
        "subdivision": 4,
        "min_spacing": 0.0625,
        "chords": True,
        "jumps": True,
    },
    "OSU PRO": {
        "threshold": 20,
        "subdivision": 4,
        "min_spacing": 0.0625,
        "chords": True,
        "jumps": True,
    },
}


class AudioPlayer:
    def __init__(self):
        self.process = None
        self.position = 0.0
        self.started_at = None
        self.paused = False
        self.file = None

    def find_program(self, names):
        locations = []

        here = os.path.dirname(os.path.abspath(sys.argv[0]))
        locations.append(here)

        path_value = os.environ.get("PATH", "")
        locations.extend(path_value.split(os.pathsep))

        for folder in locations:
            if not folder:
                continue

            for name in names:
                path = os.path.join(folder, name)

                if os.path.isfile(path):
                    return path

        return None

    def play(self, filename, start_position=0.0):
        self.stop()

        ffplay = self.find_program(FFPLAY_NAMES)

        if not ffplay:
            raise RuntimeError(
                "FFplay was not found.\n\n"
                "Install FFmpeg and make sure ffplay.exe is available."
            )

        self.file = filename
        self.position = max(0.0, float(start_position))
        self.paused = False
        self.started_at = time.perf_counter()

        command = [
            ffplay,
            "-nodisp",
            "-autoexit",
            "-loglevel",
            "quiet",
            "-ss",
            str(self.position),
            "-i",
            filename,
        ]

        self.process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW
            if os.name == "nt"
            else 0,
        )

        self.started_at = time.perf_counter()

    def get_position(self):
        if self.paused:
            return self.position

        if self.started_at is None:
            return self.position

        if self.process is not None:
            if self.process.poll() is not None:
                return self.position

        return self.position + (
            time.perf_counter() - self.started_at
        )

    def pause(self):
        if self.process is None:
            return

        if self.paused:
            return

        self.position = self.get_position()
        self.paused = True

        try:
            self.process.terminate()
            self.process.wait(timeout=0.5)
        except Exception:
            try:
                self.process.kill()
            except Exception:
                pass

        self.process = None

    def resume(self):
        if not self.paused or not self.file:
            return

        self.play(self.file, self.position)

    def stop(self):
        if self.process is not None:
            try:
                self.process.terminate()
                self.process.wait(timeout=0.5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass

        self.process = None
        self.started_at = None
        self.position = 0.0
        self.paused = False


class ManiaTK:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("1000x700")
        self.root.minsize(900, 620)
        self.root.configure(bg="#080000")

        self.canvas = tk.Canvas(
            self.root,
            bg="#080000",
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self.audio = AudioPlayer()

        self.screen = "menu"

        self.song_file = None
        self.song_name = ""
        self.wav_file = None

        self.samples = None
        self.sample_rate = 44100
        self.duration = 0.0

        self.bpm = 120.0
        self.beat_interval = 0.5
        self.beat_offset = 0.0

        self.notes = []
        self.active_notes = []

        self.difficulty = "NORMAL"
        self.note_speed = DEFAULT_NOTE_SPEED

        self.keys = DEFAULT_KEYS.copy()

        self.score = 0
        self.combo = 0
        self.max_combo = 0
        self.hits = 0
        self.misses = 0
        self.total_judged = 0

        self.hit_effects = []
        self.key_glow = [0, 0, 0, 0]

        self.song_start_time = 0.0
        self.paused_position = 0.0
        self.game_finished = False

        self.menu_buttons = []
        self.particles = []

        self.dragging_key = None

        self.youtube_window = None
        self.youtube_status = None

        self.analysis_running = False

        self.init_particles()

        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.show_menu()
        self.game_loop()

    # =========================================================
    # BASIC UI
    # =========================================================

    def clear(self):
        self.canvas.delete("all")
        self.menu_buttons = []

    def center(self):
        return (
            self.canvas.winfo_width() / 2,
            self.canvas.winfo_height() / 2,
        )

    def text(
        self,
        x,
        y,
        value,
        size=20,
        fill="white",
        anchor="center",
        weight="bold",
    ):
        return self.canvas.create_text(
            x,
            y,
            text=value,
            fill=fill,
            font=("Arial", size, weight),
            anchor=anchor,
        )

    def button(
        self,
        x1,
        y1,
        x2,
        y2,
        label,
        command,
        font=("Arial", 15, "bold"),
    ):
        tag = f"button_{len(self.menu_buttons)}"

        rect = self.canvas.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            fill="#210000",
            outline="#ff2020",
            width=2,
            tags=tag,
        )

        text_id = self.canvas.create_text(
            (x1 + x2) / 2,
            (y1 + y2) / 2,
            text=label,
            fill="white",
            font=font,
        )

        self.canvas.tag_bind(
            tag,
            "<Button-1>",
            lambda e: command(),
        )

        self.canvas.tag_bind(
            tag,
            "<Enter>",
            lambda e, r=rect: self.canvas.itemconfigure(
                r,
                fill="#4a0000",
            ),
        )

        self.canvas.tag_bind(
            tag,
            "<Leave>",
            lambda e, r=rect: self.canvas.itemconfigure(
                r,
                fill="#210000",
            ),
        )

        self.canvas.tag_bind(
            text_id,
            "<Button-1>",
            lambda e: command(),
        )

        self.canvas.tag_bind(
            text_id,
            "<Enter>",
            lambda e, r=rect: self.canvas.itemconfigure(
                r,
                fill="#4a0000",
            ),
        )

        self.canvas.tag_bind(
            text_id,
            "<Leave>",
            lambda e, r=rect: self.canvas.itemconfigure(
                r,
                fill="#210000",
            ),
        )

        self.menu_buttons.append(tag)

    # =========================================================
    # PARTICLES
    # =========================================================

    def init_particles(self):
        self.particles = []

        for _ in range(70):
            self.particles.append(
                {
                    "x": random.random(),
                    "y": random.random(),
                    "speed": random.uniform(0.0005, 0.002),
                    "size": random.uniform(1, 4),
                }
            )

    def draw_background(self):
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())

        self.canvas.create_rectangle(
            0,
            0,
            width,
            height,
            fill="#080000",
            outline="",
        )

        for particle in self.particles:
            particle["y"] += particle["speed"]

            if particle["y"] > 1:
                particle["y"] = 0
                particle["x"] = random.random()

            x = particle["x"] * width
            y = particle["y"] * height
            size = particle["size"]

            self.canvas.create_oval(
                x - size,
                y - size,
                x + size,
                y + size,
                fill="white",
                outline="",
            )

    # =========================================================
    # MENU
    # =========================================================

    def show_menu(self):
        self.screen = "menu"
        self.audio.stop()

        self.clear()

        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()

        cx = width / 2

        self.text(
            cx,
            75,
            "MANIATK",
            48,
        )

        self.text(
            cx,
            120,
            "4K rhythm game",
            16,
            "#ffaaaa",
        )

        self.button(
            cx - 190,
            175,
            cx + 190,
            225,
            "IMPORT SONG / VIDEO",
            self.import_song,
        )

        self.button(
            cx - 190,
            240,
            cx + 190,
            290,
            "PASTE YOUTUBE LINK",
            self.import_youtube,
        )

        self.button(
            cx - 190,
            305,
            cx + 190,
            355,
            "DIFFICULTY",
            self.show_difficulty,
        )

        self.button(
            cx - 190,
            370,
            cx + 190,
            420,
            f"NOTE SPEED: {self.note_speed}",
            self.show_speed,
        )

        self.button(
            cx - 190,
            435,
            cx + 190,
            485,
            "KEY SETTINGS",
            self.show_keys,
        )

        self.button(
            cx - 190,
            500,
            cx + 190,
            550,
            "TUTORIAL",
            self.show_tutorial,
        )

        self.text(
            cx,
            height - 35,
            f"ManiaTK {GAME_VERSION}",
            12,
            "#888888",
        )

    # =========================================================
    # SONG IMPORT
    # =========================================================

    def import_song(self):
        filename = filedialog.askopenfilename(
            title="Select a song or video",
            filetypes=[
                (
                    "Media files",
                    "*.mp3 *.wav *.ogg *.m4a *.flac "
                    "*.wma *.mp4 *.mkv *.avi",
                ),
                ("All files", "*.*"),
            ],
        )

        if not filename:
            return

        self.song_file = filename
        self.song_name = os.path.basename(filename)

        self.start_analysis()

    def find_ffmpeg(self):
        return self.audio.find_program(FFMPEG_NAMES)

    def convert_to_wav(self, filename):
        ffmpeg = self.find_ffmpeg()

        if not ffmpeg:
            raise RuntimeError(
                "FFmpeg was not found.\n\n"
                "Install FFmpeg and make sure ffmpeg.exe is available."
            )

        temp_dir = tempfile.mkdtemp(prefix="maniatk_")

        output = os.path.join(
            temp_dir,
            "audio.wav",
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
            creationflags=subprocess.CREATE_NO_WINDOW
            if os.name == "nt"
            else 0,
        )

        if result.returncode != 0 or not os.path.isfile(output):
            error = result.stderr.decode(
                errors="ignore"
            )

            raise RuntimeError(
                "FFmpeg could not convert the file.\n\n"
                + error[-1500:]
            )

        return output

    def read_wav(self, filename):
        with wave.open(filename, "rb") as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            frames = wav.getnframes()

            raw = wav.readframes(frames)

        if sample_width == 2:
            data = np.frombuffer(
                raw,
                dtype=np.int16,
            ).astype(np.float32)

            data /= 32768.0

        elif sample_width == 1:
            data = np.frombuffer(
                raw,
                dtype=np.uint8,
            ).astype(np.float32)

            data = (data - 128.0) / 128.0

        elif sample_width == 4:
            data = np.frombuffer(
                raw,
                dtype=np.int32,
            ).astype(np.float32)

            data /= 2147483648.0

        else:
            raise RuntimeError(
                f"Unsupported WAV sample width: {sample_width}"
            )

        if channels > 1:
            data = data.reshape(-1, channels)
            data = np.mean(data, axis=1)

        return data, sample_rate

    # =========================================================
    # ANALYSIS
    # =========================================================

    def start_analysis(self):
        if self.analysis_running:
            return

        self.analysis_running = True
        self.screen = "analysis"

        self.clear()

        cx, cy = self.center()

        self.text(
            cx,
            cy - 50,
            "ANALYZING RHYTHM...",
            32,
        )

        self.text(
            cx,
            cy + 5,
            "Finding BPM and beat phase",
            17,
            "#ffaaaa",
        )

        self.text(
            cx,
            cy + 45,
            "Notes will be locked to the detected beat grid.",
            14,
            "#aaaaaa",
        )

        threading.Thread(
            target=self.analysis_worker,
            daemon=True,
        ).start()

    def analysis_worker(self):
        try:
            self.wav_file = self.convert_to_wav(
                self.song_file
            )

            samples, sample_rate = self.read_wav(
                self.wav_file
            )

            self.samples = samples
            self.sample_rate = sample_rate
            self.duration = len(samples) / sample_rate

            if self.duration < 1.0:
                raise RuntimeError(
                    "The song is too short."
                )

            envelope, frame_time = self.make_onset_envelope(
                samples,
                sample_rate,
            )

            bpm = self.estimate_bpm(
                envelope,
                frame_time,
            )

            bpm, beat = self.optimize_beat_interval(
                envelope,
                frame_time,
                bpm,
            )

            offset = self.find_beat_phase(
                envelope,
                frame_time,
                beat,
            )

            self.bpm = bpm
            self.beat_interval = beat
            self.beat_offset = offset

            self.notes = self.generate_rhythm_locked_chart(
                envelope,
                frame_time,
                bpm,
                beat,
                offset,
                self.difficulty,
            )

            self.root.after(
                0,
                self.analysis_finished,
            )

        except Exception as exc:
            self.root.after(
                0,
                lambda e=exc: self.analysis_failed(e),
            )

    # =========================================================
    # ONSET ENVELOPE
    # =========================================================

    def make_onset_envelope(
        self,
        samples,
        sample_rate,
    ):
        frame_size = 2048
        hop = 256

        if len(samples) < frame_size:
            samples = np.pad(
                samples,
                (0, frame_size - len(samples)),
            )

        window = np.hanning(frame_size)

        count = 1 + (
            (len(samples) - frame_size) // hop
        )

        envelope = np.zeros(count)

        previous = None

        for i in range(count):
            start = i * hop

            frame = samples[
                start:start + frame_size
            ]

            if len(frame) < frame_size:
                frame = np.pad(
                    frame,
                    (0, frame_size - len(frame)),
                )

            frame = frame * window

            spectrum = np.abs(
                np.fft.rfft(frame)
            )

            spectrum = np.log1p(
                spectrum
            )

            if previous is not None:
                diff = spectrum - previous
                diff[diff < 0] = 0

                value = float(
                    np.sum(diff)
                )
            else:
                value = 0.0

            previous = spectrum

            envelope[i] = value

        envelope = self.smooth_array(
            envelope,
            3,
        )

        if np.max(envelope) > 0:
            envelope /= np.max(envelope)

        return envelope, hop / sample_rate

    def smooth_array(self, values, radius):
        if radius <= 0:
            return values

        kernel = np.ones(
            radius * 2 + 1
        ) / (
            radius * 2 + 1
        )

        return np.convolve(
            values,
            kernel,
            mode="same",
        )

    # =========================================================
    # BPM DETECTION
    # =========================================================

    def estimate_bpm(
        self,
        envelope,
        frame_time,
    ):
        if len(envelope) < 10:
            return 120.0

        envelope = envelope - np.mean(envelope)

        if np.max(np.abs(envelope)) <= 0:
            return 120.0

        min_bpm = 65.0
        max_bpm = 190.0

        min_lag = int(
            (60.0 / max_bpm) / frame_time
        )

        max_lag = int(
            (60.0 / min_bpm) / frame_time
        )

        max_lag = min(
            max_lag,
            len(envelope) - 1,
        )

        if min_lag >= max_lag:
            return 120.0

        correlations = []

        for lag in range(
            min_lag,
            max_lag + 1,
        ):
            a = envelope[:-lag]
            b = envelope[lag:]

            denominator = (
                np.linalg.norm(a)
                * np.linalg.norm(b)
            )

            if denominator <= 0:
                score = 0.0
            else:
                score = float(
                    np.dot(a, b)
                    / denominator
                )

            correlations.append(
                score
            )

        correlations = np.asarray(
            correlations
        )

        best_index = int(
            np.argmax(correlations)
        )

        lag = min_lag + best_index

        bpm = 60.0 / (
            lag * frame_time
        )

        return float(
            np.clip(
                bpm,
                min_bpm,
                max_bpm,
            )
        )

    def optimize_beat_interval(
        self,
        envelope,
        frame_time,
        estimated_bpm,
    ):
        candidates = []

        base_values = [
            estimated_bpm / 2.0,
            estimated_bpm,
            estimated_bpm * 2.0,
        ]

        for base in base_values:
            if base < 65 or base > 190:
                continue

            for delta in np.linspace(
                -0.03,
                0.03,
                13,
            ):
                bpm = base * (1.0 + delta)

                if 65 <= bpm <= 190:
                    candidates.append(bpm)

        if not candidates:
            candidates = [120.0]

        best_bpm = 120.0
        best_score = -999999.0

        for bpm in candidates:
            beat = 60.0 / bpm

            score = self.beat_grid_quality(
                envelope,
                frame_time,
                beat,
            )

            if score > best_score:
                best_score = score
                best_bpm = bpm

        return (
            float(best_bpm),
            60.0 / float(best_bpm),
        )

    def beat_grid_quality(
        self,
        envelope,
        frame_time,
        beat,
    ):
        if beat <= 0:
            return -999999

        max_time = len(envelope) * frame_time

        if max_time < beat * 4:
            return -999999

        phases = np.linspace(
            0,
            beat,
            25,
            endpoint=False,
        )

        best = -999999.0

        for phase in phases:
            times = np.arange(
                phase,
                max_time,
                beat,
            )

            if len(times) < 4:
                continue

            indices = np.rint(
                times / frame_time
            ).astype(int)

            indices = indices[
                (indices >= 0)
                & (indices < len(envelope))
            ]

            if len(indices) < 4:
                continue

            values = envelope[
                indices
            ]

            mean = float(
                np.mean(values)
            )

            deviation = float(
                np.std(values)
            )

            # We want strong energy at the
            # grid positions, but not a grid
            # that is only occasionally huge.
            score = (
                mean * 2.0
                + deviation * 0.35
            )

            if score > best:
                best = score

        return best

    # =========================================================
    # BEAT PHASE
    # =========================================================

    def find_beat_phase(
        self,
        envelope,
        frame_time,
        beat,
    ):
        max_time = len(envelope) * frame_time

        best_phase = 0.0
        best_score = -999999.0

        # Fine phase search.
        # This is the important part that keeps
        # the generated chart synchronized with
        # the actual rhythm instead of assuming
        # that beat 1 starts at exactly 0.0.
        steps = 120

        for i in range(steps):
            phase = (
                beat * i / steps
            )

            times = np.arange(
                phase,
                max_time,
                beat,
            )

            if len(times) < 4:
                continue

            indices = np.rint(
                times / frame_time
            ).astype(int)

            indices = indices[
                (indices >= 0)
                & (indices < len(envelope))
            ]

            if len(indices) < 4:
                continue

            values = envelope[
                indices
            ]

            # Also look slightly around the
            # exact beat because the onset can
            # happen a few milliseconds before
            # or after the detected beat.
            expanded = []

            radius = max(
                1,
                int(
                    0.035
                    / frame_time
                ),
            )

            for index in indices:
                lo = max(
                    0,
                    index - radius,
                )

                hi = min(
                    len(envelope),
                    index + radius + 1,
                )

                expanded.append(
                    float(
                        np.max(
                            envelope[lo:hi]
                        )
                    )
                )

            expanded = np.asarray(
                expanded
            )

            score = (
                float(np.mean(values))
                * 0.7
                + float(np.mean(expanded))
                * 1.3
            )

            if score > best_score:
                best_score = score
                best_phase = phase

        return float(best_phase)

    # =========================================================
    # RHYTHM-LOCKED CHART GENERATOR
    # =========================================================

    def generate_rhythm_locked_chart(
        self,
        envelope,
        frame_time,
        bpm,
        beat,
        offset,
        difficulty,
    ):
        settings = DIFFICULTIES[
            difficulty
        ]

        subdivision = settings[
            "subdivision"
        ]

        # Every possible note time is generated
        # from this exact mathematical grid.
        step = beat / subdivision

        max_time = (
            len(envelope)
            * frame_time
        )

        start_time = max(
            0.0,
            offset,
        )

        grid_times = []

        current = start_time

        while current < max_time - 0.05:
            grid_times.append(
                current
            )
            current += step

        if not grid_times:
            return []

        grid_strengths = []

        # Measure the audio around each grid
        # position instead of moving the note
        # to the audio peak.
        radius_seconds = min(
            0.060,
            beat * 0.12,
        )

        radius_frames = max(
            1,
            int(
                radius_seconds
                / frame_time
            ),
        )

        for t in grid_times:
            index = int(
                round(
                    t / frame_time
                )
            )

            lo = max(
                0,
                index - radius_frames,
            )

            hi = min(
                len(envelope),
                index + radius_frames + 1,
            )

            if lo >= hi:
                strength = 0.0
            else:
                # Maximum local onset energy is
                # more useful than the exact center
                # because drums often peak slightly
                # before the beat.
                strength = float(
                    np.max(
                        envelope[lo:hi]
                    )
                )

            grid_strengths.append(
                strength
            )

        grid_strengths = np.asarray(
            grid_strengths,
            dtype=np.float32,
        )

        if len(grid_strengths) == 0:
            return []

        # Remove very weak background energy.
        baseline = float(
            np.percentile(
                grid_strengths,
                25,
            )
        )

        high = float(
            np.percentile(
                grid_strengths,
                95,
            )
        )

        if high <= baseline:
            high = baseline + 0.001

        normalized = (
            (grid_strengths - baseline)
            / (high - baseline)
        )

        normalized = np.clip(
            normalized,
            0.0,
            1.0,
        )

        # Difficulty controls density.
        threshold = settings[
            "threshold"
        ] / 100.0

        notes = []

        last_time = -999.0
        last_lane = -1

        for index, t in enumerate(
            grid_times
        ):
            strength = float(
                normalized[index]
            )

            if strength < threshold:
                continue

            if (
                t - last_time
                < settings["min_spacing"]
            ):
                continue

            # Do not make notes too close to
            # the beginning/end of the song.
            if t < 0.05:
                continue

            if t > max_time - 0.08:
                continue

            lanes = self.choose_lanes(
                index,
                strength,
                last_lane,
                settings,
            )

            if not lanes:
                continue

            # IMPORTANT:
            # All lanes in a chord have the EXACT
            # SAME t. No random timing offsets.
            for lane in lanes:
                notes.append(
                    {
                        "time": float(t),
                        "lane": int(lane),
                        "hit": False,
                        "missed": False,
                    }
                )

            last_time = t
            last_lane = lanes[-1]

        return notes

    def choose_lanes(
        self,
        index,
        strength,
        last_lane,
        settings,
    ):
        pattern = [
            0,
            1,
            2,
            3,
            2,
            1,
            0,
            1,
            2,
            3,
        ]

        primary = pattern[
            index % len(pattern)
        ]

        if primary == last_lane:
            primary = (
                primary + 1
            ) % 4

        lanes = [primary]

        if not settings["chords"]:
            return lanes

        if settings["jumps"]:
            # Strong events can become chords,
            # but the chord remains exactly on
            # the beat grid.
            if strength > 0.78:
                chord_patterns = [
                    [0, 2],
                    [1, 3],
                    [0, 3],
                    [1, 2],
                ]

                chord = chord_patterns[
                    index
                    % len(chord_patterns)
                ]

                if primary not in chord:
                    chord = [
                        primary,
                        chord[1],
                    ]

                lanes = sorted(
                    set(chord)
                )

            elif strength > 0.60:
                if index % 5 == 0:
                    other = (
                        primary + 2
                    ) % 4

                    lanes = sorted(
                        {
                            primary,
                            other,
                        }
                    )

        return lanes

    # =========================================================
    # ANALYSIS COMPLETE
    # =========================================================

    def analysis_finished(self):
        self.analysis_running = False

        self.screen = "difficulty"

        self.show_difficulty()

    def analysis_failed(self, error):
        self.analysis_running = False

        self.clear()

        cx, cy = self.center()

        self.text(
            cx,
            cy - 70,
            "ANALYSIS FAILED",
            30,
            "#ff4040",
        )

        self.text(
            cx,
            cy - 20,
            str(error)[:120],
            14,
            "white",
        )

        self.button(
            cx - 150,
            cy + 45,
            cx + 150,
            cy + 95,
            "BACK",
            self.show_menu,
        )

    # =========================================================
    # DIFFICULTY
    # =========================================================

    def show_difficulty(self):
        self.screen = "difficulty"

        self.clear()

        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        cx = width / 2

        self.text(
            cx,
            55,
            "SELECT DIFFICULTY",
            34,
        )

        names = [
            "EASY",
            "NORMAL",
            "HARD",
            "INSANE",
            "EXTREME",
            "OSU PRO",
        ]

        descriptions = {
            "EASY": "Quarter-beat rhythm with low density",
            "NORMAL": "Standard rhythm",
            "HARD": "Eighth-note rhythm",
            "INSANE": "Dense eighth-note rhythm",
            "EXTREME": "Sixteenth-note rhythm",
            "OSU PRO": "Maximum density for experienced players",
        }

        y = 105

        for name in names:
            def choose(
                n=name
            ):
                self.set_difficulty(
                    n
                )

            self.button(
                cx - 230,
                y,
                cx + 230,
                y + 48,
                name,
                choose,
            )

            self.text(
                cx,
                y + 62,
                descriptions[name],
                12,
                "#bbbbbb",
            )

            y += 82

        self.button(
            cx - 130,
            height - 55,
            cx + 130,
            height - 15,
            "BACK",
            self.show_menu,
        )

    def set_difficulty(self, difficulty):
        self.difficulty = difficulty

        if self.song_file:
            self.start_analysis()
        else:
            self.show_menu()

    # =========================================================
    # NOTE SPEED
    # =========================================================

    def show_speed(self):
        self.screen = "speed"

        self.clear()

        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        cx = width / 2

        self.text(
            cx,
            70,
            "NOTE SPEED",
            36,
        )

        self.text(
            cx,
            120,
            str(self.note_speed),
            34,
            "#ff5555",
        )

        speeds = [
            ("SLOW", 250),
            ("NORMAL", 420),
            ("FAST", 600),
            ("INSANE", 800),
        ]

        y = 180

        for name, speed in speeds:
            self.button(
                cx - 180,
                y,
                cx + 180,
                y + 48,
                f"{name}  ({speed})",
                lambda s=speed: self.set_speed(s),
            )

            y += 65

        self.button(
            cx - 180,
            y,
            cx - 10,
            y + 48,
            "-",
            lambda: self.change_speed(-30),
        )

        self.button(
            cx + 10,
            y,
            cx + 180,
            y + 48,
            "+",
            lambda: self.change_speed(30),
        )

        self.button(
            cx - 130,
            height - 65,
            cx + 130,
            height - 20,
            "BACK",
            self.show_menu,
        )

    def set_speed(self, speed):
        self.note_speed = speed
        self.show_speed()

    def change_speed(self, amount):
        self.note_speed = int(
            np.clip(
                self.note_speed + amount,
                MIN_NOTE_SPEED,
                MAX_NOTE_SPEED,
            )
        )

        self.show_speed()

    # =========================================================
    # KEY SETTINGS
    # =========================================================

    def show_keys(self):
        self.screen = "keys"

        self.clear()

        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        cx = width / 2

        self.text(
            cx,
            65,
            "KEY SETTINGS",
            34,
        )

        self.text(
            cx,
            105,
            "Click a key and press the new keyboard key.",
            14,
            "#bbbbbb",
        )

        labels = [
            "LANE 1",
            "LANE 2",
            "LANE 3",
            "LANE 4",
        ]

        y = 165

        for i in range(4):
            self.text(
                cx - 100,
                y + 25,
                labels[i],
                16,
                anchor="e",
            )

            self.button(
                cx - 70,
                y,
                cx + 70,
                y + 50,
                self.keys[i].upper(),
                lambda lane=i: self.capture_key(lane),
            )

            y += 75

        self.button(
            cx - 180,
            y + 10,
            cx - 10,
            y + 55,
            "RESET",
            self.reset_keys,
        )

        self.button(
            cx + 10,
            y + 10,
            cx + 180,
            y + 55,
            "BACK",
            self.show_menu,
        )

    def capture_key(self, lane):
        self.dragging_key = lane

        self.clear()

        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        cx = width / 2

        self.text(
            cx,
            height / 2 - 40,
            f"PRESS A KEY FOR LANE {lane + 1}",
            28,
        )

        self.text(
            cx,
            height / 2 + 10,
            "ESC is reserved for pause.",
            15,
            "#ffaaaa",
        )

        self.root.bind(
            "<KeyPress>",
            self.key_capture,
        )

    def key_capture(self, event):
        if self.dragging_key is None:
            return

        key = event.keysym.lower()

        if key == "escape":
            return

        if key in self.keys:
            messagebox.showerror(
                "Key already used",
                "That key is already assigned to another lane.",
            )
            return

        lane = self.dragging_key

        self.keys[lane] = key
        self.dragging_key = None

        self.root.unbind(
            "<KeyPress>"
        )

        self.show_keys()

    def reset_keys(self):
        self.keys = DEFAULT_KEYS.copy()
        self.show_keys()

    # =========================================================
    # TUTORIAL
    # =========================================================

    def show_tutorial(self):
        self.screen = "tutorial"

        self.clear()

        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        cx = width / 2

        self.text(
            cx,
            65,
            "TUTORIAL",
            36,
        )

        lines = [
            "Notes travel toward the hit line.",
            "",
            "Press D F J K when notes reach the line.",
            "",
            "PERFECT = very close",
            "GREAT = close",
            "GOOD = acceptable",
            "MISS = too late",
            "",
            "Press ESC to pause.",
            "",
            "The chart generator locks note timing",
            "to the detected musical beat grid.",
        ]

        y = 125

        for line in lines:
            self.text(
                cx,
                y,
                line,
                16,
                "#dddddd",
            )

            y += 28

        self.button(
            cx - 130,
            height - 70,
            cx + 130,
            height - 25,
            "BACK",
            self.show_menu,
        )

    # =========================================================
    # GAME START
    # =========================================================

    def start_game(self):
        if not self.song_file:
            return

        if not self.notes:
            messagebox.showerror(
                "No notes",
                "The rhythm analyzer did not generate any notes.",
            )
            return

        self.score = 0
        self.combo = 0
        self.max_combo = 0
        self.hits = 0
        self.misses = 0
        self.total_judged = 0

        self.hit_effects = []
        self.key_glow = [0, 0, 0, 0]

        for note in self.notes:
            note["hit"] = False
            note["missed"] = False

        self.active_notes = self.notes.copy()

        self.game_finished = False

        try:
            self.audio.play(
                self.wav_file
            )
        except Exception as exc:
            messagebox.showerror(
                "Audio error",
                str(exc),
            )
            return

        # Start the game clock at the same instant
        # that the audio player starts its process.
        self.song_start_time = (
            time.perf_counter()
        )

        self.screen = "game"

    # =========================================================
    # GAME LOOP
    # =========================================================

    def game_loop(self):
        try:
            self.draw_background()

            if self.screen == "menu":
                pass

            elif self.screen == "difficulty":
                pass

            elif self.screen == "speed":
                pass

            elif self.screen == "keys":
                pass

            elif self.screen == "tutorial":
                pass

            elif self.screen == "analysis":
                self.draw_analysis_animation()

            elif self.screen == "game":
                self.draw_game()

            elif self.screen == "pause":
                self.draw_game()
                self.draw_pause_overlay()

            elif self.screen == "results":
                pass

        except tk.TclError:
            return

        self.root.after(
            16,
            self.game_loop,
        )

    def draw_analysis_animation(self):
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()

        cx = width / 2

        pulse = (
            math.sin(
                time.perf_counter()
                * 5
            )
            + 1
        ) / 2

        self.text(
            cx,
            height / 2 + 100,
            "● " * int(
                3 + pulse * 4
            ),
            18,
            "#ff4040",
        )

    # =========================================================
    # GAME DRAWING
    # =========================================================

    def draw_game(self):
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()

        lane_width = min(
            130,
            width / 5.2,
        )

        total_width = lane_width * 4
        left = (
            width - total_width
        ) / 2

        hit_y = height - 125

        # Lane backgrounds
        for lane in range(4):
            x1 = (
                left
                + lane * lane_width
            )

            x2 = x1 + lane_width

            fill = (
                "#180000"
                if lane % 2 == 0
                else "#220000"
            )

            self.canvas.create_rectangle(
                x1,
                0,
                x2,
                height,
                fill=fill,
                outline="#300000",
            )

            if self.key_glow[lane] > 0:
                self.canvas.create_rectangle(
                    x1,
                    0,
                    x2,
                    height,
                    fill="#450000",
                    outline="",
                )

        # Hit line
        self.canvas.create_rectangle(
            left,
            hit_y - 4,
            left + total_width,
            hit_y + 4,
            fill="#ffffff",
            outline="",
        )

        # Lane key labels
        for lane in range(4):
            x = (
                left
                + lane * lane_width
                + lane_width / 2
            )

            self.text(
                x,
                hit_y + 35,
                self.keys[lane].upper(),
                22,
                "#ffffff",
            )

        position = self.audio.get_position()

        # Draw notes
        for note in self.active_notes:
            if note["hit"] or note["missed"]:
                continue

            time_until_hit = (
                note["time"]
                - position
            )

            y = (
                hit_y
                - time_until_hit
                * self.note_speed
            )

            if (
                y < -100
                or y > height + 100
            ):
                continue

            self.draw_arrow(
                left
                + note["lane"]
                * lane_width,
                y,
                lane_width,
                note["lane"],
            )

        self.process_misses(
            position
        )

        # Score
        self.text(
            20,
            20,
            f"SCORE {self.score}",
            18,
            anchor="w",
        )

        self.text(
            20,
            50,
            f"COMBO {self.combo}",
            18,
            "#ffaaaa",
            anchor="w",
        )

        self.text(
            width - 20,
            20,
            f"BPM {self.bpm:.1f}",
            16,
            "#bbbbbb",
            anchor="e",
        )

        self.text(
            width - 20,
            48,
            self.difficulty,
            16,
            "#bbbbbb",
            anchor="e",
        )

        self.draw_hit_effects()

        # End only after the audio and all notes
        # have finished.
        if (
            self.active_notes
            and position
            > self.duration + 1.0
        ):
            self.finish_game()

    def draw_arrow(
        self,
        x,
        y,
        width,
        lane,
    ):
        center_x = (
            x + width / 2
        )

        size = min(
            28,
            width * 0.28,
        )

        direction = lane

        if direction == 0:
            points = [
                center_x + size,
                y - size,
                center_x,
                y,
                center_x + size,
                y + size,
                center_x + size / 2,
                y + size,
                center_x - size / 2,
                y + size,
                center_x - size,
                y,
                center_x - size / 2,
                y - size,
            ]

        elif direction == 1:
            points = [
                center_x - size,
                y - size,
                center_x,
                y,
                center_x + size,
                y - size,
                center_x + size,
                y - size / 2,
                center_x + size,
                y + size,
                center_x,
                y + size / 2,
                center_x - size,
                y + size,
            ]

        elif direction == 2:
            points = [
                center_x - size,
                y - size,
                center_x,
                y,
                center_x + size,
                y - size,
                center_x + size / 2,
                y - size,
                center_x + size / 2,
                y + size,
                center_x - size / 2,
                y + size,
                center_x - size / 2,
                y - size,
            ]

        else:
            points = [
                center_x - size,
                y,
                center_x,
                y - size,
                center_x + size,
                y,
                center_x + size / 2,
                y + size,
                center_x - size / 2,
                y + size,
            ]

        self.canvas.create_polygon(
            points,
            fill="#ff3030",
            outline="#ffffff",
            width=2,
        )

    # =========================================================
    # MISSES
    # =========================================================

    def process_misses(self, position):
        miss_window = 0.17

        for note in self.active_notes:
            if note["hit"] or note["missed"]:
                continue

            if (
                position
                - note["time"]
                > miss_window
            ):
                note["missed"] = True

                self.combo = 0
                self.misses += 1
                self.total_judged += 1

                self.add_hit_effect(
                    note["lane"],
                    "MISS",
                )

    # =========================================================
    # KEY INPUT
    # =========================================================

    def handle_key(self, event):
        key = event.keysym.lower()

        if self.screen == "game":
            if key == "escape":
                self.pause_game()
                return

            for lane in range(4):
                if key == self.keys[lane]:
                    self.hit_lane(lane)
                    return

        elif self.screen == "pause":
            if key == "escape":
                self.resume_game()

    def hit_lane(self, lane):
        position = self.audio.get_position()

        self.key_glow[lane] = 8

        best_note = None
        best_difference = 999.0

        for note in self.active_notes:
            if note["hit"] or note["missed"]:
                continue

            if note["lane"] != lane:
                continue

            difference = abs(
                note["time"]
                - position
            )

            if difference < best_difference:
                best_difference = difference
                best_note = note

        if (
            best_note is None
            or best_difference > 0.150
        ):
            self.add_hit_effect(
                lane,
                "NO NOTE",
            )
            return

        best_note["hit"] = True

        if best_difference <= 0.025:
            judgement = "PERFECT"
            points = 300

        elif best_difference <= 0.060:
            judgement = "GREAT"
            points = 200

        elif best_difference <= 0.100:
            judgement = "GOOD"
            points = 100

        else:
            judgement = "GOOD"
            points = 50

        self.score += (
            points
            + self.combo * 5
        )

        self.combo += 1

        if self.combo > self.max_combo:
            self.max_combo = self.combo

        self.hits += 1
        self.total_judged += 1

        self.add_hit_effect(
            lane,
            judgement,
        )

    # =========================================================
    # EFFECTS
    # =========================================================

    def add_hit_effect(
        self,
        lane,
        text_value,
    ):
        self.hit_effects.append(
            {
                "lane": lane,
                "text": text_value,
                "life": 20,
            }
        )

    def draw_hit_effects(self):
        width = self.canvas.winfo_width()
        lane_width = min(
            130,
            width / 5.2,
        )

        left = (
            width
            - lane_width * 4
        ) / 2

        hit_y = (
            self.canvas.winfo_height()
            - 125
        )

        remaining = []

        for effect in self.hit_effects:
            life = effect["life"]

            x = (
                left
                + effect["lane"]
                * lane_width
                + lane_width / 2
            )

            y = (
                hit_y
                - (20 - life)
            )

            self.text(
                x,
                y,
                effect["text"],
                15,
                "#ffffff",
            )

            effect["life"] -= 1

            if effect["life"] > 0:
                remaining.append(
                    effect
                )

        self.hit_effects = remaining

        for i in range(4):
            if self.key_glow[i] > 0:
                self.key_glow[i] -= 1

    # =========================================================
    # PAUSE
    # =========================================================

    def pause_game(self):
        if self.screen != "game":
            return

        self.paused_position = (
            self.audio.get_position()
        )

        self.audio.pause()

        self.screen = "pause"

    def draw_pause_overlay(self):
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()

        self.canvas.create_rectangle(
            0,
            0,
            width,
            height,
            fill="#080000",
            stipple="gray50",
            outline="",
        )

        cx = width / 2

        self.text(
            cx,
            height / 2 - 100,
            "PAUSED",
            42,
        )

        self.button(
            cx - 170,
            height / 2 - 40,
            cx + 170,
            height / 2 + 10,
            "RESUME",
            self.resume_game,
        )

        self.button(
            cx - 170,
            height / 2 + 25,
            cx + 170,
            height / 2 + 75,
            "QUIT BEATMAP",
            self.quit_game,
        )

    def resume_game(self):
        if self.screen != "pause":
            return

        self.audio.resume()

        self.screen = "game"

    def quit_game(self):
        self.audio.stop()

        self.screen = "menu"

        self.show_menu()

    # =========================================================
    # RESULTS
    # =========================================================

    def finish_game(self):
        if self.game_finished:
            return

        self.game_finished = True

        self.audio.stop()

        self.screen = "results"

        self.show_results()

    def show_results(self):
        self.clear()

        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        cx = width / 2

        accuracy = 0.0

        if self.total_judged > 0:
            accuracy = (
                self.hits
                / self.total_judged
                * 100
            )

        self.text(
            cx,
            75,
            "RESULTS",
            42,
        )

        self.text(
            cx,
            145,
            f"SCORE: {self.score}",
            24,
        )

        self.text(
            cx,
            190,
            f"ACCURACY: {accuracy:.2f}%",
            22,
            "#ffaaaa",
        )

        self.text(
            cx,
            235,
            f"MAX COMBO: {self.max_combo}",
            20,
        )

        self.text(
            cx,
            280,
            f"HITS: {self.hits}",
            18,
        )

        self.text(
            cx,
            315,
            f"MISSES: {self.misses}",
            18,
        )

        self.text(
            cx,
            350,
            f"BPM: {self.bpm:.1f}",
            16,
            "#bbbbbb",
        )

        self.text(
            cx,
            380,
            f"Difficulty: {self.difficulty}",
            16,
            "#bbbbbb",
        )

        self.button(
            cx - 180,
            height - 130,
            cx + 180,
            height - 80,
            "PLAY AGAIN",
            self.start_game,
        )

        self.button(
            cx - 180,
            height - 70,
            cx + 180,
            height - 20,
            "MAIN MENU",
            self.show_menu,
        )

    # =========================================================
    # YOUTUBE
    # =========================================================

    def import_youtube(self):
        if self.youtube_window is not None:
            try:
                self.youtube_window.destroy()
            except Exception:
                pass

        self.youtube_window = tk.Toplevel(
            self.root
        )

        self.youtube_window.title(
            "YouTube Import"
        )

        self.youtube_window.geometry(
            "600x230"
        )

        self.youtube_window.configure(
            bg="#080000"
        )

        tk.Label(
            self.youtube_window,
            text="Paste YouTube URL",
            bg="#080000",
            fg="white",
            font=("Arial", 18, "bold"),
        ).pack(
            pady=20
        )

        entry = tk.Entry(
            self.youtube_window,
            width=65,
            bg="#180000",
            fg="white",
            insertbackground="white",
        )

        entry.pack(
            padx=20,
            pady=5,
        )

        status = tk.Label(
            self.youtube_window,
            text="",
            bg="#080000",
            fg="#ffaaaa",
        )

        status.pack(
            pady=10
        )

        self.youtube_status = status

        tk.Button(
            self.youtube_window,
            text="DOWNLOAD",
            command=lambda: self.download_youtube(
                entry.get().strip()
            ),
            bg="#300000",
            fg="white",
            activebackground="#550000",
            activeforeground="white",
        ).pack(
            pady=5
        )

    def download_youtube(self, url):
        if not url:
            messagebox.showerror(
                "YouTube",
                "Paste a YouTube link first.",
                parent=self.youtube_window,
            )
            return

        if self.youtube_status:
            self.youtube_status.config(
                text="Downloading..."
            )

        threading.Thread(
            target=self.youtube_worker,
            args=(url,),
            daemon=True,
        ).start()

    def youtube_worker(self, url):
        try:
            try:
                import yt_dlp
            except ImportError:
                raise RuntimeError(
                    "yt-dlp is not installed.\n\n"
                    "Run:\n"
                    "py -3.14 -m pip install -U \"yt-dlp[default]\""
                )

            temp_dir = tempfile.mkdtemp(
                prefix="maniatk_youtube_"
            )

            output_template = os.path.join(
                temp_dir,
                "youtube_audio.%(ext)s",
            )

            options = {
                "format": (
                    "bestaudio[ext=m4a]"
                    "/bestaudio/best"
                ),
                "outtmpl": output_template,
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "restrictfilenames": True,
            }

            with yt_dlp.YoutubeDL(
                options
            ) as ydl:
                info = ydl.extract_info(
                    url,
                    download=True,
                )

                downloaded = (
                    ydl.prepare_filename(
                        info
                    )
                )

            if not os.path.isfile(
                downloaded
            ):
                files = os.listdir(
                    temp_dir
                )

                media_files = [
                    os.path.join(
                        temp_dir,
                        x,
                    )
                    for x in files
                    if x.lower().endswith(
                        (
                            ".m4a",
                            ".webm",
                            ".mp3",
                            ".opus",
                        )
                    )
                ]

                if not media_files:
                    raise RuntimeError(
                        "YouTube audio download completed "
                        "but no audio file was found."
                    )

                downloaded = media_files[0]

            self.root.after(
                0,
                lambda: self.youtube_download_finished(
                    downloaded,
                    info.get(
                        "title",
                        "YouTube song",
                    ),
                ),
            )

        except Exception as exc:
            self.root.after(
                0,
                lambda e=exc: self.youtube_failed(e),
            )

    def youtube_download_finished(
        self,
        filename,
        title,
    ):
        if self.youtube_window:
            try:
                self.youtube_window.destroy()
            except Exception:
                pass

            self.youtube_window = None

        self.song_file = filename
        self.song_name = title

        self.start_analysis()

    def youtube_failed(self, error):
        if self.youtube_status:
            try:
                self.youtube_status.config(
                    text="Download failed."
                )
            except Exception:
                pass

        messagebox.showerror(
            "YouTube download failed",
            str(error),
        )

    # =========================================================
    # UPDATE CHECK
    # =========================================================

    def check_update(self):
        try:
            with urllib.request.urlopen(
                GITHUB_VERSION_URL,
                timeout=5,
            ) as response:
                remote = (
                    response.read()
                    .decode()
                    .strip()
                )

            if remote != GAME_VERSION:
                return remote

        except Exception:
            pass

        return None

    # =========================================================
    # CLOSE
    # =========================================================

    def close(self):
        try:
            self.audio.stop()
        except Exception:
            pass

        try:
            if self.wav_file:
                folder = os.path.dirname(
                    self.wav_file
                )

                if folder.startswith(
                    tempfile.gettempdir()
                ):
                    shutil.rmtree(
                        folder,
                        ignore_errors=True,
                    )
        except Exception:
            pass

        try:
            self.root.destroy()
        except Exception:
            pass

    # =========================================================
    # START
    # =========================================================

    def run(self):
        self.root.bind(
            "<KeyPress>",
            self.handle_key,
        )

        self.root.mainloop()


if __name__ == "__main__":
    app = ManiaTK()
    app.run()
