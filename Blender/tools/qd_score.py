"""An original 32-bar, 96 BPM instrumental sketch for the Qingdao campus film."""
from pathlib import Path
import wave, numpy as np
from scipy.signal import butter,sosfilt
root=Path(__file__).resolve().parents[1]
def main():
    sr=48000;duration=80;beat=60/96;rng=np.random.default_rng(1901)
    mix=np.zeros((sr*duration,2),'float32')
    def tone(start,dur,midi,amp,pan,kind='piano'):
        idx=int(sr*start);n=min(len(mix)-idx,int(sr*dur))
        if n<=0:return
        t=np.arange(n)/sr;freq=440*2**((midi-69)/12);phase=2*np.pi*freq*t
        if kind=='piano':
            snd=(np.sin(phase)+.37*np.exp(-2*t)*np.sin(2.002*phase)+.16*np.exp(-4*t)*np.sin(3.006*phase)+.06*np.exp(-6*t)*np.sin(5.014*phase))
            env=(1-np.exp(-t*105))*np.exp(-t*2.2)*(1-np.exp(-(n/sr-t)*28))
        elif kind=='wind':
            snd=np.sin(phase+.12*np.sin(t*2*np.pi*4.8))+.18*np.sin(phase*2)+.045*np.sin(phase*3)
            env=(1-np.exp(-t*7))*(1-np.exp(-(n/sr-t)*5))*(.88+.12*np.sin(t*4.7))
        else:
            snd=np.sin(phase)+.31*np.sin(phase*2.002)+.13*np.sin(phase*3.0)
            env=(1-np.exp(-t*5))*np.exp(-t*.42)*(1-np.exp(-(n/sr-t)*6))
        env=np.maximum(0,env)
        sig=(snd*env*amp).astype('float32')
        mix[idx:idx+n,0]+=sig*np.sqrt((1-pan)/2);mix[idx:idx+n,1]+=sig*np.sqrt((1+pan)/2)
    chords=[(50,57,62,66,69),(45,57,61,64,69),(47,54,59,62,66),(43,55,59,62,69),(50,54,57,64,66),(42,54,57,61,64),(43,55,59,62,66),(45,57,62,64,69)]
    motifs=[[(0,74,1.4),(1.7,73,.8),(2.8,69,1)],[(.5,71,1.55),(2.65,69,.95)],[(0,66,1.2),(1.45,69,1),(2.75,71,1.1)],[(.3,67,2.7)],[(0,69,.85),(1.2,74,1.4),(3,76,.75)],[(.55,73,1.5),(2.7,69,1.05)],[(0,71,1.5),(1.9,67,1.65)],[(.15,69,3.05)]]
    for bar in range(32):
        c=chords[bar%8];sec=bar*beat*4
        tone(sec,2.5,c[0],.23,-.05,'bass')
        pattern=(1,2,3,4,2,3) if bar%2==0 else (1,3,2,4,3,2)
        for i,k in enumerate(pattern):
            where=(0,.6,1.4,2.05,2.72,3.45)[i]
            tone(sec+beat*where,1.62,c[k],.125*(.8+.2*rng.random()),-.30+.12*(k-1))
        if bar<31 and bar not in (0,16):
            for off,n,d in motifs[bar%8]:
                tone(sec+off*beat,d*beat+.19,n,.11 if bar<8 else .15,.18,'wind')
        if bar>=8 and bar%4 in (1,3):tone(sec+1.25,1.4,c[2]+12,.051,.47)
    # Small early room reflections and a diffuse tail, separated in stereo.
    clean=mix.copy()
    for seconds,gain,cross in [(.057,.13,False),(.093,.12,True),(.167,.095,False),(.28,.073,True),(.42,.044,False),(.63,.026,True)]:
        n=int(seconds*sr);mix[n:]+=clean[:-n,::-1] * gain if cross else clean[:-n]*gain
    mix=sosfilt(butter(2,12000,fs=sr,btype='low',output='sos'),mix,axis=0)
    fade=np.minimum(1,np.arange(len(mix))/(sr*.65))*np.minimum(1,np.arange(len(mix))[::-1]/(sr*2.7));mix*=fade[:,None]
    mix*=.74/max(.001,np.max(np.abs(mix)));pcm=np.asarray(np.clip(mix,-1,1)*32767,'<i2')
    dest=root/'.jobs/music/score.wav';dest.parent.mkdir(exist_ok=True,parents=True)
    with wave.open(str(dest),'wb') as f:f.setnchannels(2);f.setsampwidth(2);f.setframerate(sr);f.writeframes(pcm.tobytes())
    print(dest, len(mix)/sr, 'seconds')
if __name__=='__main__':main()

