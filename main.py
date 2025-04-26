import tkinter as tk
from tkinter import ttk
import pygame
import threading
import time
import numpy as np

# Initialize Pygame Mixer
pygame.mixer.init(frequency=44100, size=-16, channels=2)  # Changed to stereo (2 channels)

# Constants
SAMPLE_RATE = 44100
DURATION = 0.5
NUM_VOICES = 4
NUM_BANDS = 6
STEP_COUNT = 16  # Updated to 32 steps

def generate_pygame_tone(frequency=440, duration_ms=500, volume_db=-10.0):
    # Generate a mono sine wave
    samples = np.sin(2 * np.pi * frequency * np.arange(SAMPLE_RATE * duration_ms / 1000.0) / SAMPLE_RATE)
    samples = np.int16(samples * (2**15 - 1))  # Convert to 16-bit PCM

    # Convert to stereo by duplicating the mono samples in two channels (left and right)
    stereo_samples = np.column_stack((samples, samples))  # Create 2D array for stereo
    
    # Apply volume
    sound = pygame.sndarray.make_sound(stereo_samples)
    sound.set_volume(10 ** (volume_db / 20))  # Apply volume control (in dB)
    return sound

def check_sound_system():
    try:
        # Ensure the size is an integer for numpy ones
        tone = pygame.sndarray.make_sound(np.ones((int(SAMPLE_RATE * DURATION), 2), dtype=np.int16))  # Stereo array
        tone.play()
        pygame.time.delay(1000)  # Wait 1 second to test sound
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
        labels = ["A", "D", "S", "R", "P", "V", "G", "Loop"]

        for i, label in enumerate(labels):
            var = tk.DoubleVar(value=0.1 if label in "ADS" else 0.5)
            if label == "P":
                var.set(440)
            elif label == "V" or label == "G":
                var.set(0.5)
            elif label == "Loop":
                var.set(STEP_COUNT)

            tk.Label(parent, text=label).grid(row=0, column=i)
            max_val = 880 if label == "P" else STEP_COUNT if label == "Loop" else 1.0
            res = 1 if label in ["P", "Loop"] else 0.01
            slider = tk.Scale(parent, variable=var, from_=0.0, to=max_val, resolution=res, orient=tk.VERTICAL)
            slider.grid(row=1, column=i)
            sliders[label] = var

        eq = [tk.DoubleVar(value=0.5) for _ in range(NUM_BANDS)]
        for j in range(NUM_BANDS):
            tk.Label(parent, text=f"EQ{j+1}").grid(row=2, column=j)
            tk.Scale(parent, variable=eq[j], from_=0.0, to=1.0, resolution=0.01, orient=tk.VERTICAL).grid(row=3, column=j)

        self.voices.append({"params": sliders, "eq": eq})

        # Create horizontal sliders for Left and Right volume controls
        tk.Label(parent, text="Left").grid(row=NUM_BANDS + len(eq), column=0, padx=5, pady=5)
        tk.Label(parent, text="Right").grid(row=NUM_BANDS + len(eq), column=1, padx=5, pady=5)

        left_volume = tk.DoubleVar(value=0.5)
        right_volume = tk.DoubleVar(value=0.5)

        left_vol_slider = tk.Scale(parent, variable=left_volume, from_=0.0, to=1.0, resolution=0.01, orient=tk.VERTICAL)
        right_vol_slider = tk.Scale(parent, variable=right_volume, from_=0.0, to=1.0, resolution=0.01, orient=tk.VERTICAL)

        left_vol_slider.grid(row=NUM_BANDS + len(eq) + 1, column=0, padx=5)
        right_vol_slider.grid(row=NUM_BANDS + len(eq) + 1, column=1, padx=5)

        self.voices.append({"params": sliders, "eq": eq, "left_vol": left_volume, "right_vol": right_volume})


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
            interval = 60 / self.tempo.get() / 4  # quarter beat
            for i, voice in enumerate(self.voices):
                voice_loop = int(voice["params"]["Loop"].get())
                step_index = global_step % voice_loop
                if step_index < STEP_COUNT and self.sequence[i][step_index].get():
                    self.play_voice(i)
            global_step += 1
            time.sleep(interval)

    def play_voice(self, instrument_index):
        if instrument_index >= len(self.voices):
            return
        instrument_data = self.voices[instrument_index]["params"]

        freq = instrument_data["P"].get()
        vol = instrument_data["V"].get()
        gain = instrument_data["G"].get()
        duration_ms = 500

        total_volume_db = -40 + (vol + gain) * 20
        
        # Set stereo balance (e.g., left volume = 80% of total volume, right volume = 120%)
        left_volume = total_volume_db - 5  # Left channel slightly quieter
        right_volume = total_volume_db + 5  # Right channel slightly louder
        
        # Generate tone with stereo configuration
        tone = generate_pygame_tone(freq, duration_ms, left_volume, stereo=True)

        # Play tone
        tone.play()

if __name__ == '__main__':
    root = tk.Tk()
    app = MusicSynthesizerApp(root)
    root.mainloop()
