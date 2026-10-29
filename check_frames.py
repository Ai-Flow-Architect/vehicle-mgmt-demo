"""動画からコマを抜き、1枚のシートに並べる（字幕と画面のずれ確認用）。
使い方: python3 check_frames.py <mp4> <出力png> [字幕ファイル名]
- 字幕ファイル（video_work/ の .ass）に字幕行があれば、字幕ごとに開始+2.5秒のコマを抜く
- 字幕行が無ければ（字幕を画面の中に出して録画した版＝焼き込み字幕は空）、6秒おきに抜く
  ＝画面の中の字幕帯がコマに写るので、字幕と画面が合っているかをそのまま目で見られる
"""
import re
import subprocess
import sys
import pathlib
from PIL import Image

mp4 = sys.argv[1]
out = pathlib.Path(sys.argv[2])
ass = pathlib.Path(__file__).parent / "video_work" / (sys.argv[3] if len(sys.argv) > 3 else "caps.ass")
tmp = out.parent / "frames"
tmp.mkdir(parents=True, exist_ok=True)
times = []
if ass.exists():
    for line in ass.read_text(encoding="utf-8").splitlines():
        m = re.match(r"Dialogue: 0,(\d+):(\d+):([\d.]+),", line)
        if m:
            times.append(int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) + 2.5)
if not times:
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4],
                               capture_output=True, text=True, check=True).stdout.strip())
    times = [t + 1.0 for t in range(0, int(dur), 6)]
    print(f"字幕行なし＝6秒おきに抜きます（{len(times)}コマ）")
ims = []
for i, t in enumerate(times):
    f = tmp / f"c{i:02d}.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", mp4, "-frames:v", "1", "-vf", "scale=480:-1", str(f)], check=True)
    ims.append(Image.open(f))
if not ims:
    sys.exit("コマを1枚も抜けませんでした（動画の長さが0秒の可能性）")
cols = 4
w, h = ims[0].size
rows = (len(ims) + cols - 1) // cols
sheet = Image.new("RGB", (w * cols, h * rows), "white")
for i, im in enumerate(ims):
    sheet.paste(im, ((i % cols) * w, (i // cols) * h))
sheet.save(out)
print(len(ims), "コマ", out)
