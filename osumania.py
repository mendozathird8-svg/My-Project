import os
import time
import wave
import shutil
import tempfile
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox

import numpy as np


# ============================================================
# MANIATK
# Python 3.14 compatible
# 4K osu!mania-inspired rhythm game
#
# NO PYGAME
#
# FEATURES
#   MP3 / MP4 / WAV / OGG / M4A / WMA
#   Automatic beatmap generation
#   6 difficulties
#   Rebindable keys
#   D F J K default controls
#   Colored notes
#   Score / combo / accuracy
#   Perfect / Great / Good / Miss
#   Empty key presses
#   Pause menu
#   Resume
#   Quit Beatmap
#   Exit Game
# ============================================================


# ============================================================
# SETTINGS
# ============================================================

WIDTH = 720
HEIGHT = 820

LANES = 4

# Default keybinds
DEFAULT_KEYS = ["d", "f", "j", "k"]

# This gets changed by the keybind menu
KEYS = DEFAULT_KEYS.copy()

LANE_WIDTH = 130
LANE_GAP = 4

PLAYFIELD_WIDTH = (
    LANES * LANE_WIDTH
    + (LANES - 1) * LANE_GAP
)

PLAYFIELD_X = (
    WIDTH - PLAYFIELD_WIDTH
) // 2

RECEPTOR_Y = 700

NOTE_HEIGHT = 25

NOTE_SPEED = 520.0

PERFECT_WINDOW = 0.025
GREAT_WINDOW = 0.060
GOOD_WINDOW = 0.100
MISS_WINDOW = 0.150


# ============================================================
# COLORS
# ============================================================

NOTE_COLORS = [
    "#ff4f81",
    "#4f9cff",
    "#4fff88",
    "#ffd84f",
]


# ============================================================
# DIFFICULTIES
# ============================================================

DIFFICULTIES = {
    "EASY": {
        "threshold": 72,
        "min_spacing": 0.240,
        "chords": False,
        "jumps": False,
    },

    "NORMAL": {
        "threshold": 63,
        "min_spacing": 0.155,
        "chords": True,
        "jumps": False,
    },

    "HARD": {
        "threshold": 54,
        "min_spacing": 0.115,
        "chords": True,
        "jumps": True,
    },

    "INSANE": {
        "threshold": 45,
        "min_spacing": 0.082,
        "chords": True,
        "jumps": True,
    },

    "EXTREME": {
        "threshold": 38,
        "min_spacing": 0.060,
        "chords": True,
        "jumps": True,
    },

    "OSU PRO (MY BROTHER)": {
        "threshold": 30,
        "min_spacing": 0.042,
        "chords": True,
        "jumps": True,
    },
}


DIFFICULTY_DESCRIPTIONS = {
    "EASY":
        "Fewer notes • slower patterns",

    "NORMAL":
        "Balanced chart • occasional chords",

    "HARD":
        "Fast patterns • more chords",

    "INSANE":
        "Very dense • fast lane changes",

    "EXTREME":
        "Extremely dense • rapid patterns • lots of chords",

    "OSU PRO (MY BROTHER)":
        "Brother mode • brutal density • very fast patterns",
}


# ============================================================
# PROGRAM FINDER
# ============================================================

def find_program(name):
    return shutil.which(name)


# ============================================================
# AUDIO PLAYER
# ============================================================

class AudioPlayer:

    def __init__(self):

        self.process = None

        self.media = None

        self.started_at = None

        self.pause_position = 0.0

        self.paused = False

        self.playing = False

        self.ffplay = find_program("ffplay")

        self.ps_process = None


    def play(self, filename, position=0.0):

        self.stop()

        self.media = filename

        self.pause_position = position

        self.paused = False

        self.playing = True

        self.started_at = (
            time.perf_counter() - position
        )


        # ----------------------------------------------------
        # FFPLAY
        # ----------------------------------------------------

        if self.ffplay:

            try:

                command = [
                    self.ffplay,
                    "-nodisp",
                    "-autoexit",
                    "-loglevel",
                    "quiet",
                    "-ss",
                    str(position),
                    filename
                ]

                self.process = subprocess.Popen(
                    command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=(
                        subprocess.CREATE_NO_WINDOW
                        if os.name == "nt"
                        else 0
                    )
                )

                return

            except Exception:

                self.process = None


        # ----------------------------------------------------
        # POWERSHELL FALLBACK
        # ----------------------------------------------------

        self._play_powershell(
            filename,
            position
        )


    def _play_powershell(
        self,
        filename,
        position
    ):

        if os.name != "nt":

            messagebox.showerror(
                "Audio Error",
                "ffplay was not found."
            )

            self.playing = False

            return


        safe_path = (
            os.path.abspath(filename)
            .replace("'", "''")
        )


        script = f"""
Add-Type -AssemblyName PresentationCore

$player = New-Object System.Windows.Media.MediaPlayer

$player.Open(
    [Uri]::new('{safe_path}')
)

Start-Sleep -Milliseconds 500

$player.Position =
    [TimeSpan]::FromSeconds({position})

$player.Play()

while ($true) {{
    Start-Sleep -Milliseconds 100
}}
"""


        try:

            self.ps_process = subprocess.Popen(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    script
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

        except Exception:

            self.ps_process = None

            self.playing = False

            messagebox.showerror(
                "Audio Error",
                "Could not start audio playback.\n\n"
                "Install FFmpeg and make sure ffplay.exe "
                "is available in PATH."
            )


    def position(self):

        if not self.playing:

            return self.pause_position


        if self.paused:

            return self.pause_position


        if self.started_at is None:

            return 0.0


        return max(
            0.0,
            time.perf_counter()
            - self.started_at
        )


    def pause(self):

        if not self.playing:

            return

        if self.paused:

            return


        self.pause_position = self.position()

        self.paused = True


        if self.process:

            try:

                if self.process.poll() is None:

                    self.process.stdin.write(
                        b" "
                    )

                    self.process.stdin.flush()

            except Exception:

                pass


    def resume(self):

        if not self.playing:

            return

        if not self.paused:

            return


        if self.process:

            try:

                if self.process.poll() is None:

                    self.process.stdin.write(
                        b" "
                    )

                    self.process.stdin.flush()

            except Exception:

                pass


        self.started_at = (
            time.perf_counter()
            - self.pause_position
        )

        self.paused = False


    def stop(self):

        self.playing = False

        self.paused = False

        self.pause_position = 0.0

        self.started_at = None


        if self.process:

            try:

                if self.process.poll() is None:

                    try:

                        self.process.stdin.write(
                            b"q"
                        )

                        self.process.stdin.flush()

                    except Exception:

                        pass


                    try:

                        self.process.terminate()

                    except Exception:

                        pass

            except Exception:

                pass


            self.process = None


        if self.ps_process:

            try:

                if self.ps_process.poll() is None:

                    self.ps_process.terminate()

            except Exception:

                pass

            self.ps_process = None


    def is_finished(self):

        if not self.playing:

            return True


        if self.process:

            return (
                self.process.poll()
                is not None
            )


        return False


# ============================================================
# GAME
# ============================================================

class ManiaTK:

    def __init__(self, root):

        self.root = root

        self.root.title(
            "ManiaTK"
        )

        self.root.geometry(
            f"{WIDTH}x{HEIGHT}"
        )

        self.root.resizable(
            False,
            False
        )

        self.root.configure(
            bg="#101018"
        )


        # ----------------------------------------------------
        # CANVAS
        # ----------------------------------------------------

        self.canvas = tk.Canvas(
            root,
            width=WIDTH,
            height=HEIGHT,
            bg="#101018",
            highlightthickness=0
        )

        self.canvas.pack()


        # ----------------------------------------------------
        # STATE
        # ----------------------------------------------------

        self.screen = "menu"

        self.running = False

        self.paused = False

        self.pause_frame = None

        self.media_path = None

        self.chart = []

        self.song_length = 0.0

        self.selected_difficulty = "NORMAL"


        # ----------------------------------------------------
        # KEY REBINDING
        # ----------------------------------------------------

        self.keys = DEFAULT_KEYS.copy()

        self.rebinding_lane = None

        self.rebind_frame = None


        # ----------------------------------------------------
        # AUDIO
        # ----------------------------------------------------

        self.audio = AudioPlayer()


        # ----------------------------------------------------
        # STATS
        # ----------------------------------------------------

        self.score = 0

        self.combo = 0

        self.max_combo = 0

        self.perfects = 0

        self.greats = 0

        self.goods = 0

        self.misses = 0


        self.judgement = ""

        self.judgement_until = 0.0


        # ----------------------------------------------------
        # KEY STATE
        # ----------------------------------------------------

        self.key_down = {}


        self.update_key_state()


        # ----------------------------------------------------
        # KEYBOARD
        # ----------------------------------------------------

        self.root.bind(
            "<KeyPress>",
            self.key_press
        )

        self.root.bind(
            "<KeyRelease>",
            self.key_release
        )


        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.close_application
        )


        # ----------------------------------------------------
        # MENU
        # ----------------------------------------------------

        self.draw_menu()


    # ========================================================
    # UPDATE KEY STATE
    # ========================================================

    def update_key_state(self):

        self.key_down = {
            key: False
            for key in self.keys
        }


    # ========================================================
    # BUTTON
    # ========================================================

    def make_button(
        self,
        text,
        command,
        x,
        y,
        width=200,
        height=45
    ):

        button = tk.Button(
            self.canvas,
            text=text,
            command=command,
            font=(
                "Segoe UI",
                11,
                "bold"
            ),
            bg="#252536",
            fg="white",
            activebackground="#41415b",
            activeforeground="white",
            relief="flat",
            bd=0,
            cursor="hand2"
        )


        self.canvas.create_window(
            x,
            y,
            window=button,
            width=width,
            height=height
        )


        return button


    # ========================================================
    # MENU
    # ========================================================

    def draw_menu(self):

        self.screen = "menu"

        self.canvas.delete(
            "all"
        )

        self.canvas.configure(
            bg="#101018"
        )


        self.canvas.create_text(
            WIDTH // 2,
            65,
            text="MANIATK",
            fill="white",
            font=(
                "Segoe UI",
                34,
                "bold"
            )
        )


        self.canvas.create_text(
            WIDTH // 2,
            107,
            text="4K RHYTHM GAME",
            fill="#8888aa",
            font=(
                "Segoe UI",
                11
            )
        )


        # ----------------------------------------------------
        # SONG
        # ----------------------------------------------------

        if self.media_path:

            filename = os.path.basename(
                self.media_path
            )


            if len(filename) > 45:

                filename = (
                    filename[:42]
                    + "..."
                )


            self.canvas.create_text(
                WIDTH // 2,
                145,
                text=f"Song: {filename}",
                fill="#dddddd",
                font=(
                    "Segoe UI",
                    11
                )
            )

        else:

            self.canvas.create_text(
                WIDTH // 2,
                145,
                text="No song imported",
                fill="#777788",
                font=(
                    "Segoe UI",
                    11
                )
            )


        # ----------------------------------------------------
        # IMPORT
        # ----------------------------------------------------

        self.make_button(
            "IMPORT MP3 / MP4",
            self.import_media,
            WIDTH // 2,
            195,
            250,
            46
        )


        # ----------------------------------------------------
        # DIFFICULTY
        # ----------------------------------------------------

        self.make_button(
            "SELECT DIFFICULTY",
            self.show_difficulties,
            WIDTH // 2,
            250,
            250,
            46
        )


        # ----------------------------------------------------
        # KEYBINDS
        # ----------------------------------------------------

        self.make_button(
            "KEYBINDS",
            self.show_keybinds,
            WIDTH // 2,
            305,
            250,
            46
        )


        # ----------------------------------------------------
        # GENERATE
        # ----------------------------------------------------

        self.make_button(
            "GENERATE BEATMAP",
            self.generate_beatmap,
            WIDTH // 2,
            360,
            250,
            46
        )


        # ----------------------------------------------------
        # PLAY
        # ----------------------------------------------------

        self.make_button(
            "PLAY",
            self.start_game,
            WIDTH // 2,
            425,
            250,
            55
        )


        self.canvas.create_text(
            WIDTH // 2,
            495,
            text=(
                f"Difficulty: "
                f"{self.selected_difficulty}"
            ),
            fill="white",
            font=(
                "Segoe UI",
                13,
                "bold"
            )
        )


        self.canvas.create_text(
            WIDTH // 2,
            525,
            text=DIFFICULTY_DESCRIPTIONS[
                self.selected_difficulty
            ],
            fill="#9999aa",
            font=(
                "Segoe UI",
                9
            )
        )


        # ----------------------------------------------------
        # CURRENT KEYS
        # ----------------------------------------------------

        self.canvas.create_text(
            WIDTH // 2,
            570,
            text=(
                "KEYS:   "
                + "   ".join(
                    key.upper()
                    for key in self.keys
                )
            ),
            fill="white",
            font=(
                "Consolas",
                15,
                "bold"
            )
        )


        self.canvas.create_text(
            WIDTH // 2,
            620,
            text="ESC = Pause",
            fill="#777788",
            font=(
                "Segoe UI",
                10
            )
        )


        self.canvas.create_text(
            WIDTH // 2,
            665,
            text=(
                "No .osu file required • "
                "Beatmaps are generated automatically"
            ),
            fill="#555566",
            font=(
                "Segoe UI",
                9
            )
        )


    # ========================================================
    # IMPORT MEDIA
    # ========================================================

    def import_media(self):

        filename = filedialog.askopenfilename(
            title="Import Song / Video",
            filetypes=[
                (
                    "Media files",
                    "*.mp3 *.mp4 *.wav *.ogg *.m4a *.wma"
                ),
                (
                    "MP3",
                    "*.mp3"
                ),
                (
                    "MP4",
                    "*.mp4"
                ),
                (
                    "WAV",
                    "*.wav"
                ),
                (
                    "OGG",
                    "*.ogg"
                ),
                (
                    "M4A",
                    "*.m4a"
                ),
                (
                    "WMA",
                    "*.wma"
                ),
                (
                    "All files",
                    "*.*"
                )
            ]
        )


        if not filename:

            return


        self.media_path = filename

        self.chart = []

        self.song_length = 0.0

        self.draw_menu()


    # ========================================================
    # DIFFICULTIES
    # ========================================================

    def show_difficulties(self):

        self.screen = "difficulty"

        self.canvas.delete(
            "all"
        )


        self.canvas.create_text(
            WIDTH // 2,
            55,
            text="SELECT DIFFICULTY",
            fill="white",
            font=(
                "Segoe UI",
                27,
                "bold"
            )
        )


        names = [
            "EASY",
            "NORMAL",
            "HARD",
            "INSANE",
            "EXTREME",
            "OSU PRO (MY BROTHER)"
        ]


        y = 125


        for name in names:

            self.make_button(
                name,
                lambda n=name:
                    self.select_difficulty(n),
                WIDTH // 2,
                y,
                300,
                47
            )


            self.canvas.create_text(
                WIDTH // 2,
                y + 30,
                text=DIFFICULTY_DESCRIPTIONS[
                    name
                ],
                fill="#9999aa",
                font=(
                    "Segoe UI",
                    8
                )
            )


            y += 83


        self.make_button(
            "BACK",
            self.draw_menu,
            WIDTH // 2,
            700,
            180,
            40
        )


    def select_difficulty(
        self,
        difficulty
    ):

        self.selected_difficulty = (
            difficulty
        )

        self.draw_menu()


    # ========================================================
    # KEYBINDS SCREEN
    # ========================================================

    def show_keybinds(self):

        self.screen = "keybinds"

        self.rebinding_lane = None

        self.canvas.delete(
            "all"
        )


        self.canvas.create_text(
            WIDTH // 2,
            60,
            text="KEYBINDS",
            fill="white",
            font=(
                "Segoe UI",
                30,
                "bold"
            )
        )


        self.canvas.create_text(
            WIDTH // 2,
            105,
            text=(
                "Click a lane, then press "
                "the key you want to use"
            ),
            fill="#9999aa",
            font=(
                "Segoe UI",
                11
            )
        )


        lane_names = [
            "LANE 1",
            "LANE 2",
            "LANE 3",
            "LANE 4"
        ]


        y = 180


        for lane in range(LANES):

            self.canvas.create_text(
                WIDTH // 2 - 115,
                y,
                text=lane_names[lane],
                fill=NOTE_COLORS[lane],
                font=(
                    "Segoe UI",
                    14,
                    "bold"
                )
            )


            self.make_button(
                f"[ {self.keys[lane].upper()} ]",
                lambda l=lane:
                    self.begin_rebind(l),
                WIDTH // 2 + 80,
                y,
                180,
                48
            )


            y += 75


        # ----------------------------------------------------
        # RESET
        # ----------------------------------------------------

        self.make_button(
            "RESET TO D F J K",
            self.reset_keybinds,
            WIDTH // 2,
            525,
            230,
            45
        )


        # ----------------------------------------------------
        # BACK
        # ----------------------------------------------------

        self.make_button(
            "BACK",
            self.draw_menu,
            WIDTH // 2,
            600,
            180,
            45
        )


        self.canvas.create_text(
            WIDTH // 2,
            675,
            text=(
                "ESC cannot be rebound because "
                "it is reserved for Pause."
            ),
            fill="#666677",
            font=(
                "Segoe UI",
                9
            )
        )


    # ========================================================
    # BEGIN REBIND
    # ========================================================

    def begin_rebind(self, lane):

        self.rebinding_lane = lane

        self.screen = "keybind_wait"


        self.canvas.delete(
            "all"
        )


        self.canvas.create_text(
            WIDTH // 2,
            250,
            text=(
                f"PRESS A KEY FOR "
                f"LANE {lane + 1}"
            ),
            fill="white",
            font=(
                "Segoe UI",
                25,
                "bold"
            )
        )


        self.canvas.create_text(
            WIDTH // 2,
            305,
            text=(
                "Press ESC to cancel"
            ),
            fill="#888899",
            font=(
                "Segoe UI",
                11
            )
        )


        self.canvas.create_text(
            WIDTH // 2,
            365,
            text=(
                "Current: "
                + self.keys[lane].upper()
            ),
            fill=NOTE_COLORS[lane],
            font=(
                "Segoe UI",
                16,
                "bold"
            )
        )


    # ========================================================
    # RECEIVE REBIND KEY
    # ========================================================

    def handle_rebind(self, event):

        if self.rebinding_lane is None:

            return


        key = event.keysym.lower()


        # ----------------------------------------------------
        # ESC CANCELS
        # ----------------------------------------------------

        if key == "escape":

            self.rebinding_lane = None

            self.show_keybinds()

            return


        # ----------------------------------------------------
        # Reject modifier / special keys
        # ----------------------------------------------------

        invalid = {
            "shift_l",
            "shift_r",
            "control_l",
            "control_r",
            "alt_l",
            "alt_r",
            "win_l",
            "win_r",
            "caps_lock",
            "num_lock",
            "scroll_lock",
            "print",
            "pause",
        }


        if key in invalid:

            return


        # ----------------------------------------------------
        # Prevent duplicate keybinds
        # ----------------------------------------------------

        if key in self.keys:

            other_lane = self.keys.index(
                key
            )


            messagebox.showwarning(
                "Key Already Used",
                (
                    f"{key.upper()} is already "
                    f"assigned to Lane "
                    f"{other_lane + 1}."
                )
            )

            return


        # ----------------------------------------------------
        # Apply new key
        # ----------------------------------------------------

        lane = self.rebinding_lane

        self.keys[lane] = key

        self.update_key_state()

        self.rebinding_lane = None

        self.show_keybinds()


    # ========================================================
    # RESET KEYBINDS
    # ========================================================

    def reset_keybinds(self):

        self.keys = DEFAULT_KEYS.copy()

        self.update_key_state()

        self.rebinding_lane = None

        self.show_keybinds()


    # ========================================================
    # AUDIO CONVERSION
    # ========================================================

    def convert_to_wav(
        self,
        filename
    ):

        extension = os.path.splitext(
            filename
        )[1].lower()


        if extension == ".wav":

            return filename, False


        ffmpeg = find_program(
            "ffmpeg"
        )


        if not ffmpeg:

            raise RuntimeError(
                "FFmpeg was not found.\n\n"
                "Install FFmpeg and make sure "
                "ffmpeg.exe is in PATH."
            )


        temp = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        )

        temp.close()


        command = [
            ffmpeg,
            "-y",
            "-i",
            filename,
            "-vn",
            "-ac",
            "1",
            "-ar",
            "22050",
            "-sample_fmt",
            "s16",
            temp.name
        ]


        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )


        if result.returncode != 0:

            try:
                os.unlink(temp.name)
            except Exception:
                pass


            raise RuntimeError(
                "FFmpeg could not convert the media file.\n\n"
                + result.stderr.decode(
                    errors="ignore"
                )[-1000:]
            )


        return temp.name, True


    # ========================================================
    # READ WAV
    # ========================================================

    def read_wav(
        self,
        filename
    ):

        with wave.open(
            filename,
            "rb"
        ) as wf:

            channels = wf.getnchannels()

            sample_width = wf.getsampwidth()

            sample_rate = wf.getframerate()

            frames = wf.getnframes()

            raw = wf.readframes(
                frames
            )


        if sample_width == 2:

            audio = np.frombuffer(
                raw,
                dtype=np.int16
            ).astype(
                np.float32
            )

            audio /= 32768.0


        elif sample_width == 1:

            audio = np.frombuffer(
                raw,
                dtype=np.uint8
            ).astype(
                np.float32
            )

            audio = (
                audio - 128.0
            ) / 128.0


        elif sample_width == 4:

            audio = np.frombuffer(
                raw,
                dtype=np.int32
            ).astype(
                np.float32
            )

            audio /= 2147483648.0


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


    # ========================================================
    # GENERATE BEATMAP
    # ========================================================

    def generate_beatmap(self):

        if not self.media_path:

            messagebox.showwarning(
                "No Song",
                (
                    "Import an MP3, MP4, WAV, OGG, "
                    "M4A, or WMA first."
                )
            )

            return


        try:

            self.canvas.delete(
                "all"
            )


            self.canvas.create_text(
                WIDTH // 2,
                HEIGHT // 2 - 30,
                text="GENERATING BEATMAP...",
                fill="white",
                font=(
                    "Segoe UI",
                    24,
                    "bold"
                )
            )


            self.canvas.create_text(
                WIDTH // 2,
                HEIGHT // 2 + 15,
                text="Analyzing audio...",
                fill="#9999aa",
                font=(
                    "Segoe UI",
                    11
                )
            )


            self.root.update()


            wav_path, temporary = (
                self.convert_to_wav(
                    self.media_path
                )
            )


            try:

                audio, sample_rate = (
                    self.read_wav(
                        wav_path
                    )
                )

            finally:

                if temporary:

                    try:
                        os.unlink(
                            wav_path
                        )
                    except Exception:
                        pass


            if len(audio) == 0:

                raise RuntimeError(
                    "The audio file contains no samples."
                )


            self.song_length = (
                len(audio)
                / sample_rate
            )


            self.chart = (
                self.analyze_audio(
                    audio,
                    sample_rate,
                    self.selected_difficulty
                )
            )


            if not self.chart:

                raise RuntimeError(
                    "No notes could be generated."
                )


            self.draw_menu()


            messagebox.showinfo(
                "Beatmap Generated",
                (
                    f"Generated "
                    f"{len(self.chart)} notes.\n\n"
                    f"Difficulty: "
                    f"{self.selected_difficulty}\n"
                    f"Song length: "
                    f"{self.song_length:.2f} seconds"
                )
            )


        except Exception as e:

            self.draw_menu()

            messagebox.showerror(
                "Beatmap Error",
                str(e)
            )


    # ========================================================
    # ANALYZE AUDIO
    # ========================================================

    def analyze_audio(
        self,
        audio,
        sample_rate,
        difficulty
    ):

        settings = DIFFICULTIES[
            difficulty
        ]


        frame_size = int(
            sample_rate * 0.046
        )

        hop = int(
            sample_rate * 0.023
        )


        if len(audio) < frame_size:

            return []


        count = (
            1
            + (
                len(audio)
                - frame_size
            )
            // hop
        )


        energies = np.zeros(
            count,
            dtype=np.float32
        )


        # ----------------------------------------------------
        # RMS ENERGY
        # ----------------------------------------------------

        for i in range(count):

            start = i * hop

            end = (
                start
                + frame_size
            )

            frame = audio[
                start:end
            ]


            if len(frame) == 0:

                continue


            energies[i] = np.sqrt(
                np.mean(
                    frame * frame
                )
                + 1e-12
            )


        # ----------------------------------------------------
        # SMOOTH
        # ----------------------------------------------------

        kernel = (
            np.ones(5)
            / 5
        )


        smoothed = np.convolve(
            energies,
            kernel,
            mode="same"
        )


        # ----------------------------------------------------
        # NORMALIZE
        # ----------------------------------------------------

        low = np.percentile(
            smoothed,
            15
        )

        high = np.percentile(
            smoothed,
            98
        )


        if high <= low:

            high = low + 1e-6


        normalized = (
            smoothed - low
        ) / (
            high - low
        )


        normalized = np.clip(
            normalized,
            0.0,
            1.0
        )


        threshold = (
            settings["threshold"]
            / 100.0
        )


        # ----------------------------------------------------
        # PEAK DETECTION
        # ----------------------------------------------------

        candidates = []


        for i in range(
            2,
            len(normalized) - 2
        ):

            value = normalized[i]


            if value < threshold:

                continue


            if value < normalized[i - 1]:

                continue


            if value < normalized[i + 1]:

                continue


            if value < normalized[i - 2]:

                continue


            if value < normalized[i + 2]:

                continue


            t = (
                i
                * hop
                / sample_rate
            )


            if t < 0.7:

                continue


            candidates.append(
                (
                    t,
                    value
                )
            )


        # ----------------------------------------------------
        # MINIMUM SPACING
        # ----------------------------------------------------

        selected = []

        last_time = -999.0


        for t, value in candidates:

            if (
                t - last_time
                >= settings["min_spacing"]
            ):

                selected.append(
                    (
                        t,
                        value
                    )
                )

                last_time = t


        # ----------------------------------------------------
        # CREATE NOTES
        # ----------------------------------------------------

        chart = []

        previous_lane = 1


        for index, (
            t,
            strength
        ) in enumerate(selected):

            # ----------------------------------------------
            # LANE
            # ----------------------------------------------

            if settings["jumps"]:

                lane = (
                    int(
                        strength * 1000
                    )
                    + index * 3
                ) % LANES

            else:

                if index % 4 == 0:

                    lane = (
                        previous_lane + 1
                    ) % LANES

                elif index % 3 == 0:

                    lane = (
                        previous_lane - 1
                    ) % LANES

                else:

                    lane = (
                        int(
                            strength * 100
                        )
                        + index
                    ) % LANES


            if lane == previous_lane:

                lane = (
                    lane + 1
                ) % LANES


            previous_lane = lane


            chart.append({
                "time": t,
                "lane": lane,
                "hit": False,
                "missed": False,
                "holding": False,
            })


            # ----------------------------------------------
            # CHORDS
            # ----------------------------------------------

            if settings["chords"]:

                chord_every = {
                    "NORMAL": 11,
                    "HARD": 7,
                    "INSANE": 4,
                    "EXTREME": 3,
                    "OSU PRO (MY BROTHER)": 2,
                }.get(
                    difficulty,
                    999
                )


                if (
                    index > 0
                    and index % chord_every == 0
                ):

                    second_lane = (
                        lane + 1
                    ) % LANES


                    chart.append({
                        "time": t,
                        "lane": second_lane,
                        "hit": False,
                        "missed": False,
                        "holding": False,
                    })


            # ----------------------------------------------
            # EXTREME EXTRA
            # ----------------------------------------------

            if difficulty == "EXTREME":

                if (
                    index > 0
                    and index % 6 == 0
                ):

                    second_lane = (
                        lane + 2
                    ) % LANES


                    chart.append({
                        "time": t + 0.030,
                        "lane": second_lane,
                        "hit": False,
                        "missed": False,
                        "holding": False,
                    })


            # ----------------------------------------------
            # OSU PRO EXTRA
            # ----------------------------------------------

            if (
                difficulty
                == "OSU PRO (MY BROTHER)"
            ):

                if (
                    index > 0
                    and index % 3 == 0
                ):

                    second_lane = (
                        lane + 2
                    ) % LANES


                    chart.append({
                        "time": t + 0.022,
                        "lane": second_lane,
                        "hit": False,
                        "missed": False,
                        "holding": False,
                    })


        # ----------------------------------------------------
        # REMOVE DUPLICATES
        # ----------------------------------------------------

        cleaned = []

        seen = set()


        for note in sorted(
            chart,
            key=lambda n: (
                n["time"],
                n["lane"]
            )
        ):

            key = (
                round(
                    note["time"],
                    3
                ),
                note["lane"]
            )


            if key in seen:

                continue


            seen.add(key)

            cleaned.append(
                note
            )


        return cleaned


    # ========================================================
    # START GAME
    # ========================================================

    def start_game(self):

        if not self.media_path:

            messagebox.showwarning(
                "No Song",
                "Import a song first."
            )

            return


        if not self.chart:

            answer = messagebox.askyesno(
                "No Beatmap",
                (
                    "No beatmap has been generated yet.\n\n"
                    "Generate one now?"
                )
            )


            if answer:

                self.generate_beatmap()

            return


        # ----------------------------------------------------
        # RESET STATS
        # ----------------------------------------------------

        self.score = 0

        self.combo = 0

        self.max_combo = 0

        self.perfects = 0

        self.greats = 0

        self.goods = 0

        self.misses = 0


        for note in self.chart:

            note["hit"] = False

            note["missed"] = False

            note["holding"] = False


        self.judgement = ""

        self.judgement_until = 0.0


        self.update_key_state()


        self.running = True

        self.paused = False

        self.screen = "game"


        self.audio.play(
            self.media_path,
            0.0
        )


        self.game_loop()


    # ========================================================
    # GAME LOOP
    # ========================================================

    def game_loop(self):

        if not self.running:

            return


        if self.paused:

            return


        if self.screen != "game":

            return


        position = (
            self.audio.position()
        )


        self.update_notes(
            position
        )


        self.draw_game(
            position
        )


        if (
            self.song_length > 0
            and position >= self.song_length
        ):

            self.finish_game()

            return


        if self.audio.is_finished():

            if (
                position
                >= self.song_length - 0.2
            ):

                self.finish_game()

                return


        self.root.after(
            8,
            self.game_loop
        )


    # ========================================================
    # UPDATE NOTES
    # ========================================================

    def update_notes(
        self,
        position
    ):

        for note in self.chart:

            if note["hit"] or note["missed"]:

                continue


            if (
                position
                - note["time"]
                > MISS_WINDOW
            ):

                note["missed"] = True

                self.misses += 1

                self.combo = 0

                self.judgement = "MISS"

                self.judgement_until = (
                    time.perf_counter()
                    + 0.35
                )


    # ========================================================
    # HIT LANE
    # ========================================================

    def hit_lane(
        self,
        lane
    ):

        if not self.running:

            return


        if self.paused:

            return


        position = (
            self.audio.position()
        )


        best = None

        best_distance = MISS_WINDOW


        # ----------------------------------------------------
        # FIND CLOSEST NOTE
        # ----------------------------------------------------

        for note in self.chart:

            if note["hit"] or note["missed"]:

                continue


            if note["lane"] != lane:

                continue


            distance = abs(
                note["time"]
                - position
            )


            if distance <= best_distance:

                best_distance = distance

                best = note


        # ----------------------------------------------------
        # EMPTY PRESS
        #
        # Key still registers.
        # No score.
        # No combo break.
        # ----------------------------------------------------

        if best is None:

            self.judgement = "EMPTY"

            self.judgement_until = (
                time.perf_counter()
                + 0.20
            )

            return


        # ----------------------------------------------------
        # HIT
        # ----------------------------------------------------

        best["hit"] = True


        if (
            best_distance
            <= PERFECT_WINDOW
        ):

            self.perfects += 1

            self.score += 300

            self.combo += 1

            self.judgement = "PERFECT"


        elif (
            best_distance
            <= GREAT_WINDOW
        ):

            self.greats += 1

            self.score += 200

            self.combo += 1

            self.judgement = "GREAT"


        elif (
            best_distance
            <= GOOD_WINDOW
        ):

            self.goods += 1

            self.score += 100

            self.combo += 1

            self.judgement = "GOOD"


        else:

            self.goods += 1

            self.score += 50

            self.combo += 1

            self.judgement = "GOOD"


        self.max_combo = max(
            self.max_combo,
            self.combo
        )


        self.judgement_until = (
            time.perf_counter()
            + 0.35
        )


    # ========================================================
    # KEY PRESS
    # ========================================================

    def key_press(
        self,
        event
    ):

        key = event.keysym.lower()


        # ----------------------------------------------------
        # KEY REBIND MODE
        # ----------------------------------------------------

        if (
            self.screen
            == "keybind_wait"
        ):

            self.handle_rebind(
                event
            )

            return


        # ----------------------------------------------------
        # ESC
        # ----------------------------------------------------

        if key == "escape":

            if self.screen == "game":

                if self.paused:

                    self.resume_game()

                else:

                    self.pause_game()

            return


        # ----------------------------------------------------
        # GAME KEYS
        # ----------------------------------------------------

        if self.screen != "game":

            return


        if self.paused:

            return


        if key not in self.keys:

            return


        if self.key_down.get(
            key,
            False
        ):

            return


        self.key_down[key] = True


        lane = self.keys.index(
            key
        )


        self.hit_lane(
            lane
        )


    # ========================================================
    # KEY RELEASE
    # ========================================================

    def key_release(
        self,
        event
    ):

        key = event.keysym.lower()


        if key in self.key_down:

            self.key_down[key] = False


    # ========================================================
    # DRAW GAME
    # ========================================================

    def draw_game(
        self,
        position
    ):

        self.canvas.delete(
            "all"
        )

        self.canvas.configure(
            bg="#090910"
        )


        # ----------------------------------------------------
        # HUD
        # ----------------------------------------------------

        self.canvas.create_text(
            20,
            20,
            anchor="w",
            text=f"SCORE {self.score}",
            fill="white",
            font=(
                "Segoe UI",
                14,
                "bold"
            )
        )


        self.canvas.create_text(
            WIDTH - 20,
            20,
            anchor="e",
            text=f"COMBO {self.combo}",
            fill="white",
            font=(
                "Segoe UI",
                14,
                "bold"
            )
        )


        self.canvas.create_text(
            WIDTH // 2,
            20,
            text=self.selected_difficulty,
            fill="#bbbbcc",
            font=(
                "Segoe UI",
                10,
                "bold"
            )
        )


        # ----------------------------------------------------
        # PROGRESS
        # ----------------------------------------------------

        progress = 0.0


        if self.song_length > 0:

            progress = min(
                1.0,
                max(
                    0.0,
                    position
                    / self.song_length
                )
            )


        self.canvas.create_rectangle(
            0,
            45,
            WIDTH,
            49,
            fill="#22222f",
            outline=""
        )


        self.canvas.create_rectangle(
            0,
            45,
            WIDTH * progress,
            49,
            fill="#ffffff",
            outline=""
        )


        # ----------------------------------------------------
        # LANES
        # ----------------------------------------------------

        for lane in range(LANES):

            x1 = (
                PLAYFIELD_X
                + lane
                * (
                    LANE_WIDTH
                    + LANE_GAP
                )
            )


            x2 = (
                x1
                + LANE_WIDTH
            )


            self.canvas.create_rectangle(
                x1,
                55,
                x2,
                HEIGHT,
                fill="#11111b",
                outline="#2c2c3c"
            )


            self.canvas.create_text(
                (x1 + x2) / 2,
                HEIGHT - 28,
                text=self.keys[lane].upper(),
                fill=NOTE_COLORS[lane],
                font=(
                    "Segoe UI",
                    16,
                    "bold"
                )
            )


        # ----------------------------------------------------
        # RECEPTORS
        # ----------------------------------------------------

        for lane in range(LANES):

            x1 = (
                PLAYFIELD_X
                + lane
                * (
                    LANE_WIDTH
                    + LANE_GAP
                )
            )


            x2 = (
                x1
                + LANE_WIDTH
            )


            self.canvas.create_rectangle(
                x1,
                RECEPTOR_Y - 5,
                x2,
                RECEPTOR_Y + 5,
                fill=NOTE_COLORS[lane],
                outline="white",
                width=1
            )


        # ----------------------------------------------------
        # NOTES
        # ----------------------------------------------------

        for note in self.chart:

            if note["hit"] or note["missed"]:

                continue


            note_y = (
                RECEPTOR_Y
                - (
                    note["time"]
                    - position
                )
                * NOTE_SPEED
            )


            if (
                note_y < -NOTE_HEIGHT
                or note_y > HEIGHT
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
                + 5
            )


            x2 = (
                PLAYFIELD_X
                + lane
                * (
                    LANE_WIDTH
                    + LANE_GAP
                )
                + LANE_WIDTH
                - 5
            )


            self.canvas.create_rectangle(
                x1,
                note_y - NOTE_HEIGHT / 2,
                x2,
                note_y + NOTE_HEIGHT / 2,
                fill=NOTE_COLORS[lane],
                outline="white",
                width=2
            )


        # ----------------------------------------------------
        # JUDGEMENT
        # ----------------------------------------------------

        if (
            self.judgement
            and time.perf_counter()
            < self.judgement_until
        ):

            if self.judgement == "PERFECT":

                judgement_color = "#ffffff"

            elif self.judgement == "GREAT":

                judgement_color = "#66ccff"

            elif self.judgement == "GOOD":

                judgement_color = "#66ff99"

            elif self.judgement == "MISS":

                judgement_color = "#ff5555"

            else:

                judgement_color = "#777788"


            self.canvas.create_text(
                WIDTH // 2,
                RECEPTOR_Y + 70,
                text=self.judgement,
                fill=judgement_color,
                font=(
                    "Segoe UI",
                    20,
                    "bold"
                )
            )


        # ----------------------------------------------------
        # ACCURACY
        # ----------------------------------------------------

        self.canvas.create_text(
            WIDTH // 2,
            70,
            text=(
                f"ACC "
                f"{self.get_accuracy():.2f}%"
            ),
            fill="#888899",
            font=(
                "Segoe UI",
                9
            )
        )


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


        points = (
            self.perfects * 100
            + self.greats * 70
            + self.goods * 40
        )


        return (
            points
            / (
                total * 100
            )
            * 100
        )


    # ========================================================
    # PAUSE
    # ========================================================

    def pause_game(self):

        if not self.running:

            return


        if self.paused:

            return


        self.paused = True

        self.screen = "pause"


        self.audio.pause()


        self.show_pause_overlay()


    # ========================================================
    # PAUSE OVERLAY
    # ========================================================

    def show_pause_overlay(self):

        if self.pause_frame:

            try:
                self.pause_frame.destroy()
            except Exception:
                pass


        self.pause_frame = tk.Frame(
            self.root,
            bg="#15151f",
            highlightbackground="#555566",
            highlightthickness=2
        )


        self.pause_frame.place(
            relx=0.5,
            rely=0.5,
            anchor="center",
            width=360,
            height=390
        )


        tk.Label(
            self.pause_frame,
            text="PAUSED",
            bg="#15151f",
            fg="white",
            font=(
                "Segoe UI",
                28,
                "bold"
            )
        ).pack(
            pady=(35, 30)
        )


        tk.Button(
            self.pause_frame,
            text="RESUME",
            command=self.resume_game,
            bg="#252536",
            fg="white",
            activebackground="#41415b",
            activeforeground="white",
            relief="flat",
            font=(
                "Segoe UI",
                12,
                "bold"
            ),
            cursor="hand2"
        ).pack(
            fill="x",
            padx=55,
            pady=8,
            ipady=7
        )


        tk.Button(
            self.pause_frame,
            text="QUIT BEATMAP",
            command=self.quit_beatmap,
            bg="#252536",
            fg="white",
            activebackground="#41415b",
            activeforeground="white",
            relief="flat",
            font=(
                "Segoe UI",
                12,
                "bold"
            ),
            cursor="hand2"
        ).pack(
            fill="x",
            padx=55,
            pady=8,
            ipady=7
        )


        tk.Button(
            self.pause_frame,
            text="EXIT GAME",
            command=self.close_application,
            bg="#352020",
            fg="white",
            activebackground="#552828",
            activeforeground="white",
            relief="flat",
            font=(
                "Segoe UI",
                12,
                "bold"
            ),
            cursor="hand2"
        ).pack(
            fill="x",
            padx=55,
            pady=8,
            ipady=7
        )


    # ========================================================
    # RESUME
    # ========================================================

    def resume_game(self):

        if not self.running:

            return


        if self.pause_frame:

            try:
                self.pause_frame.destroy()
            except Exception:
                pass


            self.pause_frame = None


        self.audio.resume()


        self.paused = False

        self.screen = "game"


        self.game_loop()


    # ========================================================
    # QUIT BEATMAP
    # ========================================================

    def quit_beatmap(self):

        self.running = False

        self.paused = False

        self.audio.stop()


        if self.pause_frame:

            try:
                self.pause_frame.destroy()
            except Exception:
                pass


            self.pause_frame = None


        self.screen = "menu"

        self.draw_menu()


    # ========================================================
    # FINISH GAME
    # ========================================================

    def finish_game(self):

        if not self.running:

            return


        self.running = False

        self.paused = False

        self.audio.stop()


        if self.pause_frame:

            try:
                self.pause_frame.destroy()
            except Exception:
                pass


            self.pause_frame = None


        self.screen = "results"


        self.draw_results()


    # ========================================================
    # RESULTS
    # ========================================================

    def draw_results(self):

        self.canvas.delete(
            "all"
        )

        self.canvas.configure(
            bg="#101018"
        )


        self.canvas.create_text(
            WIDTH // 2,
            70,
            text="RESULTS",
            fill="white",
            font=(
                "Segoe UI",
                32,
                "bold"
            )
        )


        self.canvas.create_text(
            WIDTH // 2,
            125,
            text=f"SCORE  {self.score}",
            fill="white",
            font=(
                "Segoe UI",
                19,
                "bold"
            )
        )


        self.canvas.create_text(
            WIDTH // 2,
            165,
            text=(
                f"ACCURACY  "
                f"{self.get_accuracy():.2f}%"
            ),
            fill="#ccccdd",
            font=(
                "Segoe UI",
                15
            )
        )


        self.canvas.create_text(
            WIDTH // 2,
            205,
            text=(
                f"MAX COMBO  "
                f"{self.max_combo}"
            ),
            fill="#ccccdd",
            font=(
                "Segoe UI",
                15
            )
        )


        self.canvas.create_text(
            WIDTH // 2,
            270,
            text=f"PERFECT   {self.perfects}",
            fill="#ffffff",
            font=(
                "Segoe UI",
                13,
                "bold"
            )
        )


        self.canvas.create_text(
            WIDTH // 2,
            305,
            text=f"GREAT     {self.greats}",
            fill="#66ccff",
            font=(
                "Segoe UI",
                13,
                "bold"
            )
        )


        self.canvas.create_text(
            WIDTH // 2,
            340,
            text=f"GOOD      {self.goods}",
            fill="#66ff99",
            font=(
                "Segoe UI",
                13,
                "bold"
            )
        )


        self.canvas.create_text(
            WIDTH // 2,
            375,
            text=f"MISS      {self.misses}",
            fill="#ff5555",
            font=(
                "Segoe UI",
                13,
                "bold"
            )
        )


        self.make_button(
            "PLAY AGAIN",
            self.start_game,
            WIDTH // 2,
            470,
            230,
            48
        )


        self.make_button(
            "BACK TO MENU",
            self.draw_menu,
            WIDTH // 2,
            530,
            230,
            48
        )


        self.make_button(
            "EXIT GAME",
            self.close_application,
            WIDTH // 2,
            590,
            230,
            48
        )


    # ========================================================
    # CLOSE APPLICATION
    # ========================================================

    def close_application(self):

        self.running = False

        self.paused = False


        try:

            self.audio.stop()

        except Exception:

            pass


        if self.pause_frame:

            try:
                self.pause_frame.destroy()
            except Exception:
                pass


            self.pause_frame = None


        try:

            self.root.destroy()

        except Exception:

            pass


# ============================================================
# MAIN
# ============================================================

def main():

    root = tk.Tk()

    ManiaTK(root)

    root.mainloop()


if __name__ == "__main__":

    main()