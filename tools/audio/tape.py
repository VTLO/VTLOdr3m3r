"""Analog magnetic-tape artefacts (wow/flutter, dropouts, tape stop, tracking noise, print-through, hiss) — shared by voices, hack track and ambience."""
import numpy as np
from scipy import signal
def sos(kind, fc, sr, order=4): return signal.butter(order, fc, kind, fs=sr, output='sos')
def wow_flutter(x, sr, r, wow=.0016, flutter=.0007, wow_hz=(.45, 1.3), fl_hz=(7, 13)):
    """Time-varying playback speed: slow wow + fast flutter (resampling at a modulated rate)."""
    n = len(x); t = np.arange(n) / sr
    m = wow * np.sin(2*np.pi*r.uniform(*wow_hz)*t + r.uniform(0, 6.28)) + flutter * np.sin(2*np.pi*r.uniform(*fl_hz)*t + r.uniform(0, 6.28))
    m += wow * .5 * signal.sosfilt(sos('lowpass', 2, sr, 2), r.standard_normal(n)) / 0.3
    pos = np.cumsum(1 + m); pos = np.clip(pos - pos[0], 0, n - 1)
    return np.interp(pos, np.arange(n), x).astype(np.float32)
def dropouts(x, sr, r, count, dur=(.02, .09), depth=(.05, .3), hf_loss=True):
    """Oxide dropouts: level dips + treble loss, sometimes with a click at the edge."""
    x = x.copy(); n = len(x)
    for _ in range(count):
        m = int(r.uniform(*dur) * sr); a = int(r.uniform(0, max(1, n - m - 1)))
        if a + m >= n: continue
        g = r.uniform(*depth); seg = x[a:a+m]
        if hf_loss: seg = signal.sosfilt(sos('lowpass', 900, sr, 2), seg)
        w = np.hanning(m) ** .5; x[a:a+m] = x[a:a+m] * (1 - w) + seg * g * w
        if r.random() < .5: x[a] += r.uniform(-.25, .25)
    return x
def tape_stop(x, sr, at, dur):
    """Motor slows to a stop: pitch and speed slur down."""
    n = len(x); a = int(at * sr); m = int(dur * sr)
    if a + m > n: m = n - a
    s = np.linspace(1, 0.05, m) ** 1.6; pos = a + np.cumsum(s); pos = np.clip(pos, 0, n - 1)
    out = x.copy(); out[a:a+m] = np.interp(pos, np.arange(n), x) * np.linspace(1, .2, m); out[a+m:] *= 0; return out.astype(np.float32)
def tracking_noise(n, sr, r, level=.05):
    """VHS tracking / head-switch noise: gritty band-limited buzz with 50 Hz banding."""
    t = np.arange(n) / sr
    b = signal.sosfilt(sos('bandpass', [700, 5200], sr, 2), r.standard_normal(n))
    return (b * (.4 + .6 * np.abs(np.sin(2*np.pi*50*t))) * level).astype(np.float32)
def hiss(n, sr, r, level=.012):
    return (signal.sosfilt(sos('highpass', 2500, sr, 2), r.standard_normal(n)) * level).astype(np.float32)
def print_through(x, sr, delay=.45, gain=.05):
    """Magnetic bleed between tape layers: faint pre-echo."""
    d = int(delay * sr); y = x.copy(); y[:-d] += signal.sosfilt(sos('lowpass', 1500, sr, 2), x[d:]) * gain; return y
def tape_eq(x, sr, lp=6500, hp=60):
    x = signal.sosfilt(sos('highpass', hp, sr, 2), x); x = signal.sosfilt(sos('lowpass', lp, sr, 3), x)
    return np.tanh(1.15 * x) / np.tanh(1.15)
