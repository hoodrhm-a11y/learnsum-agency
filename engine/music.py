"""Original background music generator (no copyright issues). Calm, upbeat, no whooshes."""
import numpy as np
from scipy.signal import butter, sosfilt
from scipy.io import wavfile

SR = 44100
PROGRESSIONS = [
    ([[53, 57, 60, 64], [52, 55, 59, 62], [50, 53, 57, 60], [48, 52, 55, 59]], [41, 40, 38, 36]),  # Fmaj7 Em7 Dm7 Cmaj7
    ([[48, 52, 55, 59], [45, 48, 52, 55], [50, 53, 57, 60], [55, 59, 62, 65]], [36, 33, 38, 43]),  # Cmaj7 Am7 Dm7 G7
    ([[57, 60, 64, 67], [53, 57, 60, 64], [48, 52, 55, 59], [55, 59, 62, 66]], [45, 41, 36, 43]),  # Am7 Fmaj7 Cmaj7 G
]


def make(dur, out_wav, seed=0, intro=3.0):
    rng = np.random.default_rng(seed)
    bpm = [88, 92, 96][seed % 3]
    B = 60 / bpm; BAR = 4 * B
    N = int(SR * dur)
    mix = np.zeros((N, 2))
    lp = lambda x, f: sosfilt(butter(2, f, "low", fs=SR, output="sos"), x)
    hp = lambda x, f: sosfilt(butter(2, f, "high", fs=SR, output="sos"), x)
    bp = lambda x, a, b: sosfilt(butter(2, [a, b], "band", fs=SR, output="sos"), x)
    note = lambda n: 440 * 2 ** ((n - 69) / 12)

    def add(sig, t, g=1.0, pan=0.0):
        i = int(t * SR)
        if i >= N or i < 0: return
        sig = sig[: N - i]
        l, r = np.cos((pan + 1) * np.pi / 4) * 1.414, np.sin((pan + 1) * np.pi / 4) * 1.414
        mix[i:i + len(sig), 0] += sig * g * l; mix[i:i + len(sig), 1] += sig * g * r

    def keys(freqs, d):
        t = np.arange(int(d * SR)) / SR
        out = np.zeros_like(t)
        for f in freqs:
            out += np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t) * np.exp(-t * 3) + 0.12 * np.sin(6 * np.pi * f * t) * np.exp(-t * 5)
        return out * (1 - np.exp(-t * 60)) * np.exp(-t * 0.9) * (1 + 0.12 * np.sin(2 * np.pi * 4.5 * t)) / len(freqs)

    def kick():
        t = np.arange(int(0.4 * SR)) / SR
        return np.sin(2 * np.pi * np.cumsum(48 + 90 * np.exp(-t * 30)) / SR) * np.exp(-t * 9)

    def rim():
        t = np.arange(int(0.12 * SR)) / SR
        return (bp(rng.standard_normal(len(t)), 1500, 4000) * 0.5 + np.sin(2 * np.pi * 820 * t) * 0.4) * np.exp(-t * 45)

    def hat():
        t = np.arange(int(0.05 * SR)) / SR
        return hp(rng.standard_normal(len(t)), 8000) * np.exp(-t * 90) * 0.3

    prog, roots = PROGRESSIONS[seed % len(PROGRESSIONS)]
    for b in range(int(np.ceil(dur / BAR))):
        t0 = b * BAR
        ch = [note(n) for n in prog[b % 4]]
        add(lp(keys(ch, BAR * 0.55), 3000), t0, 0.33, -0.15)
        add(lp(keys(ch, BAR * 0.45), 3000), t0 + 2.5 * B, 0.22, 0.15)
        tb = np.arange(int(BAR * SR)) / SR
        add(np.sin(2 * np.pi * note(roots[b % 4]) * tb) * np.minimum(1, tb * 40) * np.exp(-tb * 0.6), t0, 0.32)
    for k in range(int(dur / B) + 1):
        t0 = k * B
        if t0 > dur - 1.6: break
        on = t0 >= intro - 0.01
        if on:
            if k % 4 in (0, 2): add(kick(), t0, 0.55)
            if k % 8 == 7: add(kick(), t0 + B / 2, 0.45)
            if k % 2 == 1: add(rim(), t0, 0.35, 0.1)
        add(hat(), t0, 0.35 if on else 0.18, 0.3)
        add(hat(), t0 + B / 2 + 0.03, 0.25 if on else 0.12, 0.3)
    noise = lp(rng.standard_normal(N), 5000) * 0.012
    mix[:, 0] += noise; mix[:, 1] += noise
    m = np.tanh(mix / (np.abs(mix).max() + 1e-9) * 1.2) / np.tanh(1.2)
    fo = int(1.5 * SR); m[-fo:] *= np.linspace(1, 0, fo)[:, None]
    fi = int(0.05 * SR); m[:fi] *= np.linspace(0, 1, fi)[:, None]
    wavfile.write(out_wav, SR, (m * 0.85 * 32767).astype(np.int16))
