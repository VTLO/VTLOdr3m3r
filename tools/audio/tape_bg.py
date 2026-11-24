import numpy as np, subprocess, wave, json, sys
from scipy import signal
import pyloudnorm as pyln, tape
SRC=sys.argv[1] if len(sys.argv) > 1 else '../../app/src/main/assets/www/audio/bg.mp3'
subprocess.run(['ffmpeg','-y','-loglevel','error','-i',SRC,'-ar','32000','wav4/bg_src.wav'],check=True)
w=wave.open('wav4/bg_src.wav'); SR=w.getframerate(); ch=w.getnchannels(); x=np.frombuffer(w.readframes(w.getnframes()),dtype=np.int16).reshape(-1,ch).T.astype(np.float32)/32768
r=np.random.default_rng(404); N=x.shape[1]; T=np.arange(N)/SR
out=[]
for c in range(ch):
    y=tape.wow_flutter(x[c],SR,r,wow=.0022,flutter=.0008)
    y=tape.dropouts(y,SR,r,16,dur=(.04,.22),depth=(.05,.4))
    env=np.clip(np.sin(2*np.pi*T/37+c)*.6+.4,0,1)**3                      # slow "tracking" swells
    y=y+tape.tracking_noise(N,SR,r,.010)*env+tape.hiss(N,SR,r,.006)
    y=tape.print_through(y,SR,.6,.05); y=tape.tape_eq(y,SR,10500,35); out.append(y)
st=np.stack(out); m=pyln.Meter(SR)
ref=m.integrated_loudness(x.T.astype(np.float64)); cur=m.integrated_loudness(st.T.astype(np.float64)); st*=10**((ref-cur)/20)
pk=np.abs(st).max(); st*= min(1,10**(-1.2/20)/pk)
pcm=(np.clip(st.T,-1,1)*32767).astype('<i2')
with wave.open('wav4/bg_tape.wav','wb') as o: o.setnchannels(ch);o.setsampwidth(2);o.setframerate(SR);o.writeframes(pcm.tobytes())
subprocess.run(['ffmpeg','-y','-loglevel','error','-i','wav4/bg_tape.wav','-codec:a','libmp3lame','-b:a','128k','-joint_stereo','1','out4/bg.mp3'],check=True)
print('bg LUFS ref',round(ref,1),'out',round(m.integrated_loudness(st.T.astype(np.float64)),1),'peak',round(20*np.log10(np.abs(st).max()),2))
