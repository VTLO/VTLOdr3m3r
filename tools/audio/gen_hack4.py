# -*- coding: utf-8 -*-
"""FORCED TRANSMISSION v4 (30.0 s) — hacked military radio from "outer space", analog-horror treatment.
Layers: tuning sweep + heterodyne whistles · numbers station (forward, AM/tape-degraded) · alien command voices (English, reversed,
pitch-dropped, noise-vocoded) · FSK/frequency-hopping data bursts · 10 Hz "woodpecker" jammer · abstract inharmonic FM mass ·
sub-bass · magnetic-tape artefacts (wow/flutter, dropouts, tracking noise, print-through). Band-split mix with sidechain ducking."""
import json, subprocess, wave, numpy as np
from scipy import signal, ndimage
import pyloudnorm as pyln
from kokoro_onnx import Kokoro
import tape
SR = 32000; rng = np.random.default_rng(1313)
def sos(kind, fc, order=4): return signal.butter(order, fc, kind, fs=SR, output='sos')
def lr4(x, fc, kind): s = signal.butter(2, fc, kind, fs=SR, output='sos'); return signal.sosfilt(s, signal.sosfilt(s, x))
def band(x, lo, hi):
    y = x
    if lo: y = lr4(y, lo, 'highpass')
    if hi: y = lr4(y, hi, 'lowpass')
    return y
def env_of(x, fc=10): return np.maximum(signal.sosfilt(sos('lowpass', fc, 2), np.abs(x)), 0)
def drive(x, d): return np.tanh(d * x) / np.tanh(d)
def crush(x, bits, rate):
    k = max(1, int(SR / rate)); xs = np.repeat(x[::k], k)[:len(x)]; q = 2 ** (bits - 1); return np.round(np.clip(xs, -1, 1) * q) / q
def limiter(x, ceil_db=-1.0, half_ms=15):
    ceil = 10 ** (ceil_db / 20); h = int(half_ms * SR / 1000)
    need = np.minimum(1.0, ceil / (np.abs(x) + 1e-12)); g = ndimage.uniform_filter1d(ndimage.minimum_filter1d(need, 2 * h + 1), 2 * h + 1); return x * g
def lufs(st): return pyln.Meter(SR).integrated_loudness(st.T.astype(np.float64))
def to_lufs(st, target, ceil):
    for _ in range(4):
        st = st * 10 ** ((target - lufs(st)) / 20); st = np.stack([limiter(st[0], ceil), limiter(st[1], ceil)])
    return st
def smooth_rand(n, fc, seed):
    r = np.random.default_rng(seed); x = signal.sosfilt(sos('lowpass', fc, 2), r.standard_normal(n)); return x / (np.std(x) + 1e-9)
def place(buf, x, t0, gain=1.0):
    a = int(t0 * SR); m = min(len(x), len(buf) - a)
    if m > 0 and a >= 0: buf[a:a + m] += x[:m] * gain
D = 30.0; N = int(D * SR); T = np.arange(N) / SR
K = Kokoro('kok/kokoro-v1.0.int8.onnx', 'kok/voices-v1.0.bin')
def say(text, voice, speed):
    a, sr = K.create(text, voice=voice, speed=speed, lang='en-us'); x = np.asarray(a, dtype=np.float32); g = np.gcd(SR, sr)
    return signal.resample_poly(x, SR // g, sr // g).astype(np.float32)
def pitch(x, f): n = int(len(x) / f); return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
def vocode(x, carrier_hz, bands=14, noise=.25, seed=1):
    """Noise/pulse vocoder: speech envelope imposed on a buzzing carrier → machine voice."""
    n = len(x); t = np.arange(n) / SR; r = np.random.default_rng(seed)
    car = signal.sawtooth(2 * np.pi * np.cumsum(carrier_hz * (1 + .03 * smooth_rand(n, 6, seed))) / SR) * (1 - noise) + r.standard_normal(n) * noise
    edges = np.geomspace(180, 6500, bands + 1); out = np.zeros(n)
    for lo, hi in zip(edges[:-1], edges[1:]):
        b = signal.butter(2, [lo, hi], 'bandpass', fs=SR, output='sos')
        out += signal.sosfilt(sos('lowpass', 70, 2), np.abs(signal.sosfilt(b, x))) * signal.sosfilt(b, car)
    return (out / (np.max(np.abs(out)) + 1e-9)).astype(np.float32)

print('alien command voices…', flush=True)
PH = [("We are listening.", 6.2), ("Cease all transmission.", 10.0), ("The sky is open.", 13.6), ("Extinguish your lights.", 17.2),
      ("We have always been listening.", 21.0), ("Stand by for contact.", 25.0)]
VA = np.zeros(N, np.float32); VB = np.zeros(N, np.float32)
for i, (ph, s0) in enumerate(PH):
    m = say(ph, 'am_michael', .78)[::-1].copy()                               # reversed, male
    m = pitch(m, .62); m = vocode(m, 58 + 5 * i, noise=.22, seed=10 + i)
    m = drive(m * np.sin(2 * np.pi * (26 + 4 * i) * np.arange(len(m)) / SR) * .45 + m * .75, 3.2)
    f = say(ph, 'af_heart', .85)[::-1].copy()                                 # reversed, female, detuned
    f = pitch(f, .84); f = vocode(f, 171 + 9 * i, noise=.4, seed=30 + i); f = crush(drive(f, 2.5), 7, 9000)
    place(VA, band(m, 90, 3600), s0, 1.0); place(VB, band(f, 300, 4800), s0 + .38, .55)
FW = say("We are here.", 'am_michael', .7); FW = pitch(FW, .72); FW = band(drive(vocode(FW, 64, noise=.15, seed=77) * .9 + FW * .35, 2.2), 100, 3400)
FWB = np.zeros(N, np.float32); place(FWB, FW, 27.3, .9)                         # the only forward-sounding words, near the end

print('numbers station…', flush=True)
NUM = np.zeros(N, np.float32)
digs = "seven four niner, niner two one, three seven zero, five five eight, two niner niner, zero zero one"
for k, (grp, t0) in enumerate(zip(digs.split(', '), (2.9, 5.1, 14.3, 15.4, 19.3, 20.2))):
    x = say(grp + '.', 'af_heart', .8 + .06 * k); x = tape.wow_flutter(x, SR, rng, wow=.004, flutter=.002)
    x = band(x, 320, 2900); x = drive(x / (np.abs(x).max() + 1e-9), 2.2); x = crush(x, 8, 8000)
    place(NUM, x, t0, .75)
car = np.sin(2 * np.pi * 1000 * T) * 0.035 * ((T > 2.4) & (T < 7)); NUM += car.astype(np.float32)      # carrier tone before/under the voice

print('data bursts, hopping, woodpecker…', flush=True)
DAT = np.zeros(N, np.float32); HOP = np.zeros(N, np.float32)
def fsk(dur, baud=1200, lo=1200, hi=2200):
    nb = int(dur * baud); bits = rng.integers(0, 2, nb); f = np.repeat(np.where(bits, hi, lo), int(SR / baud))
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.hanning(len(f)) ** .3).astype(np.float32)
for t0 in (1.1, 5.9, 8.4, 11.9, 13.1, 16.3, 18.1, 19.9, 22.2, 23.6, 24.4, 26.0, 28.6):
    d = rng.uniform(.18, .7); x = band(fsk(d, baud=rng.choice([300, 1200, 2400]), lo=rng.uniform(900, 1400), hi=rng.uniform(1900, 2800)), 700, 3200)
    place(DAT, crush(x, 6, 7000), t0, .34)
for t0, n in ((4.6, 9), (12.2, 14), (17.9, 18), (23.0, 26), (26.6, 30)):                   # frequency-hopping squawks
    for j in range(n):
        f = rng.uniform(600, 4200); L = int(rng.uniform(.025, .05) * SR); tt = np.arange(L) / SR
        place(HOP, np.sin(2 * np.pi * f * tt) * np.hanning(L), t0 + j * .052, .26)
WOOD = np.zeros(N, np.float32)
for a, b in ((8.0, 11.0), (15.5, 19.0), (21.5, 26.0)):                                       # 10 Hz pulse-train jammer
    for k in range(int((b - a) * 10)):
        m = int(.012 * SR); burst = band(rng.standard_normal(m), 400, 6500) * np.hanning(m); place(WOOD, burst, a + k * .1, .7 if b - a > 3.5 else .5)

print('tuning, whistles, abstract mass, sub…', flush=True)
TUNE = np.zeros(N, np.float32); L = int(2.4 * SR); tt = np.arange(L) / SR
cen = 300 * np.exp(tt / 2.4 * np.log(3800 / 300)); ns = signal.sosfilt(sos('highpass', 200, 2), rng.standard_normal(L))
TUNE[:L] = ns * 0.35 * np.minimum(1, tt / .5) * (1 - np.clip((tt - 2.0) / .4, 0, 1))
f_a = 1800 - 1200 * tt / 2.4; het = np.sin(2 * np.pi * np.cumsum(f_a) / SR) * np.sin(2 * np.pi * np.cumsum(np.maximum(30, 900 * (1 - tt / 2.4))) / SR)
TUNE[:L] += het * .35 * np.hanning(L) ** .5
chirp = np.sin(2 * np.pi * np.cumsum(np.linspace(600, 4200, int(.09 * SR))) / SR) * np.hanning(int(.09 * SR)); place(TUNE, chirp, 2.35, .8)     # lock-on chirp
pop = band(rng.standard_normal(int(.05 * SR)), 300, 7000) * np.hanning(int(.05 * SR)); place(TUNE, pop, 2.4, 1.0)                             # squelch opens
def abstract_pass(dur, f0, seed, glide):
    n = int(dur * SR); t = np.arange(n) / SR; u = t / dur
    f = f0 * np.exp(glide * u) * (1 + .035 * smooth_rand(n, 9, seed)); ph = 2 * np.pi * np.cumsum(f) / SR
    idx = 2.5 + 5.5 * np.clip(.5 + .5 * smooth_rand(n, 1.7, seed + 1), 0, 1)
    fm = np.sin(ph + idx * (np.sin(2 * np.pi * np.cumsum(f * 1.4142) / SR) + .6 * np.sin(2 * np.pi * np.cumsum(f * 2.7183) / SR)))
    cl = sum(np.sin(2 * np.pi * np.cumsum(f * r_ * (1 + .002 * (k - 3))) / SR + k * 1.3) / (1 + .35 * k) for k, r_ in enumerate((1.0, 1.0595, 1.4983, 1.5874, 2.0, 2.1189)))
    w = np.sin((2.2 + 3.0 * u) * (fm * .9 + cl * .55)) * (.35 + .65 * np.clip(smooth_rand(n, 14, seed + 2) * 1.2 + .55, 0, 1))
    w *= 1 - .55 * (.5 + .5 * np.sin(2 * np.pi * (11 + 40 * u ** 2) * t)); w *= np.minimum(1, t / .5) * np.minimum(1, (dur - t) / .5)
    return signal.sosfilt(sos('bandpass', [max(140, f0 * .5), min(6500, f0 * 9)], 2), w).astype(np.float32)
ABL = np.zeros(N, np.float32); ABR = np.zeros(N, np.float32)
for k, (c, dur, f0, gl, g) in enumerate(((9.0, 7.0, 600, -.9, .5), (17.0, 7.0, 860, -1.1, .55), (24.5, 6.0, 500, -1.3, .65), (27.6, 2.8, 1200, -1.6, .7))):
    w = abstract_pass(dur, f0, 900 + k * 13, gl); a = max(0, int((c - dur / 2) * SR)); m = min(len(w), N - a)
    ang = (np.sin(np.cumsum(.35 + 1.8 * (np.arange(m) / SR / dur) ** 2) / SR * 2 * np.pi) + 1) * np.pi / 4
    ABL[a:a + m] += w[:m] * np.cos(ang) * g; ABR[a:a + m] += np.roll(w[:m], 11 + 3 * k) * np.sin(ang) * g
SUB = band(np.sin(2 * np.pi * (38 + 6 * np.sin(2 * np.pi * .21 * T)) * T) * (.25 + .75 * np.clip((T - 4) / 20, 0, 1)), 26, 95)
GR = band(signal.sosfilt(sos('bandpass', [140, 720], 2), rng.standard_normal(N)) * (.5 + .5 * np.sin(2 * np.pi * 7.3 * T)) * (.35 + .65 * np.clip((T - 5) / 16, 0, 1)), 130, 750)
STAT = [band(rng.standard_normal(N), 3500, 12000) * (.035 + .05 * np.clip((T - 2) / 25, 0, 1) + .02 * np.sin(2 * np.pi * .6 * T + k)) for k in (0, 2)]
RISER = band(signal.sosfilt(sos('bandpass', [200, 6000], 2), rng.standard_normal(N)) * np.clip((T - 27.0) / 3.0, 0, 1) ** 2.2 * .6, 250, 6500)

print('mix by bands + tape…', flush=True)
vox = VA + .8 * VB + NUM * .8; duck = np.clip(env_of(vox, 12) / (np.percentile(env_of(vox, 12), 99) + 1e-9), 0, 1); gd = 1 - .45 * duck
L1 = VA + VB * .8 + NUM + FWB + ABL * gd + TUNE + DAT * gd + HOP * gd + WOOD * gd + GR * .5 * (1 - .5 * duck) + SUB * .6 + STAT[0] * gd + RISER
R1 = VA + VB * .8 + NUM + FWB + ABR * gd + TUNE + DAT * gd + HOP * gd + WOOD * gd + GR * .5 * (1 - .5 * duck) + SUB * .6 + STAT[1] * gd + RISER
R1 = np.roll(R1, 13)
def tape_chain(c, seed):
    r = np.random.default_rng(seed)
    c = tape.wow_flutter(c, SR, r, wow=.0018 + .0030 * np.clip((T - 8) / 18, 0, 1).mean(), flutter=.0009)
    c = tape.dropouts(c, SR, r, 11, dur=(.03, .14), depth=(.02, .25))
    c = c + tape.tracking_noise(N, SR, r, .02) * (np.clip(np.sin(2 * np.pi * .23 * T + seed) , 0, 1) ** 3 * 2.4 + .1) + tape.hiss(N, SR, r, .012)
    c = tape.print_through(c, SR, .5, .06); return tape.tape_eq(c, SR, 9000, 40)
fade = np.ones(N); fade[-int(.02 * SR):] = np.linspace(1, 0, int(.02 * SR)); fade[:int(.004 * SR)] = np.linspace(0, 1, int(.004 * SR))
st = np.stack([tape_chain(L1, 5) * fade, tape_chain(R1, 6) * fade]).astype(np.float32)
st = np.stack([signal.sosfilt(sos('highpass', 24, 2), c) for c in st]).astype(np.float32)
st = to_lufs(st, -9.5, -1.7)
pcm = (np.clip(st.T, -1, 1) * 32767).astype('<i2')
with wave.open('wav4/hack.wav', 'wb') as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', 'wav4/hack.wav', '-ar', str(SR), '-codec:a', 'libmp3lame', '-b:a', '128k', '-joint_stereo', '1', 'out4/hack.mp3'], check=True)
print('hack v4: LUFS', round(lufs(st), 1), 'peak', round(20 * np.log10(np.abs(st).max()), 2), 'dBFS', flush=True)
