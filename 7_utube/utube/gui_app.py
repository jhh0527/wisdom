"""YouTube 인기·고조회 영상 조회 GUI."""

from __future__ import annotations

import csv
import threading
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from utube.api import YouTubeApiError, fetch_top_by_views, fetch_trending
from utube.categories import category_label
from utube.config import load_api_key, module_root, save_api_key
from utube.export_util import export_videos_excel
from utube.format_util import duration_display_to_seconds, format_count, format_published
from utube.models import VideoItem

_REGIONS = ("KR", "US", "JP", "GB", "DE", "FR", "IN", "BR")
_MODES = ("인기 급상승", "조회수 TOP 검색")
_DAYS = ("7", "30", "90", "180", "365")
_CATEGORIES = (
    ("전체", ""),
    ("음악", "10"),
    ("게임", "20"),
    ("뉴스", "25"),
    ("과학/기술", "28"),
    ("교육", "27"),
    ("엔터", "24"),
    ("스포츠", "17"),
)

_COLS = ("rank", "views", "likes", "date", "duration", "channel", "category", "title")
_COL_LABELS = {
    "rank": "#",
    "views": "조회수",
    "likes": "좋아요",
    "date": "업로드",
    "duration": "길이",
    "channel": "채널",
    "category": "카테고리",
    "title": "제목",
}
_DEFAULT_DESC_COLS = frozenset({"views", "likes", "date", "duration"})


def _sort_key(col: str, v: VideoItem, index: int) -> object:
    if col == "rank":
        return index
    if col == "views":
        return v.view_count
    if col == "likes":
        return v.like_count if v.like_count is not None else -1
    if col == "date":
        return v.published_at or ""
    if col == "duration":
        return duration_display_to_seconds(v.duration)
    if col == "channel":
        return v.channel.casefold()
    if col == "category":
        return category_label(v.category_id).casefold()
    if col == "title":
        return v.title.casefold()
    return index


def main() -> None:
    root = tk.Tk()
    root.title("7_utube — YouTube 인기·고조회 영상")
    root.minsize(960, 520)
    root.geometry("1100x640")

    rows_state: list[VideoItem] = []
    sort_col: str = "views"
    sort_reverse: bool = True

    frm = ttk.Frame(root, padding=8)
    frm.pack(fill=tk.BOTH, expand=True)
    frm.columnconfigure(0, weight=1)
    frm.rowconfigure(3, weight=1)

    # API 키
    key_fr = ttk.LabelFrame(frm, text="YouTube Data API v3 키", padding=6)
    key_fr.grid(row=0, column=0, sticky="ew", pady=(0, 6))
    key_fr.columnconfigure(1, weight=1)
    ttk.Label(key_fr, text="API 키").grid(row=0, column=0, sticky="w", padx=(0, 6))
    api_var = tk.StringVar(value=load_api_key())
    api_ent = ttk.Entry(key_fr, textvariable=api_var, show="*")
    api_ent.grid(row=0, column=1, sticky="ew")
    show_key = tk.BooleanVar(value=False)

    def toggle_show() -> None:
        api_ent.configure(show="" if show_key.get() else "*")

    ttk.Checkbutton(key_fr, text="표시", variable=show_key, command=toggle_show).grid(row=0, column=2, padx=4)
    ttk.Label(
        key_fr,
        text="Google Cloud Console → YouTube Data API v3 활성화 후 키 발급. 저장 시 config/youtube_api.json",
        font=("", 8),
    ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))

    def save_key() -> None:
        k = api_var.get().strip()
        if not k:
            messagebox.showwarning("API 키", "키를 입력하세요.")
            return
        save_api_key(k)
        messagebox.showinfo("API 키", "저장했습니다.")

    ttk.Button(key_fr, text="키 저장", command=save_key).grid(row=0, column=3, padx=(6, 0))

    # 조회 옵션
    opt_fr = ttk.LabelFrame(frm, text="조회 조건", padding=6)
    opt_fr.grid(row=1, column=0, sticky="ew", pady=(0, 6))
    mode_var = tk.StringVar(value=_MODES[0])
    region_var = tk.StringVar(value="KR")
    days_var = tk.StringVar(value="30")
    max_var = tk.StringVar(value="50")
    query_var = tk.StringVar(value="")
    cat_var = tk.StringVar(value="전체")

    ttk.Label(opt_fr, text="모드").grid(row=0, column=0, sticky="w")
    mode_cb = ttk.Combobox(opt_fr, textvariable=mode_var, values=_MODES, state="readonly", width=14)
    mode_cb.grid(row=0, column=1, sticky="w", padx=(4, 12))

    ttk.Label(opt_fr, text="지역").grid(row=0, column=2, sticky="w")
    ttk.Combobox(opt_fr, textvariable=region_var, values=_REGIONS, state="readonly", width=6).grid(
        row=0, column=3, sticky="w", padx=(4, 12)
    )

    ttk.Label(opt_fr, text="카테고리").grid(row=0, column=4, sticky="w")
    ttk.Combobox(
        opt_fr,
        textvariable=cat_var,
        values=[c[0] for c in _CATEGORIES],
        state="readonly",
        width=10,
    ).grid(row=0, column=5, sticky="w", padx=(4, 12))

    ttk.Label(opt_fr, text="검색어").grid(row=1, column=0, sticky="w", pady=(6, 0))
    query_ent = ttk.Entry(opt_fr, textvariable=query_var, width=28)
    query_ent.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(4, 12), pady=(6, 0))

    ttk.Label(opt_fr, text="기간(일)").grid(row=1, column=2, sticky="w", pady=(6, 0))
    days_cb = ttk.Combobox(opt_fr, textvariable=days_var, values=_DAYS, state="readonly", width=6)
    days_cb.grid(row=1, column=3, sticky="w", padx=(4, 12), pady=(6, 0))

    ttk.Label(opt_fr, text="개수").grid(row=1, column=4, sticky="w", pady=(6, 0))
    ttk.Combobox(opt_fr, textvariable=max_var, values=("25", "50"), state="readonly", width=6).grid(
        row=1, column=5, sticky="w", padx=(4, 12), pady=(6, 0)
    )

    def on_mode_change(_e=None) -> None:
        is_search = mode_var.get() == _MODES[1]
        query_ent.configure(state="normal" if is_search else "disabled")
        days_cb.configure(state="readonly" if is_search else "disabled")

    mode_cb.bind("<<ComboboxSelected>>", on_mode_change)
    on_mode_change()

    status_var = tk.StringVar(value="API 키를 입력한 뒤 「조회」를 누르세요. 컬럼 헤더 클릭으로 정렬합니다.")
    ttk.Label(frm, textvariable=status_var).grid(row=2, column=0, sticky="w", pady=(0, 4))

    # 테이블
    tree = ttk.Treeview(frm, columns=_COLS, show="headings", height=16, selectmode="browse")
    tree.column("rank", width=40, anchor="center", stretch=False)
    tree.column("views", width=72, anchor="e", stretch=False)
    tree.column("likes", width=72, anchor="e", stretch=False)
    tree.column("date", width=88, anchor="center", stretch=False)
    tree.column("duration", width=56, anchor="center", stretch=False)
    tree.column("channel", width=120, anchor="w", stretch=False)
    tree.column("category", width=88, anchor="center", stretch=False)
    tree.column("title", width=360, anchor="w", stretch=True)
    ysb = ttk.Scrollbar(frm, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=ysb.set)
    tree.grid(row=3, column=0, sticky="nsew")
    ysb.grid(row=3, column=1, sticky="ns")

    def update_headings() -> None:
        for col in _COLS:
            label = _COL_LABELS[col]
            if col == sort_col:
                label += " ▼" if sort_reverse else " ▲"
            tree.heading(col, text=label, command=lambda c=col: on_sort_column(c))

    def apply_sort() -> None:
        indexed = list(enumerate(rows_state))
        indexed.sort(key=lambda pair: _sort_key(sort_col, pair[1], pair[0]), reverse=sort_reverse)
        rows_state[:] = [v for _, v in indexed]

    def refresh_table() -> None:
        sel_id = tree.selection()[0] if tree.selection() else None
        tree.delete(*tree.get_children())
        for i, v in enumerate(rows_state):
            tree.insert(
                "",
                tk.END,
                iid=str(i),
                values=(
                    i + 1,
                    format_count(v.view_count),
                    format_count(v.like_count),
                    format_published(v.published_at),
                    v.duration,
                    v.channel[:36],
                    category_label(v.category_id)[:16],
                    v.title[:100],
                ),
            )
        update_headings()
        if sel_id and sel_id in tree.get_children():
            tree.selection_set(sel_id)
            tree.focus(sel_id)

    def on_sort_column(col: str) -> None:
        nonlocal sort_col, sort_reverse
        if not rows_state:
            return
        if sort_col == col:
            sort_reverse = not sort_reverse
        else:
            sort_col = col
            sort_reverse = col in _DEFAULT_DESC_COLS
        apply_sort()
        refresh_table()
        arrow = "내림차순" if sort_reverse else "오름차순"
        status_var.set(f"{len(rows_state)}개 · {_COL_LABELS[col]} {arrow} 정렬")

    update_headings()

    def selected_video() -> VideoItem | None:
        sel = tree.selection()
        if not sel:
            return None
        i = int(sel[0])
        if 0 <= i < len(rows_state):
            return rows_state[i]
        return None

    def fill_table(rows: list[VideoItem]) -> None:
        nonlocal sort_col, sort_reverse
        rows_state.clear()
        rows_state.extend(rows)
        sort_col = "views"
        sort_reverse = True
        apply_sort()
        refresh_table()
        status_var.set(f"{len(rows_state)}개 영상 · 헤더 클릭 정렬 · 더블클릭 YouTube 열기")

    def category_id() -> str | None:
        label = cat_var.get()
        for name, cid in _CATEGORIES:
            if name == label and cid:
                return cid
        return None

    def do_fetch() -> None:
        key = api_var.get().strip() or load_api_key()
        if not key:
            messagebox.showwarning("조회", "YouTube API 키를 입력·저장하세요.")
            return
        try:
            mx = int(max_var.get())
        except ValueError:
            mx = 50

        def work() -> None:
            try:
                if mode_var.get() == _MODES[0]:
                    data = fetch_trending(
                        key,
                        region=region_var.get(),
                        max_results=mx,
                        category_id=category_id(),
                    )
                else:
                    data = fetch_top_by_views(
                        key,
                        query=query_var.get(),
                        region=region_var.get(),
                        days=int(days_var.get()),
                        max_results=mx,
                    )
            except (YouTubeApiError, ValueError) as e:
                root.after(0, lambda: messagebox.showerror("조회 실패", str(e)))
                root.after(0, lambda: status_var.set("조회 실패"))
                return
            root.after(0, lambda: fill_table(data))

        status_var.set("조회 중…")
        threading.Thread(target=work, daemon=True).start()

    def _export_rows() -> list[VideoItem]:
        return list(rows_state)

    def export_csv() -> None:
        rows = _export_rows()
        if not rows:
            messagebox.showinfo("CSV", "먼저 조회하세요.")
            return
        default = module_root() / "output" / "youtube_videos.csv"
        path = filedialog.asksaveasfilename(
            title="CSV 저장",
            initialdir=str(default.parent),
            initialfile=default.name,
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(
                ["순위", "제목", "채널", "카테고리", "조회수", "좋아요", "댓글", "업로드", "길이", "URL"]
            )
            for i, v in enumerate(rows, start=1):
                w.writerow(
                    [
                        i,
                        v.title,
                        v.channel,
                        category_label(v.category_id),
                        v.view_count,
                        v.like_count or "",
                        v.comment_count or "",
                        format_published(v.published_at),
                        v.duration,
                        v.url,
                    ]
                )
        messagebox.showinfo("CSV", f"저장: {p}")

    def export_excel() -> None:
        rows = _export_rows()
        if not rows:
            messagebox.showinfo("엑셀", "먼저 조회하세요.")
            return
        default = module_root() / "output" / "youtube_videos.xlsx"
        path = filedialog.asksaveasfilename(
            title="엑셀 저장",
            initialdir=str(default.parent),
            initialfile=default.name,
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
        )
        if not path:
            return
        p = Path(path)
        if p.suffix.lower() != ".xlsx":
            p = p.with_suffix(".xlsx")
        try:
            export_videos_excel(p, rows)
        except RuntimeError as e:
            messagebox.showerror("엑셀", str(e))
            return
        except OSError as e:
            messagebox.showerror("엑셀", f"저장 실패: {e}")
            return
        messagebox.showinfo("엑셀", f"저장: {p}")

    btn_fr = ttk.Frame(frm)
    btn_fr.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    ttk.Button(btn_fr, text="조회", command=do_fetch).pack(side=tk.LEFT, padx=(0, 6))

    def open_youtube() -> None:
        v = selected_video()
        if v:
            webbrowser.open(v.url)

    ttk.Button(btn_fr, text="YouTube에서 열기", command=open_youtube).pack(side=tk.LEFT, padx=(0, 6))

    def copy_url() -> None:
        v = selected_video()
        if not v:
            messagebox.showinfo("URL", "목록에서 영상을 선택하세요.")
            return
        root.clipboard_clear()
        root.clipboard_append(v.url)
        status_var.set(f"URL 복사: {v.url}")

    ttk.Button(btn_fr, text="URL 복사", command=copy_url).pack(side=tk.LEFT, padx=(0, 6))
    ttk.Button(btn_fr, text="CSV 저장", command=export_csv).pack(side=tk.LEFT, padx=(0, 6))
    ttk.Button(btn_fr, text="엑셀 저장", command=export_excel).pack(side=tk.LEFT, padx=(0, 6))

    tree.bind("<Double-1>", lambda _e: open_youtube())

    root.mainloop()


if __name__ == "__main__":
    main()
