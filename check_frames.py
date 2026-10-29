"""字幕ごとに開始+2.5秒のコマを抜き、1枚のシートに並べる（字幕と画面のずれ確認用）。"""
import re
import subprocess
import sys
import pathlib
from PIL import Image

mp4 = sys.argv[1]
ass = pathlib.Path(__file__).parent / "video_work" / (sys.argv[3] if len(sys.argv) > 3 else "caps.ass")
out = pathlib.Path(sys.argv[2])
tmp = out.parent / "frames"
tmp.mkdir(parents=True, exist_ok=True)
times = []
for line in ass.read_text(encoding="utf-8").splitlines():
    m = re.match(r"Dialogue: 0,(\d+):(\d+):([\d.]+),", line)
    if m:
        times.append(int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) + 2.5)
ims = []
for i, t in enumerate(times):
    f = tmp / f"c{i:02d}.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", mp4, "-frames:v", "1", "-vf", "scale=480:-1", str(f)], check=True)
    ims.append(Image.open(f))
cols = 4
w, h = ims[0].size
rows = (len(ims) + cols - 1) // cols
sheet = Image.new("RGB", (w * cols, h * rows), "white")
for i, im in enumerate(ims):
    sheet.paste(im, ((i % cols) * w, (i // cols) * h))
sheet.save(out)
print(len(ims), "コマ", out)
