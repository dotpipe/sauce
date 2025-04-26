import tkinter as tk
from tkinter import filedialog
import pygame
import threading
import time
import numpy as np
import json

# Initialize Pygame Mixer
pygame.mixer.init(frequency=44100, size=-16, channels=2)

# Constants
SAMPLE_RATE = 44100
DURATION = 0.5
NUM_VOICES = 4
NUM_BANDS = 6
STEP_COUNT = 32

def apply_eq(samples, eq_values):
    """Apply a simple EQ by scaling different frequency bands."""
    samples_fft = np.fft.rfft(samples)
    freqs = np.fft.rfftfreq(len(samples), d=1/SAMPLE_RATE)

    band_limits = np.linspace(0, np.max(freqs), len(eq_values) + 1)

    for i in range(len(eq_values)):
        band = (freqs >= band_limits[i]) & (freqs < band_limits[i+1])
        samples_fft[band] *= eq_values[i]

    samples_eq = np.fft.irfft(samples_fft)
    return samples_eq

def generate_pygame_tone(frequency1=440, frequency2=660, duration_ms=500, volume_db=-10.0, distortion_amount=0.0, eq=None, left_vol=0.5, right_vol=0.5):
    t = np.arange(SAMPLE_RATE * duration_ms / 1000.0) / SAMPLE_RATE
    samples1 = np.sin(2 * np.pi * frequency1 * t)
    samples2 = np.sin(2 * np.pi * frequency2 * t)
    samples = (samples1 + samples2) / 2

    if eq is not None:
        samples = apply_eq(samples, eq)

    if distortion_amount > 0.0:
        gain = 1 + distortion_amount * 10
        samples = samples * gain
        samples = np.tanh(samples)

    samples = samples * (2**15 - 1)
    samples = np.clip(samples, -32768, 32767)

    left = np.int16(samples * left_vol)
    right = np.int16(samples * right_vol)
    stereo_samples = np.column_stack((left, right))

    sound = pygame.sndarray.make_sound(stereo_samples)
    sound.set_volume(10 ** (volume_db / 20))
    return sound

def check_sound_system():
    try:
        tone = pygame.sndarray.make_sound(np.ones((int(SAMPLE_RATE * DURATION), 2), dtype=np.int16))
        tone.play()
        pygame.time.delay(100)
        print("Sound system is working!")
        return True
    except pygame.error:
        print("Error: Sound system not available.")
        return False

class MusicSynthesizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Modular Synth Rack")
        self.voice_data = []
        self.voices = []
        self.tempo = tk.IntVar(value=120)
        self.running = False

        if not check_sound_system():
            self.root.quit()
            return

        self.create_ui()
        self.sequencer_thread = None

    def create_ui(self):
        top = tk.Frame(self.root)
        top.pack(pady=5)

        tk.Label(top, text="Tempo (BPM)").pack(side=tk.LEFT)
        tk.Scale(top, from_=60, to=240, variable=self.tempo, orient=tk.HORIZONTAL).pack(side=tk.LEFT)

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="Play", command=self.start_sequencer).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Stop", command=self.stop_sequencer).pack(side=tk.LEFT, padx=5)

        tk.Button(btn_frame, text="Save Pattern", command=self.save_pattern).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Load Pattern", command=self.load_pattern).pack(side=tk.LEFT, padx=5)

        frame = tk.Frame(self.root)
        frame.pack()

        for i in range(NUM_VOICES):
            voice_frame = tk.LabelFrame(frame, text=f"Voice {i+1}", padx=5, pady=5)
            voice_frame.grid(row=0, column=i, padx=5)
            self.create_voice_controls(voice_frame)

        self.seq_frame = tk.Frame(self.root)
        self.seq_frame.pack(pady=10)
        self.create_sequencer()

    def create_voice_controls(self, parent):
        sliders = {}
        labels = ["A", "D", "S", "R", "P1", "P2", "V", "G", "Loop"]

        for i, label in enumerate(labels):
            var = tk.DoubleVar(value=0.1 if label in "ADS" else 0.5)
            if label == "P1" or label == "P2":
                var.set(440)
            elif label == "Loop":
                var.set(STEP_COUNT)

            tk.Label(parent, text=label).grid(row=0, column=i)
            max_val = 880 if label in ["P1", "P2"] else STEP_COUNT if label == "Loop" else 1.0
            res = 1 if label in ["P1", "P2", "Loop"] else 0.01
            slider = tk.Scale(parent, variable=var, from_=0.0, to=max_val, resolution=res, orient=tk.VERTICAL)
            slider.grid(row=1, column=i)
            sliders[label] = var

        eq = [tk.DoubleVar(value=0.5) for _ in range(NUM_BANDS)]
        for j in range(NUM_BANDS):
            tk.Label(parent, text=f"EQ{j+1}").grid(row=2, column=j)
            tk.Scale(parent, variable=eq[j], from_=0.0, to=1.0, resolution=0.01, orient=tk.VERTICAL).grid(row=3, column=j)

        tk.Label(parent, text="Dist").grid(row=2, column=NUM_BANDS)
        distortion = tk.DoubleVar(value=0.0)
        tk.Scale(parent, variable=distortion, from_=0.0, to=1.0, resolution=0.01, orient=tk.VERTICAL).grid(row=3, column=NUM_BANDS)

        tk.Label(parent, text="Left").grid(row=2, column=NUM_BANDS + 1)
        tk.Label(parent, text="Right").grid(row=2, column=NUM_BANDS + 2)

        left_volume = tk.DoubleVar(value=0.5)
        right_volume = tk.DoubleVar(value=0.5)

        tk.Scale(parent, variable=left_volume, from_=0.0, to=1.0, resolution=0.01, orient=tk.VERTICAL).grid(row=3, column=NUM_BANDS + 1)
        tk.Scale(parent, variable=right_volume, from_=0.0, to=1.0, resolution=0.01, orient=tk.VERTICAL).grid(row=3, column=NUM_BANDS + 2)

        self.voices.append({
            "params": sliders,
            "eq": eq,
            "left_vol": left_volume,
            "right_vol": right_volume,
            "distortion": distortion
        })

    def save_pattern(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".json",
                                                filetypes=[("JSON files", "*.json")])
        if not file_path:
            return

        data = {
            "sequence": [[var.get() for var in row] for row in self.sequence],
            "voices": []
        }

        for voice in self.voices:
            voice_data = {
                "params": {k: v.get() for k, v in voice["params"].items()},
                "eq": [eqv.get() for eqv in voice["eq"]],
                "left_vol": voice["left_vol"].get(),
                "right_vol": voice["right_vol"].get(),
                "distortion": voice["distortion"].get()
            }
            data["voices"].append(voice_data)

        with open(file_path, "w") as f:
            json.dump(data, f)

    def load_pattern(self):
        file_path = filedialog.askopenfilename(defaultextension=".json",
                                            filetypes=[("JSON files", "*.json")])
        if not file_path:
            return

        with open(file_path, "r") as f:
            data = json.load(f)

        for i, row in enumerate(data["sequence"]):
            for j, val in enumerate(row):
                if i < len(self.sequence) and j < len(self.sequence[i]):
                    self.sequence[i][j].set(val)

        for i, voice_data in enumerate(data["voices"]):
            if i < len(self.voices):
                for k, v in voice_data["params"].items():
                    if k in self.voices[i]["params"]:
                        self.voices[i]["params"][k].set(v)
                for j, eqv in enumerate(voice_data["eq"]):
                    if j < len(self.voices[i]["eq"]):
                        self.voices[i]["eq"][j].set(eqv)
                self.voices[i]["left_vol"].set(voice_data["left_vol"])
                self.voices[i]["right_vol"].set(voice_data["right_vol"])
                self.voices[i]["distortion"].set(voice_data["distortion"])

    def create_sequencer(self):
        self.sequence = []
        for i in range(NUM_VOICES):
            row = []
            for j in range(STEP_COUNT):
                var = tk.IntVar()
                cb = tk.Checkbutton(self.seq_frame, variable=var)
                cb.grid(row=i, column=j)
                row.append(var)
            self.sequence.append(row)

    def start_sequencer(self):
        if not self.running:
            self.running = True
            self.sequencer_thread = threading.Thread(target=self.run_sequence, daemon=True)
            self.sequencer_thread.start()

    def stop_sequencer(self):
        self.running = False

    def run_sequence(self):
        global_step = 0
        while self.running:
            interval = 60 / self.tempo.get() / 4
            for i, voice in enumerate(self.voices):
                voice_loop = int(voice["params"]["Loop"].get())
                step_index = global_step % voice_loop
                if step_index < STEP_COUNT and self.sequence[i][step_index].get():
                    self.play_voice(i)
            global_step += 1
            time.sleep(interval)

    def apply_adsr(self, samples, attack, decay, sustain, release, duration, sample_rate):
        total_samples = int(duration * sample_rate)

        # Limit parameters
        attack = max(0.001, min(attack, 0.9))
        decay = max(0.001, min(decay, 0.9))
        release = max(0.001, min(release, 0.9))
        sustain = max(0.0, min(sustain, 1.0))

        # Normalize if attack+decay+release > 1
        total_adsr = attack + decay + release
        if total_adsr >= 1.0:
            factor = 0.99 / total_adsr
            attack *= factor
            decay *= factor
            release *= factor

        attack_samples = int(attack * total_samples)
        decay_samples = int(decay * total_samples)
        release_samples = int(release * total_samples)

        sustain_samples = total_samples - (attack_samples + decay_samples + release_samples)
        if sustain_samples < 0:
            sustain_samples = 0

        # Envelope
        envelope = np.zeros(total_samples)

        if attack_samples > 0:
            envelope[:attack_samples] = np.linspace(0, 1, attack_samples, endpoint=False)
        if decay_samples > 0:
            envelope[attack_samples:attack_samples + decay_samples] = np.linspace(1, sustain, decay_samples, endpoint=False)
        if sustain_samples > 0:
            envelope[attack_samples + decay_samples:attack_samples + decay_samples + sustain_samples] = sustain
        if release_samples > 0:
            envelope[attack_samples + decay_samples + sustain_samples:] = np.linspace(sustain, 0, release_samples)

        # Apply envelope
        samples = samples * envelope[:, np.newaxis]

        # Clip between -1.0 and 1.0 to prevent overflow noise
        samples = np.clip(samples, -1.0, 1.0)

        # Convert to int16
        samples = (samples * 32767).astype(np.int16)

        return samples

# After applying ADSR:
    def play_voice(self, instrument_index):
        if instrument_index >= len(self.voices):
            return
        voice = self.voices[instrument_index]
        params = voice["params"]

        freq1 = params["P1"].get()
        freq2 = params["P2"].get()
        vol = params["V"].get()
        gain = params["G"].get()
        duration_ms = 500

        total_volume_db = -40 + (vol + gain) * 20
        eq_values = [eq.get() for eq in voice["eq"]]
        distortion = voice["distortion"].get()
        left_vol = voice["left_vol"].get()
        right_vol = voice["right_vol"].get()

        # Get ADSR parameters from voice controls
        attack = params["A"].get()  # Attack
        decay = params["D"].get()   # Decay
        sustain = params["S"].get()  # Sustain
        release = params["R"].get() # Release

        # Generate tone and apply ADSR envelope
        tone = generate_pygame_tone(freq1, freq2, duration_ms, total_volume_db,
                                    distortion_amount=distortion, eq=eq_values,
                                    left_vol=left_vol, right_vol=right_vol)
        
        # Apply ADSR envelope
        samples = pygame.sndarray.array(tone)
        samples = np.copy(samples)
        samples = self.apply_adsr(samples, attack, decay, sustain, release, duration_ms / 1000.0, SAMPLE_RATE)


        # Play the tone with ADSR applied
        tone = pygame.sndarray.make_sound(samples)
        tone.play()

if __name__ == "__main__":
    root = tk.Tk()
    app = MusicSynthesizerApp(root)
    root.mainloop()
