from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import (
    ImageClip,
    VideoFileClip,
    CompositeVideoClip,
    AudioFileClip,
    CompositeAudioClip,
    concatenate_videoclips,
    vfx,
    afx,
)

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_config(cfg: dict) -> None:
    if not isinstance(cfg, dict):
        raise ValueError("설정 파일 형식이 올바르지 않습니다. JSON 객체 형태여야 합니다.")
    if "video" not in cfg or not isinstance(cfg["video"], dict):
        raise ValueError("`video` 설정이 없습니다. width/height/fps를 확인하세요.")
    if "scenes" not in cfg or not isinstance(cfg["scenes"], list) or len(cfg["scenes"]) == 0:
        raise ValueError("`scenes`가 비어 있습니다. 최소 1개 이상의 장면을 설정하세요.")

    vcfg = cfg["video"]
    width = int(vcfg.get("width", 0))
    height = int(vcfg.get("height", 0))
    fps = int(vcfg.get("fps", 0))
    if width <= 0 or height <= 0:
        raise ValueError("영상 크기(width/height)는 1 이상의 정수여야 합니다.")
    if fps <= 0:
        raise ValueError("fps는 1 이상의 정수여야 합니다.")

    for i, scene in enumerate(cfg["scenes"], start=1):
        if not isinstance(scene, dict):
            raise ValueError(f"{i}번 장면 형식이 잘못되었습니다. 객체 형태로 입력하세요.")
        source = scene.get("source")
        if not source or not isinstance(source, str):
            raise ValueError(f"{i}번 장면에 `source`가 없습니다.")
        duration = float(scene.get("duration", 0))
        if duration <= 0:
            raise ValueError(f"{i}번 장면 duration은 0보다 커야 합니다.")
        zoom = float(scene.get("zoom", 1.0))
        if zoom <= 0:
            raise ValueError(f"{i}번 장면 zoom은 0보다 커야 합니다.")


def find_font(bold: bool = True) -> str | None:
    candidates = [
        ROOT / "assets/fonts/NanumGothicBold.ttf",
        ROOT / "assets/fonts/NanumGothic.ttf",
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"),
        Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    if not bold:
        candidates = [p for p in candidates if "Bold" not in p.name] + candidates
    for p in candidates:
        if p.exists():
            return str(p)
    return None


def load_font(size: int, bold: bool = True):
    path = find_font(bold=bold)
    if path:
        return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def fit_cover(img: Image.Image, size: Tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)
    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = max(0, (new_w - target_w) // 2)
    top = max(0, (new_h - target_h) // 2)
    return img.crop((left, top, left + target_w, top + target_h))


def placeholder_scene(index: int, caption: str, size: Tuple[int, int]) -> Image.Image:
    """이미지 파일이 없을 때도 프로젝트가 바로 실행되도록 임시 장면 생성."""
    w, h = size
    # 장면마다 밝기가 조금씩 다른 배경
    base = 54 + (index * 17) % 120
    img = Image.new("RGB", size, (base, min(180, base + 35), min(210, base + 70)))
    draw = ImageDraw.Draw(img)

    # 세로 화면에서도 잘 보이도록 하단 들판 + 상단 해
    draw.rectangle((0, int(h * 0.66), w, h), fill=(80, 135, 74))
    sun_r = int(min(w, h) * 0.075)
    sun_x, sun_y = int(w * 0.84), int(h * 0.14)
    draw.ellipse((sun_x - sun_r, sun_y - sun_r, sun_x + sun_r, sun_y + sun_r), fill=(250, 220, 110))

    # 동물 네 마리를 안전 영역 안쪽에 배치
    centers = [
        (int(w * 0.21), int(h * 0.60)),
        (int(w * 0.40), int(h * 0.64)),
        (int(w * 0.60), int(h * 0.60)),
        (int(w * 0.79), int(h * 0.64)),
    ]
    colors = [(205, 150, 95), (115, 115, 125), (235, 235, 235), (220, 205, 190)]
    r = max(28, int(min(w, h) * 0.09))
    for (cx, cy), color in zip(centers, colors):
        draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=color, outline=(35, 35, 35), width=4)
        eye = max(3, r // 10)
        draw.ellipse((cx-r//3-eye, cy-r//5-eye, cx-r//3+eye, cy-r//5+eye), fill=(20, 20, 20))
        draw.ellipse((cx+r//3-eye, cy-r//5-eye, cx+r//3+eye, cy-r//5+eye), fill=(20, 20, 20))

    font_big = load_font(max(36, int(h * 0.052)))
    font_small = load_font(max(20, int(h * 0.028)), bold=False)
    title = f"SCENE {index:02d}"
    box = draw.textbbox((0, 0), title, font=font_big)
    draw.text(((w - (box[2]-box[0]))/2, h*0.10), title, font=font_big, fill="white",
              stroke_width=3, stroke_fill=(0,0,0))
    short = caption[:28]
    box2 = draw.textbbox((0, 0), short, font=font_small)
    draw.text(((w - (box2[2]-box2[0]))/2, h*0.19), short, font=font_small, fill="white",
              stroke_width=2, stroke_fill=(0,0,0))
    return img


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, stroke_width: int = 0, max_lines: int = 0) -> list[str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return []

    lines: list[str] = []
    for raw in cleaned.splitlines():
        current = ""
        for ch in raw:
            trial = current + ch
            bb = draw.textbbox((0, 0), trial, font=font, stroke_width=stroke_width)
            if bb[2] - bb[0] <= max_width or not current:
                current = trial
            else:
                lines.append(current.strip())
                current = ch
        if current.strip():
            lines.append(current.strip())

    lines = [line for line in lines if line]
    if max_lines > 0 and len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines:
            trial = lines[-1].rstrip(" .") + "…"
            bb = draw.textbbox((0, 0), trial, font=font, stroke_width=stroke_width)
            if bb[2] - bb[0] <= max_width:
                lines[-1] = trial
                break
            lines[-1] = lines[-1][:-1]
            if not lines[-1]:
                lines.pop()
    return lines


def caption_overlay(text: str, size: Tuple[int, int]) -> np.ndarray:
    w, h = size
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = load_font(max(28, int(h * 0.034)))

    safe_left = int(w * 0.06)
    safe_right = int(w * 0.94)
    max_width = safe_right - safe_left - int(w * 0.06)
    lines = wrap_text(draw, text, font, max_width=max_width, stroke_width=2, max_lines=4)
    if not lines:
        return np.array(overlay)

    font_h = draw.textbbox((0, 0), "가", font=font, stroke_width=2)[3]
    line_gap = max(6, int(font_h * 0.35))
    line_h = font_h + line_gap
    total_h = line_h * len(lines) + int(h * 0.05)
    y0 = h - total_h - int(h * 0.045)

    draw.rounded_rectangle(
        (safe_left, y0, safe_right, h - int(h * 0.03)),
        radius=24,
        fill=(0, 0, 0, 150),
    )

    y = y0 + int(h * 0.018)
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=font, stroke_width=2)
        tw = bb[2] - bb[0]
        draw.text(
            ((w - tw) / 2, y),
            line,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=2,
            stroke_fill=(0,0,0,220),
        )
        y += line_h
    return np.array(overlay)


def title_overlay(title: str, subtitle: str, size: Tuple[int, int]) -> np.ndarray:
    w, h = size
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    title_font = load_font(max(44, int(h * 0.05)))
    sub_font = load_font(max(24, int(h * 0.028)), bold=False)

    safe_left = int(w * 0.08)
    safe_right = int(w * 0.92)
    max_width = safe_right - safe_left
    title_lines = wrap_text(draw, title, title_font, max_width=max_width, stroke_width=3, max_lines=2)
    subtitle_lines = wrap_text(draw, subtitle, sub_font, max_width=max_width, stroke_width=2, max_lines=2)

    y = int(h * 0.08)
    for line in title_lines:
        bb = draw.textbbox((0, 0), line, font=title_font, stroke_width=3)
        tw = bb[2] - bb[0]
        draw.text(
            ((w - tw) / 2, y),
            line,
            font=title_font,
            fill=(255, 255, 255, 255),
            stroke_width=3,
            stroke_fill=(0, 0, 0, 210),
        )
        y += int((bb[3] - bb[1]) * 1.15)

    y += int(h * 0.015)
    for line in subtitle_lines:
        bb = draw.textbbox((0, 0), line, font=sub_font, stroke_width=2)
        sw = bb[2] - bb[0]
        draw.text(
            ((w - sw) / 2, y),
            line,
            font=sub_font,
            fill=(255, 255, 255, 245),
            stroke_width=2,
            stroke_fill=(0, 0, 0, 200),
        )
        y += int((bb[3] - bb[1]) * 1.2)
    return np.array(overlay)


def make_image_scene(
    path: Path,
    duration: float,
    caption: str,
    zoom: float,
    size: Tuple[int, int],
    scene_index: int,
    fade_seconds: float,
):
    if path.exists():
        try:
            with Image.open(path) as opened:
                img = fit_cover(opened.convert("RGB"), size)
        except OSError:
            print(f"[안내] 이미지 열기 실패: {path.name} -> 임시 장면으로 대체")
            img = placeholder_scene(scene_index, caption, size)
    else:
        print(f"[안내] 이미지 없음: {path.name} -> 임시 장면으로 대체")
        img = placeholder_scene(scene_index, caption, size)

    base = ImageClip(np.array(img)).with_duration(duration)

    # 1.00 -> zoom 배율로 아주 천천히 확대
    if zoom and zoom > 1.0:
        base = base.with_effects([
            vfx.Resize(lambda t: 1.0 + (zoom - 1.0) * min(1.0, t / max(duration, 0.01)))
        ])

    base = base.with_position(("center", "center"))
    canvas = CompositeVideoClip([base], size=size).with_duration(duration)

    caption_img = caption_overlay(caption, size)
    cap = ImageClip(caption_img, is_mask=False).with_duration(duration)
    canvas = CompositeVideoClip([canvas, cap], size=size).with_duration(duration)

    if fade_seconds > 0:
        canvas = canvas.with_effects([
            vfx.FadeIn(min(fade_seconds, duration/3)),
            vfx.FadeOut(min(fade_seconds, duration/3)),
        ])
    return canvas


def make_video_scene(
    path: Path,
    duration: float,
    caption: str,
    size: Tuple[int, int],
    fade_seconds: float,
):
    clip = VideoFileClip(str(path))
    if clip.duration >= duration:
        clip = clip.subclipped(0, duration)
    else:
        clip = clip.with_effects([vfx.Loop(duration=duration)])

    w, h = clip.size
    target_w, target_h = size
    scale = max(target_w / w, target_h / h)
    clip = clip.resized(scale)
    clip = CompositeVideoClip([clip.with_position(("center", "center"))], size=size).with_duration(duration)

    cap = ImageClip(caption_overlay(caption, size)).with_duration(duration)
    clip = CompositeVideoClip([clip, cap], size=size).with_duration(duration)

    if fade_seconds > 0:
        clip = clip.with_effects([
            vfx.FadeIn(min(fade_seconds, duration/3)),
            vfx.FadeOut(min(fade_seconds, duration/3)),
        ])
    return clip


def build_video():
    cfg = load_config()
    validate_config(cfg)
    vcfg = cfg["video"]
    size = (int(vcfg["width"]), int(vcfg["height"]))
    fps = int(vcfg.get("fps", 30))
    fade_seconds = float(vcfg.get("fade_seconds", 0.35))

    clips = []
    final = None
    title = None
    bgm_source = None
    bgm = None
    try:
        for i, scene in enumerate(cfg["scenes"], start=1):
            source = ROOT / scene["source"]
            duration = float(scene.get("duration", 7.5))
            caption = scene.get("caption", "")
            zoom = float(scene.get("zoom", 1.04))

            if source.suffix.lower() in VIDEO_EXTENSIONS:
                if not source.exists():
                    raise FileNotFoundError(f"{i}번 장면 영상 파일을 찾을 수 없습니다: {source}")
                clip = make_video_scene(source, duration, caption, size, fade_seconds)
            else:
                clip = make_image_scene(source, duration, caption, zoom, size, i, fade_seconds)
            clips.append(clip)

        final = concatenate_videoclips(clips, method="compose")

        # 첫 장면 상단 타이틀
        title_duration = min(4.5, final.duration)
        title = ImageClip(
            title_overlay(cfg.get("project_title", ""), cfg.get("subtitle", ""), size)
        ).with_duration(title_duration)
        title = title.with_effects([vfx.FadeIn(0.5), vfx.FadeOut(0.7)])
        final = CompositeVideoClip([final, title], size=size).with_duration(final.duration)

        # BGM이 있으면 전체 길이에 맞춰 반복 후 믹싱
        bgm_path = ROOT / cfg.get("bgm", "")
        if bgm_path.exists():
            bgm_source = AudioFileClip(str(bgm_path))
            bgm = bgm_source.with_effects([
                afx.AudioLoop(duration=final.duration),
                afx.MultiplyVolume(float(vcfg.get("bgm_volume", 0.16))),
                afx.AudioFadeIn(1.0),
                afx.AudioFadeOut(1.5),
            ])
            if final.audio is not None:
                final = final.with_audio(CompositeAudioClip([final.audio, bgm]))
            else:
                final = final.with_audio(bgm)
        else:
            print(f"[안내] BGM 없음: {bgm_path}. 무음 영상으로 생성합니다.")

        out = ROOT / cfg.get("output", "output/animal_trip.mp4")
        out.parent.mkdir(parents=True, exist_ok=True)
        print(f"[렌더링 시작] {out}")
        final.write_videofile(
            str(out),
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            threads=4,
            ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
        )
        print(f"[완료] {out}")
    finally:
        if title is not None:
            title.close()
        if bgm is not None:
            bgm.close()
        if bgm_source is not None:
            bgm_source.close()
        if final is not None:
            final.close()
        for clip in clips:
            clip.close()


if __name__ == "__main__":
    build_video()
