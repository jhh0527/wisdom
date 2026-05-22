# -*- coding: utf-8 -*-
"""3_ttsToVoice: ElevenLabs TTS 블록 → 파트별 MP3·SRT·JSON 합성 + 수동 `all` 병합.

- 각 파트(`1.{}`, `2.{}` …)별로 `part01`, `part02` … 이름으로 MP3·SRT·JSON 을 생성합니다.
- 파트 내부 MP3 병합은 ffmpeg(concat, `-c copy` → 실패 시 재인코딩) 후, 실패 시 바이너리 이어붙임입니다.
- 통합 `all.*` 파일은 **별도 버튼**으로 출력 폴더의 기존 `part*.` 파일만 읽어 생성합니다.
- 출력 폴더는 항상 `3_ttsToVoice/output/` 입니다.
- 자막 구간 길이는 세그먼트 MP3를 ffprobe 한 값을 사용하고, 파트 전체 길이에 맞게 미세 보정합니다.
- TTS가 마침표·쉼표·느낌표·물음표 등으로 끝나지 않으면 다음 줄과 한 API 호출로 이어서 합성합니다.
"""

from __future__ import annotations

import json
import re
import threading
import traceback
import tkinter as tk
from collections import OrderedDict
from pathlib import Path
from tkinter import font as tkfont, messagebox, scrolledtext, ttk

from elsub import __version__
from elsub.elevenlabs_client import (
    concat_mp3_files,
    concat_mp3_files_binary_from_paths,
    concat_mp3_files_ffmpeg,
    strip_tts_tags,
    synthesize_mp3,
)
from elsub.media_probe import ffprobe_duration_sec
from elsub.parser import CaptionLine, parse_knowledgetts_block
from elsub.settings import (
    config_file_path,
    copy_bundled_example_if_needed,
    load_settings,
    resolve_output_dir,
)
from elsub.srt_gen import build_srt_from_durations, estimate_duration_ms, merge_srt_files
from elsub.tts_merge import (
    group_entries_for_synthesis,
    merge_group_tts,
    split_duration_ms,
)


_PART_MP3 = re.compile(r"^part(\d+)\.mp3$", re.IGNORECASE)


def _font() -> tuple[str, int]:
    try:
        f = tkfont.nametofont("TkDefaultFont")
        return (f.actual("family"), max(10, int(f.actual("size"))))
    except tk.TclError:
        return ("맑은 고딕", 10)


def _group_by_part(entries: list[CaptionLine]) -> "OrderedDict[str, list[CaptionLine]]":
    groups: "OrderedDict[str, list[CaptionLine]]" = OrderedDict()
    for e in entries:
        groups.setdefault(e.part_id, []).append(e)
    return groups


def _part_label(part_id: str, max_pad: int) -> str:
    try:
        return f"part{int(part_id):0{max_pad}d}"
    except ValueError:
        return f"part{part_id}"


def discover_part_mp3_paths(output_dir: Path) -> list[Path]:
    """`part01.mp3`, `part02.mp3`, … 를 숫자 순으로 반환합니다."""
    found: list[tuple[int, Path]] = []
    for p in output_dir.iterdir():
        if not p.is_file():
            continue
        m = _PART_MP3.match(p.name)
        if m:
            found.append((int(m.group(1)), p))
    found.sort(key=lambda x: x[0])
    return [x[1] for x in found]


def build_merged_json_from_part_files(
    part_mp3_paths: list[Path],
    all_mp3: Path,
    all_srt: Path,
) -> dict:
    """`partNN.json` 을 읽어 통합 JSON 문서를 만듭니다."""
    parts_meta: list[dict] = []
    all_segments: list[dict] = []
    cum_ms = 0
    model_id = ""

    for mp in part_mp3_paths:
        jp = mp.with_suffix(".json")
        raw = json.loads(jp.read_text(encoding="utf-8"))
        if not model_id:
            model_id = str(raw.get("model_id") or "").strip()
        pid = str(raw.get("part_id", ""))
        segs = raw.get("segments") or []
        if not isinstance(segs, list):
            segs = []
        parts_meta.append(
            {
                "part_id": pid,
                "lines": len(segs),
                "mp3": str(raw.get("part_mp3") or str(mp.resolve())),
                "srt": str(raw.get("part_srt") or str(mp.with_suffix(".srt").resolve())),
                "json": str(jp.resolve()),
                "merge_method": str(raw.get("merge_method") or ""),
            }
        )
        for s in segs:
            if not isinstance(s, dict):
                continue
            row = dict(s)
            row["part_id"] = pid
            sm = int(row.get("start_ms_estimate") or 0)
            em = int(row.get("end_ms_estimate") or 0)
            row["start_ms_estimate"] = cum_ms + sm
            row["end_ms_estimate"] = cum_ms + em
            all_segments.append(row)
        dur = int(raw.get("duration_ms_estimate") or 0)
        cum_ms += dur

    total_from_probe = 0
    probe_parts_ok = True
    for mp in part_mp3_paths:
        try:
            total_from_probe += int(round(ffprobe_duration_sec(mp) * 1000))
        except Exception:
            probe_parts_ok = False
            break
    if not probe_parts_ok or total_from_probe <= 0:
        total_from_probe = cum_ms

    return {
        "merged_mp3": str(all_mp3.resolve()),
        "subtitle_srt": str(all_srt.resolve()),
        "model_id": model_id or "eleven_multilingual_v2",
        "merge_method": "manual: part*.json 기준 병합",
        "total_duration_ms_estimate": total_from_probe,
        "parts": parts_meta,
        "segments": all_segments,
    }


def main() -> None:
    root = tk.Tk()
    root.title(f"3_ttsToVoice {__version__}")
    root.minsize(640, 560)
    root.geometry("820x640")
    fam, sz = _font()
    root.option_add("*Font", (fam, sz))

    copy_bundled_example_if_needed()
    cfg_path = config_file_path()
    out_dir = resolve_output_dir()
    status = tk.StringVar()
    if cfg_path.is_file():
        status.set("대기 중")
    else:
        status.set(f"{cfg_path.name} 없음 — exe와 같은 폴더에 두고 elevenlabs_api_key 등을 설정하세요.")

    frm = ttk.Frame(root, padding=10)
    frm.grid(row=0, column=0, sticky="nsew")
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)
    frm.grid_rowconfigure(2, weight=1)
    frm.grid_columnconfigure(0, weight=1)

    ttk.Label(
        frm,
        text=(
            f"API 키·Voice ID·모델은 아래 파일에서만 설정합니다.\n{cfg_path}\n"
            f"출력 폴더(고정): {out_dir}\n"
            "① 파트 생성: part01.{mp3,srt,json} …  ② 병합: 출력 폴더의 part* 를 읽어 all.{mp3,srt,json} 생성"
        ),
        foreground="gray",
        justify="left",
    ).grid(row=0, column=0, sticky="w", pady=(0, 8))

    ttk.Label(frm, text="TTS 변환 결과 붙여넣기 (원본: / TTS: 줄)").grid(row=1, column=0, sticky="sw")
    txt = scrolledtext.ScrolledText(frm, height=18, wrap="word", font=(fam, sz))
    txt.grid(row=2, column=0, sticky="nsew", pady=(4, 6))
    frm.grid_rowconfigure(2, weight=1)

    log_fr = ttk.LabelFrame(frm, text="실행 로그", padding=4)
    log_fr.grid(row=3, column=0, sticky="nsew", pady=(0, 6))
    log_fr.grid_rowconfigure(0, weight=1)
    log_fr.grid_columnconfigure(0, weight=1)
    frm.grid_rowconfigure(3, weight=0)
    log = scrolledtext.ScrolledText(log_fr, height=8, wrap="word", font=(fam, max(9, sz - 1)))

    def log_line(s: str) -> None:
        log.insert(tk.END, s.rstrip() + "\n")
        log.see(tk.END)

    log.grid(row=0, column=0, sticky="nsew")

    busy = {"v": False}

    def run_gen() -> None:
        if busy["v"]:
            return
        s = load_settings()
        key = s.elevenlabs_api_key.strip()
        vid = s.voice_id.strip()
        model = (s.model_id or "eleven_multilingual_v2").strip()

        if not key:
            messagebox.showwarning(
                "설정",
                f"{cfg_path.name} 에 elevenlabs_api_key 를 넣으세요.\n\n{cfg_path}",
            )
            return
        if not vid:
            messagebox.showwarning("설정", f"{cfg_path.name} 에 voice_id 를 넣으세요.")
            return

        block = txt.get("1.0", "end-1c")
        entries = parse_knowledgetts_block(block)
        if not entries:
            messagebox.showerror("파싱", "유효한 줄이 없습니다.\n`1-1 원본: … TTS: …` 형식인지 확인하세요.")
            return

        groups = _group_by_part(entries)
        total_lines = len(entries)

        busy["v"] = True
        btn_run.state(["disabled"])
        btn_merge.state(["disabled"])
        status.set(f"처리 중… (0/{total_lines})")
        log.delete("1.0", tk.END)

        def work() -> None:
            try:
                output_dir = resolve_output_dir()
                output_dir.mkdir(parents=True, exist_ok=True)
                seg_root = output_dir / "segments"
                seg_root.mkdir(parents=True, exist_ok=True)

                pad = max(2, len(str(len(groups))))
                done = 0

                for pid, group_entries in groups.items():
                    part_lbl = _part_label(pid, pad)
                    part_mp3 = output_dir / f"{part_lbl}.mp3"
                    part_srt = part_mp3.with_suffix(".srt")
                    part_json = part_mp3.with_suffix(".json")

                    part_seg_paths: list[Path] = []
                    part_seg_blobs: list[bytes] = []
                    seg_durs_ms: list[int] = []
                    line_segment_mp3: list[str] = []

                    synth_groups = group_entries_for_synthesis(group_entries)
                    for gidx, grp in enumerate(synth_groups, start=1):
                        merged_tts = merge_group_tts(grp)

                        def upd(n: int = done) -> None:
                            status.set(f"음성 합성… {part_lbl} ({n}/{total_lines})")

                        root.after(0, upd)
                        blob = synthesize_mp3(key, vid, merged_tts, model_id=model)
                        seg_p = seg_root / f"{part_lbl}_{gidx:04d}.mp3"
                        seg_p.write_bytes(blob)
                        part_seg_paths.append(seg_p)
                        part_seg_blobs.append(blob)

                        try:
                            group_ms = int(round(ffprobe_duration_sec(seg_p) * 1000))
                        except Exception:
                            group_ms = estimate_duration_ms(merged_tts)
                        group_ms = max(1, group_ms)
                        weights = [len(strip_tts_tags(e.tts).strip()) or 1 for e in grp]
                        line_durs = split_duration_ms(group_ms, weights)
                        seg_path = str(seg_p.resolve())
                        for e, dms in zip(grp, line_durs):
                            done += 1
                            root.after(0, upd)
                            seg_durs_ms.append(dms)
                            line_segment_mp3.append(seg_path)

                    part_merge_note = ""
                    try:
                        concat_mp3_files_ffmpeg(part_seg_paths, part_mp3)
                        part_merge_note = "ffmpeg"
                    except Exception as ff_err:
                        concat_mp3_files(part_seg_blobs, str(part_mp3))
                        part_merge_note = f"binary-fallback ({ff_err})"

                    try:
                        merged_ms = int(round(ffprobe_duration_sec(part_mp3) * 1000))
                    except Exception:
                        merged_ms = sum(seg_durs_ms)
                    ssum = sum(seg_durs_ms)
                    if merged_ms > 0 and ssum > 0 and merged_ms != ssum:
                        scaled = [max(1, int(round(d * merged_ms / ssum))) for d in seg_durs_ms]
                        drift = merged_ms - sum(scaled)
                        scaled[-1] = max(1, scaled[-1] + drift)
                        seg_durs_ms = scaled

                    part_cur_ms = 0
                    part_seg_json: list[dict] = []
                    for i, (e, dur) in enumerate(zip(group_entries, seg_durs_ms), start=1):
                        part_seg_json.append(
                            {
                                "index": i,
                                "caption_id": e.caption_id,
                                "original": e.original,
                                "tts": e.tts,
                                "segment_mp3": line_segment_mp3[i - 1],
                                "duration_ms_estimate": dur,
                                "start_ms_estimate": part_cur_ms,
                                "end_ms_estimate": part_cur_ms + dur,
                            }
                        )
                        part_cur_ms += dur

                    part_srt_body, _, _ = build_srt_from_durations(
                        [(e.original, d) for e, d in zip(group_entries, seg_durs_ms)]
                    )
                    part_srt.write_text(part_srt_body, encoding="utf-8")

                    part_doc = {
                        "part_id": pid,
                        "part_mp3": str(part_mp3.resolve()),
                        "part_srt": str(part_srt.resolve()),
                        "model_id": model,
                        "merge_method": part_merge_note,
                        "segment_count": len(part_seg_paths),
                        "duration_ms_estimate": part_cur_ms,
                        "segments": part_seg_json,
                    }
                    part_json.write_text(
                        json.dumps(part_doc, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )

                    def log_part(p: str = part_lbl, m: str = part_merge_note) -> None:
                        log_line(f"[{p}] mp3/srt/json 생성 완료 (mp3 병합: {m})")

                    root.after(0, log_part)

                def ok() -> None:
                    status.set("완료")
                    log_line("")
                    log_line(f"출력 폴더: {output_dir}")
                    log_line(f"세그먼트 폴더: {seg_root}")
                    log_line("통합 all.* 은 「병합 파일 생성」 버튼으로 만드세요.")
                    messagebox.showinfo(
                        "완료",
                        f"파트 수: {len(groups)}\n"
                        f"출력 폴더: {output_dir}\n\n"
                        "통합 all.{mp3,srt,json} 은 「병합 파일 생성」으로 수동 생성할 수 있습니다.\n"
                        "자막 시간은 각 세그먼트 MP3(ffprobe) 길이에 맞춥니다. ffprobe 없으면 글자 수 추정으로 대체됩니다.",
                    )

                root.after(0, ok)
            except Exception:
                err = traceback.format_exc()

                def fail() -> None:
                    status.set("오류")
                    log_line(err)
                    messagebox.showerror("오류", "실패했습니다. 하단 실행 로그를 복사해 확인하세요.")

                root.after(0, fail)
            finally:

                def fin() -> None:
                    busy["v"] = False
                    btn_run.state(["!disabled"])
                    btn_merge.state(["!disabled"])

                root.after(0, fin)

        threading.Thread(target=work, daemon=True).start()

    def run_merge_all() -> None:
        if busy["v"]:
            return
        output_dir = resolve_output_dir()
        part_mp3s = discover_part_mp3_paths(output_dir)
        if not part_mp3s:
            messagebox.showerror(
                "병합",
                f"{output_dir} 에 part01.mp3, part02.mp3 … 가 없습니다.\n먼저 파트 생성을 실행하세요.",
            )
            return
        missing: list[str] = []
        for mp in part_mp3s:
            if not mp.with_suffix(".srt").is_file():
                missing.append(f"{mp.stem}.srt")
            if not mp.with_suffix(".json").is_file():
                missing.append(f"{mp.stem}.json")
        if missing:
            messagebox.showerror("병합", "다음 파일이 없습니다:\n" + "\n".join(missing))
            return

        busy["v"] = True
        btn_run.state(["disabled"])
        btn_merge.state(["disabled"])
        status.set("병합 중…")
        log.delete("1.0", tk.END)

        def work() -> None:
            try:
                all_mp3 = output_dir / "all.mp3"
                all_srt = output_dir / "all.srt"
                all_json = output_dir / "all.json"

                concat_mp3_files_binary_from_paths(part_mp3s, all_mp3)

                srt_paths = [p.with_suffix(".srt") for p in part_mp3s]
                merged_srt, _timeline_end = merge_srt_files(srt_paths, part_mp3_paths=part_mp3s)
                all_srt.write_text(merged_srt, encoding="utf-8")

                merged_doc = build_merged_json_from_part_files(part_mp3s, all_mp3, all_srt)
                all_json.write_text(json.dumps(merged_doc, ensure_ascii=False, indent=2), encoding="utf-8")

                def ok() -> None:
                    status.set("병합 완료")
                    log_line(f"all.mp3 ← {len(part_mp3s)}개 파트 (바이너리 이어붙임)")
                    log_line(f"all.srt ← part*.srt 병합 (큐 번호=시작 시각 초, 예: 00:07:29→449)")
                    log_line(f"all.json ← part*.json 메타 병합")
                    log_line(f"MP3: {all_mp3}")
                    log_line(f"SRT: {all_srt}")
                    log_line(f"JSON: {all_json}")
                    messagebox.showinfo(
                        "병합 완료",
                        f"all.mp3\nall.srt\nall.json\n\n폴더: {output_dir}",
                    )

                root.after(0, ok)
            except Exception:
                err = traceback.format_exc()

                def fail() -> None:
                    status.set("병합 오류")
                    log_line(err)
                    messagebox.showerror("병합 오류", "실패했습니다. 실행 로그를 확인하세요.")

                root.after(0, fail)
            finally:

                def fin() -> None:
                    busy["v"] = False
                    btn_run.state(["!disabled"])
                    btn_merge.state(["!disabled"])

                root.after(0, fin)

        threading.Thread(target=work, daemon=True).start()

    btn_row = ttk.Frame(frm)
    btn_row.grid(row=4, column=0, sticky="w", pady=(0, 4))
    btn_run = ttk.Button(
        btn_row,
        text="파트별 MP3·SRT·JSON 생성 (TTS 합성)",
        command=run_gen,
    )
    btn_run.grid(row=0, column=0, sticky="w", padx=(0, 8))
    btn_merge = ttk.Button(
        btn_row,
        text="병합 파일 생성 (all.mp3 / all.srt / all.json)",
        command=run_merge_all,
    )
    btn_merge.grid(row=0, column=1, sticky="w")
    ttk.Label(frm, textvariable=status).grid(row=5, column=0, sticky="w")

    ttk.Label(
        frm,
        text="elsub_config.json 은 Git·공유에 넣지 마세요.",
        foreground="gray",
    ).grid(row=6, column=0, sticky="w", pady=(10, 0))

    root.mainloop()


if __name__ == "__main__":
    main()
