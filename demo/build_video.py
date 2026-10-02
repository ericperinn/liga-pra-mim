"""Builds the demo video from the site recording, Polly narration, cards, captions and music.

Usage (needs `aws login` for Polly):  demo/.venv/Scripts/python demo/build_video.py
       offline preview with silent narration:  NARRATION=silent demo/.venv/Scripts/python demo/build_video.py
Inputs:  demo/narration.json, demo/out/site-en.webm + site-en.chapters.json (record_site.py),
         demo/music/dreamer.mp3, optional demo/out/call.mp3 + demo/out/call.srt (real phone call)
Output:  demo/out/liga-pra-mim-demo.mp4
"""

import glob
import os
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
OUT = HERE / "out"
WORK = OUT / "build"
W, H, FPS = 1280, 720, 30
GAP = 0.8  # breathing room after each narration line
MAX_SPEEDUP = 1.6

FF = shutil.which("ffmpeg") or glob.glob(
    str(Path.home() / "AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg*/*/bin/ffmpeg.exe")
)[0]
FFPROBE = str(Path(FF).with_name("ffprobe.exe" if FF.endswith(".exe") else "ffprobe"))

PHONE = "+1 (725) 333-6978"
SITE = "main.d3197h98vf4n1z.amplifyapp.com"
REPO = "github.com/ericperinn/liga-pra-mim"

CARD_CSS = """
<link href="https://fonts.googleapis.com/css2?family=Familjen+Grotesk:wght@500;700&family=Inclusive+Sans&display=swap" rel="stylesheet">
<style>
  body { margin:0; width:1280px; height:720px; background:#eef0ec; color:#1b2233; font-family:'Inclusive Sans',sans-serif;
         display:flex; align-items:center; padding:0 96px; box-sizing:border-box; gap:72px; }
  h1 { font-family:'Familjen Grotesk',sans-serif; font-size:76px; line-height:1.02; margin:0 0 20px; }
  h2 { font-family:'Familjen Grotesk',sans-serif; font-size:52px; line-height:1.08; margin:0 0 28px; }
  p { font-size:28px; line-height:1.4; margin:0 0 12px; color:#4a5366; max-width:22em; }
  .dome { width:300px; height:260px; flex:none; border-radius:50% 50% 20% 20% / 66% 66% 14% 14%;
          background:radial-gradient(ellipse 60% 45% at 38% 26%, rgba(255,255,255,.35), transparent 70%), #e8741e;
          box-shadow: inset 0 -16px 0 #b8540c; }
  .big { font-family:'Familjen Grotesk',sans-serif; font-weight:700; font-size:40px; color:#1b2233; }
  .row { display:flex; align-items:baseline; gap:20px; border-top:6px solid #e8741e; padding:18px 0 10px; }
  .row b { font-family:'Familjen Grotesk',sans-serif; font-size:56px; min-width:4.2ch; }
  .small { font-size:20px; }
</style>"""

CARDS = {
    "title": """<div class="dome"></div><div><h1>Liga pra Mim</h1>
        <p>An AI helpline anyone can call.</p><p>No app. No internet. No reading required.</p></div>""",
    "evaluation": """<div style="width:100%"><h2>Measured, not assumed</h2>
        <div class="row"><b>25/25</b><p>real conversations passed, in Portuguese and English</p></div>
        <div class="row"><b>65</b><p>unit tests for the rules, the CRAS search and the handlers</p></div>
        <div class="row"><b>0</b><p>dead air: an essential mode answers if the AI is down</p></div></div>""",
    "call": """<div class="dome" style="width:220px;height:190px"></div><div><h2>A real call</h2>
        <p>Portuguese, with English subtitles.</p><p class="big">""" + PHONE + "</p></div>",
    "end": f"""<div class="dome" style="width:220px;height:190px"></div><div><h2>Call it. Try it.</h2>
        <p class="big">{PHONE}</p><p>{SITE}</p><p>{REPO}</p>
        <p class="small" style="margin-top:36px">Music: "Dreamer" Kevin MacLeod (incompetech.com),
        licensed under Creative Commons: By Attribution 4.0</p></div>""",
}


def ffmpeg(*args: str, cwd: Path | None = None) -> None:
    subprocess.run([FF, "-y", "-loglevel", "error", *args], check=True, cwd=cwd)


def duration(path: Path) -> float:
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def render_cards(names: set[str]) -> dict[str, Path]:
    paths = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H})
        for name in names:
            page.set_content(f"<!doctype html><html><head><meta charset='utf-8'>{CARD_CSS}</head><body>{CARDS[name]}</body></html>")
            page.wait_for_timeout(1200)  # web fonts
            paths[name] = WORK / f"card-{name}.png"
            page.screenshot(path=str(paths[name]))
        browser.close()
    return paths


def synthesize(seg_id: str, text: str, voice: str) -> Path:
    digest = hashlib.sha1(f"{voice}|{text}".encode()).hexdigest()[:10]
    path = WORK / f"narr-{seg_id}-{digest}.mp3"
    if path.exists():
        return path
    if os.environ.get("NARRATION") == "silent":  # offline preview: silence lasting about as long as the speech
        ffmpeg("-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", f"{len(text.split()) / 2.6:.2f}", str(path))
        return path
    import boto3

    polly = boto3.client("polly", region_name="us-east-1")
    for engine in ("generative", "neural"):
        try:
            audio = polly.synthesize_speech(Text=text, VoiceId=voice, Engine=engine, OutputFormat="mp3")
            path.write_bytes(audio["AudioStream"].read())
            return path
        except polly.exceptions.ClientError:
            continue
    raise RuntimeError(f"Polly could not synthesize {seg_id}")


def video_filter(extra: str = "") -> str:
    base = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0xeef0ec,fps={FPS},format=yuv420p"
    return f"{extra},{base}" if extra else base


def make_clip(index: int, visual: str, audio: Path | None, length: float, chapters: dict, cards: dict) -> Path:
    clip = WORK / f"clip-{index:02d}.mp4"
    audio_in = ["-i", str(audio)] if audio else ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    audio_out = ["-map", "1:a", "-af", f"apad,atrim=0:{length:.2f}", "-ar", "48000", "-ac", "2", "-c:a", "aac", "-b:a", "160k"]
    common = ["-t", f"{length:.2f}", "-c:v", "libx264", "-crf", "20", "-r", str(FPS), "-map", "0:v", *audio_out, str(clip)]

    if visual.startswith("card:") or visual == "call":
        card = cards["call" if visual == "call" else visual.split(":", 1)[1]]
        ffmpeg("-loop", "1", "-i", str(card), *audio_in, "-vf", video_filter(), *common)
    elif visual.startswith("image:"):
        image = (HERE / visual.split(":", 1)[1]).resolve()
        frames = int(length * FPS)
        zoom = f"scale={W * 2}:-2,zoompan=z='min(zoom+0.0002,1.03)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{int(W * 828 / 3472) * 2}:fps={FPS}"
        ffmpeg("-loop", "1", "-i", str(image), *audio_in, "-vf", video_filter(zoom), *common)
    else:
        start, end = chapters[visual.split(":", 1)[1]]
        source_len = end - start
        factor = max(length / source_len, 1 / MAX_SPEEDUP)  # <1 speeds up, >1 slows down
        speed = f"trim={start:.2f}:{end:.2f},setpts=(PTS-STARTPTS)*{factor:.4f},tpad=stop_mode=clone:stop_duration=30"
        ffmpeg("-i", str(OUT / "site-en.webm"), *audio_in, "-vf", video_filter(speed), *common)
    return clip


def split_caption(text: str, words_per_line: int = 9) -> list[str]:
    words = text.split()
    return [" ".join(words[i:i + words_per_line]) for i in range(0, len(words), words_per_line)]


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def parse_srt(path: Path) -> list[tuple[float, float, str]]:
    def secs(s: str) -> float:
        h, m, rest = s.split(":")
        sec, ms = rest.split(",")
        return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000

    cues = []
    for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8").strip()):
        lines = block.splitlines()
        a, b = lines[1].split(" --> ")
        cues.append((secs(a), secs(b), " ".join(lines[2:])))
    return cues


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    plan = json.loads((HERE / "narration.json").read_text(encoding="utf-8"))
    marks = json.loads((OUT / "site-en.chapters.json").read_text(encoding="utf-8"))
    chapters = {"hero": (marks["hero"], marks["chat"]), "chat": (marks["chat"], marks["impact"]),
                "impact": (marks["impact"], marks["end"])}
    call_audio, call_srt = OUT / "call.mp3", OUT / "call.srt"
    segments = [s for s in plan["segments"] if s["visual"] != "call" or call_audio.exists()]
    cards = render_cards({s["visual"].split(":", 1)[1] for s in segments if s["visual"].startswith("card:")}
                         | ({"call"} if call_audio.exists() else set()))

    clips, cues, t = [], [], 0.0
    for i, seg in enumerate(segments):
        if seg["visual"] == "call":
            audio, length = call_audio, duration(call_audio) + GAP
            if call_srt.exists():
                cues += [(t + a, t + b, txt) for a, b, txt in parse_srt(call_srt)]
        elif seg["text"]:
            audio = synthesize(seg["id"], seg["text"], plan["voice"])
            spoken = duration(audio)
            length = spoken + GAP
            if seg["visual"].startswith("site:"):
                start, end = chapters[seg["visual"].split(":", 1)[1]]
                length = max(length, (end - start) / MAX_SPEEDUP)
            chunks, cursor = split_caption(seg["text"]), t
            total_chars = sum(len(c) for c in chunks)
            for chunk in chunks:
                span = spoken * len(chunk) / total_chars
                cues.append((cursor, cursor + span, chunk))
                cursor += span
        else:
            audio, length = None, 6.0
        clips.append(make_clip(i, seg["visual"], audio, length, chapters, cards))
        t += length
        print(f"{seg['id']:<13} {length:5.1f}s")

    (WORK / "clips.txt").write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
    ffmpeg("-f", "concat", "-safe", "0", "-i", "clips.txt", "-c", "copy", "joined.mp4", cwd=WORK)
    (WORK / "captions.srt").write_text(
        "".join(f"{n}\n{srt_time(a)} --> {srt_time(b)}\n{txt}\n\n" for n, (a, b, txt) in enumerate(cues, 1)),
        encoding="utf-8")

    style = "FontName=Arial,FontSize=19,PrimaryColour=&H00FFFFFF,BackColour=&H99000000,BorderStyle=4,Outline=0,Shadow=0,MarginV=26"
    music = (HERE / "music" / "dreamer.mp3").resolve()
    mix = (f"[1:a]volume=0.22,atrim=0:{t:.2f},afade=t=in:d=2,afade=t=out:st={max(0, t - 4):.2f}:d=4[m];"
           "[0:a]asplit=2[v1][v2];"
           "[m][v1]sidechaincompress=threshold=0.02:ratio=12:attack=15:release=600[md];"
           "[v2][md]amix=inputs=2:duration=first:normalize=0[a]")
    ffmpeg("-i", "joined.mp4", "-stream_loop", "-1", "-i", str(music),
           "-filter_complex", mix, "-map", "0:v", "-map", "[a]",
           "-vf", f"subtitles=captions.srt:force_style='{style}'",
           "-c:v", "libx264", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
           "-t", f"{t:.2f}", "../liga-pra-mim-demo.mp4", cwd=WORK)
    print(f"total {t:.1f}s -> {OUT / 'liga-pra-mim-demo.mp4'}")


if __name__ == "__main__":
    main()
