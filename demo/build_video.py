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
from xml.sax.saxutils import escape
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
OUT = HERE / "out"
WORK = OUT / "build"
W, H, FPS = 1280, 720, 30
GAP = 0.8  # breathing room after each narration line
MAX_SPEEDUP = 2.6

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
  .arch-title { position:absolute; top:44px; left:72px; font-family:'Familjen Grotesk',sans-serif; font-size:40px; font-weight:700; }
  .arch { position:absolute; left:72px; right:72px; top:150px; display:flex; align-items:center; gap:18px; }
  .lanes { display:flex; flex-direction:column; gap:26px; }
  .lane { display:flex; align-items:center; gap:10px; font-size:30px; color:#e8741e; }
  .pill { display:inline-flex; flex-direction:column; justify-content:center; background:#fff; border:2px solid #1f4e9a;
          border-radius:12px; padding:10px 14px; font-size:21px; color:#1b2233; line-height:1.2; min-height:58px; box-sizing:border-box; }
  .pill small { font-size:15px; color:#4a5366; }
  .src { border-color:#1b2233; background:#1b2233; color:#fff; }
  .arrow { font-size:34px; color:#e8741e; }
  .brain { background:#e8741e; color:#1b2233; border-radius:16px; padding:22px 20px; font-size:22px; text-align:center; line-height:1.25; }
  .brain b { display:block; font-family:'Familjen Grotesk',sans-serif; font-size:30px; }
  .ai { display:flex; flex-direction:column; gap:14px; }
  .strong { background:#1f4e9a; color:#fff; font-size:22px; }
  .tool { border-style:dashed; }
  .notes { position:absolute; left:72px; right:72px; bottom:150px; display:flex; gap:16px; }
  .notes span { flex:1; border-top:6px solid #e8741e; padding-top:10px; font-size:19px; color:#4a5366; line-height:1.35; }
  .notes b { color:#1b2233; }
</style>"""

CARDS = {
    "title": """<div class="dome"></div><div><h1>Liga pra Mim</h1>
        <p>An AI helpline anyone can call.</p><p>No app. No internet. No reading required.</p></div>""",
    "architecture": """<div class="arch-title">How it works</div>
        <div class="arch">
          <div class="lanes">
            <div class="lane"><span class="pill src">Any phone</span><span class="arrow">&rarr;</span>
              <span class="pill">Amazon Connect<small>phone number</small></span><span class="arrow">&rarr;</span>
              <span class="pill">Amazon Lex<small>speech &#8644; text</small></span></div>
            <div class="lane"><span class="pill src">Website</span><span class="arrow">&rarr;</span>
              <span class="pill">AWS Amplify<small>Next.js site</small></span><span class="arrow">&rarr;</span>
              <span class="pill">API Gateway<small>+ Amazon Polly voice</small></span></div>
          </div>
          <span class="arrow">&rarr;</span>
          <div class="brain">AWS Lambda<b>the brain</b></div>
          <span class="arrow">&rarr;</span>
          <div class="ai">
            <span class="pill strong">Claude on Amazon Bedrock</span>
            <span class="pill tool">Benefit rules calculator<small>official 2026 rules, tested</small></span>
            <span class="pill tool">CRAS locator<small>8,641 official centers</small></span>
          </div>
        </div>
        <div class="notes">
          <span><b>Essential mode:</b> guided questions with the same rules if the AI is down</span>
          <span><b>Amazon DynamoDB:</b> 24-hour memory and anonymous impact stats</span>
          <span><b>AWS CDK:</b> the whole stack is infrastructure as code</span>
        </div>""",
    "ai-answer": """<div style="width:100%">
        <p class="small" style="margin-bottom:22px">Real answer from Claude on Amazon Bedrock &middot; recorded during evaluation, Sept 30, 2026</p>
        <div style="background:#fbe3cf;border-radius:18px 18px 4px 18px;padding:18px 24px;margin:0 0 18px auto;max-width:780px;font-size:26px">
          Where is the nearest social assistance center (CRAS) in S&atilde;o Paulo? I live in Jardim Santa F&eacute;.</div>
        <div style="background:#dfe7f4;border-radius:18px 18px 18px 4px;padding:20px 26px;max-width:960px;font-size:25px;line-height:1.45">
          Hello! The closest CRAS to you is <b>CRAS Anhanguera</b>, right in your neighborhood, Jardim Santa F&eacute;.
          The address is <b>Avenida Piero Tricca, 27</b>, next to Igreja Universal. It's open 5 days a week, 10 hours a day.
          You can also call them at <b>1 1, 3 9 1 1, 3 9 0 6</b> if you want to confirm the exact hours.
          Would you like the information for another CRAS nearby, or can I help you with something else?</div></div>""",
    "twist": """<div class="dome" style="width:220px;height:190px;filter:grayscale(.6)"></div><div>
        <h2>Sept 30: Bedrock access paused</h2>
        <p>AWS paused this account's access to Bedrock for verification, one day before the deadline.</p>
        <p class="big" style="margin-top:28px">A helpline can't go silent.</p>
        <p>Essential mode: guided questions, the same official rules, the same list of 8,641 CRAS centers.</p></div>""",
    "evaluation": """<div style="width:100%"><h2>Measured, not assumed</h2>
        <div class="row"><b>25/25</b><p>real conversations passed, in Portuguese and English</p></div>
        <div class="row"><b>65</b><p>unit tests for the rules, the CRAS search and the handlers</p></div>
        <div class="row"><b>8,641</b><p>official CRAS centers the assistant can direct people to</p></div></div>""",
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


# The generative engine sounds the most natural but mispronounces Portuguese names and ignores <phoneme>;
# so each [pt]name[/pt] is spoken by the same voice on the neural engine with an IPA hint and stitched in.
PT_SPAN = re.compile(r"\[pt\](.*?)\[/pt\]")
PRONUNCIATION = {"Liga pra Mim": "ˈliɡə pɹə ˈmin"}


def plain(text: str) -> str:
    return PT_SPAN.sub(lambda m: m.group(1), text)


def _polly(text: str, voice: str, engine: str, path: Path) -> None:
    import boto3

    polly = boto3.client("polly", region_name="us-east-1")
    kwargs = {"TextType": "ssml"} if text.startswith("<speak>") else {}
    audio = polly.synthesize_speech(Text=text, VoiceId=voice, Engine=engine, OutputFormat="mp3", SampleRate="24000", **kwargs)
    path.write_bytes(audio["AudioStream"].read())


def synthesize(seg_id: str, text: str, voice: str) -> Path:
    digest = hashlib.sha1(f"{voice}|hybrid|{text}".encode()).hexdigest()[:10]
    path = WORK / f"narr-{seg_id}-{digest}.mp3"
    if path.exists():
        return path
    if os.environ.get("NARRATION") == "silent":  # offline preview: silence lasting about as long as the speech
        ffmpeg("-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", f"{len(plain(text).split()) / 2.6:.2f}", str(path))
        return path
    parts, last = [], 0
    for m in PT_SPAN.finditer(text):
        parts += [("en", text[last:m.start()]), ("pt", m.group(1))]
        last = m.end()
    parts.append(("en", text[last:]))
    parts = [(kind, chunk.strip(" ,")) for kind, chunk in parts if chunk.strip(" ,")]

    pieces = []
    for i, (kind, chunk) in enumerate(parts):
        piece = WORK / f"part-{seg_id}-{digest}-{i}.mp3"
        if kind == "pt":
            ssml = f'<speak><phoneme alphabet="ipa" ph="{PRONUNCIATION[chunk]}">{escape(chunk)}</phoneme></speak>'
            _polly(ssml, voice, "neural", piece)
        else:
            _polly(chunk, voice, "generative", piece)
        pieces.append((kind, piece))
    if len(pieces) == 1:
        pieces[0][1].replace(path)
        return path

    # trim the silence Polly leaves around each piece so the name flows into the sentence
    filters, labels = [], []
    for i, (kind, _) in enumerate(pieces):
        trim = "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse"
        pad = ",apad=pad_dur=0.12" if kind == "pt" else ",apad=pad_dur=0.05"
        filters.append(f"[{i}:a]aresample=24000,{trim}{pad}[p{i}]")
        labels.append(f"[p{i}]")
    graph = ";".join(filters) + ";" + "".join(labels) + f"concat=n={len(pieces)}:v=0:a=1"
    inputs = [a for _, piece in pieces for a in ("-i", str(piece))]
    ffmpeg(*inputs, "-filter_complex", graph, "-ac", "1", str(path))
    return path


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
            chunks, cursor = split_caption(plain(seg["text"])), t
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

    style = "FontName=Arial,FontSize=19,PrimaryColour=&H00FFFFFF,BackColour=&H30000000,BorderStyle=4,Outline=0,Shadow=0,MarginV=26"
    music = (HERE / "music" / "dreamer.mp3").resolve()
    mix = (f"[1:a]volume=0.22,atrim=0:{t:.2f},afade=t=in:d=2,afade=t=out:st={max(0, t - 4):.2f}:d=4[m];"
           "[0:a]asplit=2[v1][v2];"
           "[m][v1]sidechaincompress=threshold=0.02:ratio=12:attack=15:release=600[md];"
           "[v2][md]amix=inputs=2:duration=first:normalize=0[a]")
    ffmpeg("-i", "joined.mp4", "-stream_loop", "-1", "-i", str(music),
           "-filter_complex", mix, "-map", "0:v", "-map", "[a]",
           "-vf", f"subtitles=captions.srt:force_style='{style}'",
           "-c:v", "libx264", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
           "-t", f"{t:.2f}", "../liga-pra-mim-demo-v4.mp4", cwd=WORK)
    print(f"total {t:.1f}s -> {OUT / "liga-pra-mim-demo-v4.mp4"}")


if __name__ == "__main__":
    main()
