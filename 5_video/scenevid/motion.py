"""정지 이미지에 Ken Burns 스타일 모션(zoompan)을 적용하는 FFmpeg vf 조각."""

from __future__ import annotations

import math
import re
from pathlib import Path

# script / JSON / CLI 에서 쓰는 토큰
EFFECT_IDS: tuple[str, ...] = (
    "none",
    "pan_left",
    "pan_right",
    "pan_up",
    "pan_down",
    "zoom_in",
    "zoom_out",
)


def normalize_effect(raw: str | None) -> str:
    """한글·별칭 → 내부 토큰. 알 수 없으면 none."""
    if raw is None:
        return "none"
    s = str(raw).strip()
    # BOM·ZWSP 등 (compose_effects.txt / 복사-붙여넣기)
    s = s.lstrip("\ufeff\u200b\u200c\u200d")
    s = s.strip()
    if not s:
        return "none"
    # 일부 편집기·문서의 전각 @ :
    s = s.replace("\uff1a", ":").replace("\uff20", "@").strip()
    s_low = s.lower()
    # "zoom in", "pan-left" → zoom_in, pan_left
    slug_low = re.sub(r"[-\s]+", "_", s_low)
    nospace_low = re.sub(r"\s+", "", s_low)

    for cand in (slug_low, s_low, nospace_low):
        if cand in EFFECT_IDS:
            return cand
    # 한글·짧은 별칭
    aliases: dict[str, str] = {
        "고정": "none",
        "없음": "none",
        "static": "none",
        "좌": "pan_left",
        "왼쪽": "pan_left",
        "왼편": "pan_left",
        "좌측": "pan_left",
        "좌편": "pan_left",
        "우": "pan_right",
        "오른쪽": "pan_right",
        "오른편": "pan_right",
        "우측": "pan_right",
        "우편": "pan_right",
        "상": "pan_up",
        "위": "pan_up",
        "하": "pan_down",
        "아래": "pan_down",
        "줌인": "zoom_in",
        "확대": "zoom_in",
        "줌아웃": "zoom_out",
        "축소": "zoom_out",
        "좌우": "pan_right",  # 애매하면 우선 오른쪽으로
        "상하": "pan_down",
        "left": "pan_left",
        "right": "pan_right",
        "up": "pan_up",
        "down": "pan_down",
    }
    for cand in (s_low, slug_low, nospace_low):
        if cand in aliases:
            return aliases[cand]
    return "none"


def _static_pad_vf(w: int, h: int) -> str:
    return (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black"
    )


def build_image_motion_vf(
    width: int,
    height: int,
    fps: int,
    duration_sec: float,
    effect: str | None,
    *,
    motion_span_sec: float | None = None,
    motion_phase_sec: float | None = None,
) -> str:
    """자막 없이: 정지(scale+pad) 또는 zoompan 모션. duration은 이 클립 길이(초).

    motion_span_sec / motion_phase_sec 가 주어지면, 같은 정지 이미지가 SRT 여러 큐에 걸쳐
    이어질 때 **전체 구간(span)에 대해 효과를 한 번만** 적용하고, 이 클립은 그 타임라인의
    ``motion_phase_sec`` 지점부터 잘라낸 구간으로 렌더링합니다(큐마다 효과가 처음부터 반복되지 않음).
    """
    eff = normalize_effect(effect)
    w, h = int(width), int(height)
    fps = max(1, int(fps))
    if eff == "none":
        return _static_pad_vf(w, h)

    d_out = max(1, int(math.ceil(float(duration_sec) * fps)))
    use_span = (
        motion_span_sec is not None
        and motion_phase_sec is not None
        and float(motion_span_sec) > 1e-6
    )
    if use_span:
        d_run = max(1, int(math.ceil(float(motion_span_sec) * fps)))
        dm_run = max(1, d_run - 1)
        off = int(round(float(motion_phase_sec) * fps))
        if off < 0:
            off = 0
        max_off = max(0, d_run - d_out)
        if off > max_off:
            off = max_off
        d = d_out
        dm = dm_run
        d_tot = d_run
        on_e = f"(on+{off})"
    else:
        d = d_out
        dm = max(1, d - 1)
        d_tot = d
        on_e = "on"

    # zoompan 입력을 넉넉히 크게 (패딩 없이 increase)
    sw = max(int(w * 1.55) | 1, w + 32)
    sh = max(int(h * 1.55) | 1, h + 32)
    pre = f"scale={sw}:{sh}:force_original_aspect_ratio=increase:flags=lanczos"

    if eff == "zoom_in":
        # 쉼표는 FFmpeg 필터그래프에서 이스케이프
        zexpr = f"min(1.25\\,1+0.22*{on_e}/{dm})"
        xexpr = "(iw-iw/zoom)/2"
        yexpr = "(ih-ih/zoom)/2"
    elif eff == "zoom_out":
        zexpr = f"max(1\\,1.22-0.22*{on_e}/{dm})"
        xexpr = "(iw-iw/zoom)/2"
        yexpr = "(ih-ih/zoom)/2"
    elif eff == "pan_left":
        zexpr = "1.12"
        xexpr = f"(iw-iw/zoom)*({d_tot}-{on_e})/{dm}"
        yexpr = "(ih-ih/zoom)/2"
    elif eff == "pan_right":
        zexpr = "1.12"
        xexpr = f"(iw-iw/zoom)*{on_e}/{dm}"
        yexpr = "(ih-ih/zoom)/2"
    elif eff == "pan_up":
        zexpr = "1.12"
        xexpr = "(iw-iw/zoom)/2"
        yexpr = f"(ih-ih/zoom)*({d_tot}-{on_e})/{dm}"
    elif eff == "pan_down":
        zexpr = "1.12"
        xexpr = "(iw-iw/zoom)/2"
        yexpr = f"(ih-ih/zoom)*{on_e}/{dm}"
    else:
        return _static_pad_vf(w, h)

    zp = (
        f"zoompan=z='{zexpr}':x='{xexpr}':y='{yexpr}':"
        f"d={d}:s={w}x{h}:fps={fps}"
    )
    return f"{pre},{zp}"


def _same_compose_image_path(a: Path | None, b: Path | None) -> bool:
    if a is None or b is None:
        return False
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return False


def compose_motion_span_phase_per_cue(
    cues_ms: list[tuple[int, int, int, str]],
    resolved_imgs: list[Path | None],
) -> list[tuple[float | None, float | None]]:
    """compose 전용: 같은 정지 이미지가 **연속**된 SRT 큐 구간마다 (span_sec, phase_sec).

    - ``span_sec``: 해당 이미지가 보이는 연속 구간 전체 길이(초) — 모션 속도는 이 길이에 맞춤.
    - ``phase_sec``: 이 큐의 시작 시각이 그 구간 선두에서부터 몇 초 뒤인지 — zoompan 위상 오프셋.
    - 이미지가 없는(검은) 구간은 ``(None, None)`` (클립 단위 기존 동작).
    """
    n = len(cues_ms)
    if n == 0 or len(resolved_imgs) != n:
        return []
    out: list[tuple[float | None, float | None]] = []
    i = 0
    while i < n:
        img = resolved_imgs[i]
        if img is None:
            out.append((None, None))
            i += 1
            continue
        j = i
        while j + 1 < n and _same_compose_image_path(resolved_imgs[j + 1], img):
            j += 1
        t0_first = cues_ms[i][1]
        t1_last = cues_ms[j][2]
        run_start = t0_first / 1000.0
        run_end = t1_last / 1000.0
        span = max(1e-6, float(run_end - run_start))
        for k in range(i, j + 1):
            tk0 = cues_ms[k][1]
            phase = max(0.0, tk0 / 1000.0 - run_start)
            out.append((span, phase))
        i = j + 1
    return out


def load_compose_effects_lines(path: Path) -> list[str]:
    """한 줄에 하나: 효과 토큰 또는 비어 있음(none). # 로 시작하면 주석."""
    lines_out: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    for ln in text.splitlines():
        s = ln.split("#", 1)[0].strip()
        lines_out.append(s if s else "none")
    return lines_out


def effects_for_compose_cues(
    n_cues: int,
    *,
    effects_file: Path | None,
    images_dir: Path,
    default_effect: str,
) -> list[str]:
    """큐 개수만큼 효과 문자열 리스트. 파일이 짧으면 마지막 값으로 패딩."""
    base = normalize_effect(default_effect)
    if n_cues <= 0:
        return []

    path = effects_file
    if path is None:
        cand = images_dir / "compose_effects.txt"
        path = cand if cand.is_file() else None

    if path is None or not path.is_file():
        return [base] * n_cues

    raw = load_compose_effects_lines(path)
    effs = [normalize_effect(x) for x in raw]
    if not effs:
        return [base] * n_cues
    if len(effs) < n_cues:
        pad = effs[-1]
        effs = effs + [pad] * (n_cues - len(effs))
    elif len(effs) > n_cues:
        effs = effs[:n_cues]
    return effs


def scene_effective_motion(scene_effect: str | None, default_effect: str | None) -> str:
    """장면별 image_effect가 비어 있으면 프로젝트 기본값."""
    s = (scene_effect or "").strip()
    if s:
        return normalize_effect(s)
    return normalize_effect(default_effect)
