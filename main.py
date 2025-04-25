import tkinter as tk
from tkinter import ttk
import pygame
import threading
import time
import numpy as np

# Initialize Pygame Mixer
pygame.mixer.init(frequency=44100, size=-16, channels=1)

# Constants
SAMPLE_RATE = 44100
DURATION = 0.5
NUM_VOICES = 4
NUM_BANDS = 6

def generate_pygame_tone(frequency=440, duration_ms=500, volume_db=-10.0):
    """
    Generates a tone using pygame's mixer and returns a Sound object.
    """
    # Generate a sine wave tone using numpy for the raw data
    samples = np.sin(2 * np.pi * frequency * np.arange(SAMPLE_RATE * duration_ms / 1000.0) / SAMPLE_RATE)
    
    # Convert the samples to 16-bit PCM format
    samples = np.int16(samples * (2**15 - 1))  # Max value for 16-bit
    sound = pygame.sndarray.make_sound(samples)
    
    # Apply volume adjustment (gain) in dB
    sound.set_volume(10 ** (volume_db / 20))
    
    return sound

def check_sound_system():
    try:
        # Try to play a simple sound to test the system
        tone = pygame.sndarray.make_sound(np.ones(int(SAMPLE_RATE * DURATION), dtype=np.int16))  # A basic 1-second tone
        tone.play()
        time.sleep(1)  # Wait for the sound to play for 1 second
        print("Sound system is working!")
        return True
    except pygame.error:
        print("Error: Sound system not available.")
        return False

class Voice:
    def __init__(self, pitch=440, attack=0.1, decay=0.1, sustain=0.5, release=0.1, volume=0.5, gain=0.5):
        self.pitch = pitch
        self.attack = attack
        self.decay = decay
        self.sustain = sustain
        self.release = release
        self.volume = volume
        self.gain = gain

    def apply_adsr(self, tone):
        # Apply ADSR envelope to the tone
        tone = self.apply_adsr_envelope(tone, self.attack, self.decay, self.sustain, self.release)
        return tone
    
    def apply_adsr_envelope(self, audio, attack, decay, sustain, release):
        # This is a placeholder to modify sound based on ADSR values
        return audio  # For now, just returning the tone without actual ADSR envelope applied.

class MusicSynthesizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Modular Synth Rack")
        self.voice_data = []

        self.voices = []
        self.tempo = tk.IntVar(value=120)
        self.running = False

        # Check the sound system immediately on load
        if not check_sound_system():
            self.root.quit()  # Quit the program if the sound system isn't working
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
        labels = ["A", "D", "S", "R", "P", "V", "G", "TS"]  # ADSR, Pitch, Volume, Gain, Time Signature

        for i, label in enumerate(labels):
            var = tk.DoubleVar(value=0.1 if label in "ADS" else 0.5)
            if label == "P":
                var.set(440)
            elif label == "V" or label == "G":
                var.set(0.5)
            elif label == "TS":
                var.set(4)

            tk.Label(parent, text=label).grid(row=0, column=i)
            slider = tk.Scale(parent, variable=var, from_=0.0, to=1.0 if label != "P" and label != "TS" else 880 if label == "P" else 12,
                              resolution=0.01 if label != "P" and label != "TS" else 1, orient=tk.VERTICAL)
            slider.grid(row=1, column=i)
            sliders[label] = var

        eq = [tk.DoubleVar(value=0.5) for _ in range(NUM_BANDS)]
        for j in range(NUM_BANDS):
            tk.Label(parent, text=f"EQ{j+1}").grid(row=2, column=j)
            tk.Scale(parent, variable=eq[j], from_=0.0, to=1.0, resolution=0.01, orient=tk.VERTICAL).grid(row=3, column=j)

        self.voices.append({"params": sliders, "eq": eq})

    def create_sequencer(self):
        self.sequence = []
        for i in range(NUM_VOICES):
            row = []
            for j in range(16):
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
        step = 0
        while self.running:
            interval = 60 / self.tempo.get() / 4  # quarter beat interval
            for i, voice in enumerate(self.voices):
                if self.sequence[i][step % 16].get() == 1:
                    self.play_voice(i)
            step += 1
            time.sleep(interval)

    def play_voice(self, instrument_index):
        if instrument_index >= len(self.voices):
            return
        voice = self.voices[instrument_index]
        params = voice["params"]

        # Read the control parameters
        freq = params["P"].get()
        vol = params["V"].get()
        gain = params["G"].get()
        attack = params["A"].get()
        decay = params["D"].get()
        sustain = params["S"].get()
        release = params["R"].get()
        duration_ms = 500  # Adjustable duration

        # Apply the ADSR and play the tone
        voice_obj = Voice(pitch=freq, attack=attack, decay=decay, sustain=sustain, release=release, volume=vol, gain=gain)
        tone = generate_pygame_tone(freq, duration_ms, vol)
        tone_with_adsr = voice_obj.apply_adsr(tone)
        tone_with_adsr.play()

if __name__ == '__main__':
    root = tk.Tk()
    app = MusicSynthesizerApp(root)
    root.mainloop()
