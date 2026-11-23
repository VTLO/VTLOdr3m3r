# -*- coding: utf-8 -*-
"""
Scenario sound #2 — "interference" (11.0 s), played right after the forced transmission.
Loud radio interference: broadband static + crackle, TDMA-style buzz, heterodyne whistles, data-burst chirps,
stutter dropouts; full level until 8.5 s, then fades to silence (the screen fades to black) before the show resumes.
Needs only numpy + ffmpeg.   Usage: python3 gen_interference.py [out.mp3]
"""
import sys, wave, subprocess, numpy as np

SR, D = 32000, 11.0
N = int(SR * D); t = np.arange(N) / SR
rng = np.random.default_rng(2027)
out = sys.argv[1] if len(sys.argv) > 1 else 'interference.mp3'

def onepole_lp(x, fc):                       # cheap low-pass (FFT brick-wall, smooth enough for noise shaping)
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR); X *= 1 / np.sqrt(1 + (f / fc) ** 4); return np.fft.irfft(X, len(x))
def bandpass(x, lo, hi):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= (1 / np.sqrt(1 + (lo / np.maximum(f, 1)) ** 4)) * (1 / np.sqrt(1 + (f / hi) ** 4)); return np.fft.irfft(X, len(x))
def smooth_gate(n, rate, duty, seed):
    r = np.random.default_rng(seed); g = np.zeros(n); i = 0
    while i < n:
        on = int(r.exponential(duty / rate) * SR) + 1; off = int(r.exponential((1 - duty) / rate) * SR) + 1
        g[i:i + on] = 1; i += on + off
    return onepole_lp(g, 180)
def norm(x): return x / (np.max(np.abs(x)) + 1e-9)

# 1. broadband static (the bed), slowly breathing
static = norm(bandpass(rng.standard_normal(N), 180, 9000)) * (.75 + .25 * np.sin(2 * np.pi * .7 * t))
# 2. crackle: dense random clicks of varying size
crk = np.zeros(N)
for a in rng.uniform(0, D, 900):
    m = int(rng.uniform(.0008, .006) * SR); i0 = int(a * SR); seg = rng.standard_normal(m) * np.exp(-np.arange(m) / (m / 3))
    crk[i0:i0 + m] += seg[:max(0, N - i0)] * rng.uniform(.3, 1.0)
crk = norm(bandpass(crk, 900, 11000))
# 3. TDMA buzz (217 Hz frame bursts, like a phone next to a speaker), in irregular episodes
frame = ((t * 217) % 1 < .12).astype(float)
buzz = norm(bandpass(frame * np.sign(np.sin(2 * np.pi * 1733 * t)), 150, 6000)) * smooth_gate(N, 1.1, .55, 7)
# 4. heterodyne whistles: carriers beating against each other, drifting
het = np.zeros(N)
for k, (f0, dr, rate) in enumerate(((1450, 900, .37), (2600, -1300, .23), (820, 400, .61))):
    f = f0 + dr * np.sin(2 * np.pi * rate * t + k) + 60 * np.sin(2 * np.pi * 5.3 * t)
    het += np.sin(2 * np.pi * np.cumsum(f) / SR) * (.4 + .6 * smooth_gate(N, .8, .5, 20 + k))
het = norm(het)
# 5. digital data bursts: fast FSK chirps
data = np.zeros(N)
for a in rng.uniform(.4, 8.2, 14):
    L = int(rng.uniform(.18, .55) * SR); i0 = int(a * SR); L = min(L, N - i0)
    bits = rng.integers(0, 2, L // int(SR / 300) + 1).repeat(int(SR / 300))[:L]
    fr = np.where(bits, 2400, 1200) * rng.uniform(.8, 1.4); data[i0:i0 + L] += np.sign(np.sin(2 * np.pi * np.cumsum(fr) / SR)) * np.hanning(L) ** .3
data = norm(bandpass(data, 600, 7000))
# 6. sub thump of the carrier dropping in and out
sub = np.sin(2 * np.pi * 52 * t) * smooth_gate(N, 2.5, .4, 99)

mix = static * .85 + crk * .55 + buzz * .55 + het * .32 + data * .4 + sub * .35
# stutter: hard dropouts (signal lost for a few ms) — denser toward the middle
drop = np.ones(N)
for a in rng.uniform(.3, 8.3, 46):
    m = int(rng.uniform(.015, .09) * SR); i0 = int(a * SR); drop[i0:i0 + m] = .05
mix *= onepole_lp(drop, 400)
# envelope: hard-in (20 ms), full level until 8.5 s, fade to silence by 10.2 s
env = np.ones(N); a = int(.02 * SR); env[:a] = np.linspace(0, 1, a)
f0, f1 = int(8.5 * SR), int(10.2 * SR); env[f0:f1] = np.linspace(1, 0, f1 - f0) ** 1.6; env[f1:] = 0
mix *= env
L = mix; R = np.roll(mix, 17) * .96 + bandpass(rng.standard_normal(N), 3000, 9000) * .04 * env   # slight width
st = np.stack([L, R]); st = st / (np.max(np.abs(st)) + 1e-9) * .89

wp = out + '.wav'
with wave.open(wp, 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st.T * 32767).astype('<i2').tobytes())
# loud: -10 LUFS integrated over the noisy part, true peak -1.5 dBTP
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', wp, '-af', 'loudnorm=I=-10:TP=-1.5:LRA=7', '-ar', str(SR),
                '-codec:a', 'libmp3lame', '-b:a', '128k', out], check=True)
import os; os.remove(wp); print('OK →', out)
