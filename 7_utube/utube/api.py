from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from utube.format_util import parse_iso8601_duration, parse_iso8601_duration_seconds
from utube.models import VideoItem

_API = "https://www.googleapis.com/youtube/v3"


class YouTubeApiError(RuntimeError):
    pass


def _get(path: str, params: dict[str, str], api_key: str) -> dict:
    q = dict(params)
    q["key"] = api_key
    url = f"{_API}/{path}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except OSError:
            pass
        msg = body
        try:
            err = json.loads(body).get("error", {})
            msg = err.get("message") or body
        except (json.JSONDecodeError, AttributeError):
            pass
        raise YouTubeApiError(f"YouTube API HTTP {e.code}: {msg}") from e
    except urllib.error.URLError as e:
        raise YouTubeApiError(f"네트워크 오류: {e.reason}") from e
    return json.loads(raw)


def _items_from_videos_response(data: dict) -> list[VideoItem]:
    out: list[VideoItem] = []
    for it in data.get("items") or []:
        vid = str(it.get("id") or "")
        if not vid:
            continue
        sn = it.get("snippet") or {}
        st = it.get("statistics") or {}
        cd = it.get("contentDetails") or {}
        vc = st.get("viewCount")
        lc = st.get("likeCount")
        cc = st.get("commentCount")
        iso_dur = str(cd.get("duration") or "")
        out.append(
            VideoItem(
                video_id=vid,
                title=str(sn.get("title") or "").replace("\n", " "),
                channel=str(sn.get("channelTitle") or ""),
                view_count=int(vc) if vc is not None else 0,
                like_count=int(lc) if lc is not None else None,
                comment_count=int(cc) if cc is not None else None,
                published_at=str(sn.get("publishedAt") or ""),
                duration=parse_iso8601_duration(iso_dur),
                duration_seconds=parse_iso8601_duration_seconds(iso_dur),
                category_id=str(sn.get("categoryId") or "") or None,
            )
        )
    return out


def fetch_trending(
    api_key: str,
    *,
    region: str = "KR",
    max_results: int = 50,
    category_id: str | None = None,
) -> list[VideoItem]:
    """지역별 인기 급상승(mostPopular) 영상."""
    if not api_key.strip():
        raise YouTubeApiError("YouTube API 키가 없습니다. config/youtube_api.json 또는 YOUTUBE_API_KEY 를 설정하세요.")
    max_results = max(1, min(50, int(max_results)))
    params: dict[str, str] = {
        "part": "snippet,statistics,contentDetails",
        "chart": "mostPopular",
        "regionCode": region.upper()[:2],
        "maxResults": str(max_results),
    }
    if category_id:
        params["videoCategoryId"] = category_id
    data = _get("videos", params, api_key)
    return _items_from_videos_response(data)


def _search_video_ids(
    api_key: str,
    *,
    query: str,
    region: str,
    days: int,
    max_results: int,
    order: str,
    require_query: bool,
) -> list[str]:
    q = query.strip()
    if require_query and not q:
        raise YouTubeApiError("검색어를 입력하세요.")
    max_results = max(1, min(50, int(max_results)))
    days = max(1, min(365, int(days)))
    after = datetime.now(timezone.utc) - timedelta(days=days)
    search_params: dict[str, str] = {
        "part": "snippet",
        "type": "video",
        "order": order,
        "regionCode": region.upper()[:2],
        "publishedAfter": after.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "maxResults": str(max_results),
    }
    if q:
        search_params["q"] = q
    search_data = _get("search", search_params, api_key)
    ids: list[str] = []
    for it in search_data.get("items") or []:
        vid = (it.get("id") or {}).get("videoId")
        if vid:
            ids.append(str(vid))
    return ids


def _videos_by_ids(api_key: str, ids: list[str]) -> list[VideoItem]:
    if not ids:
        return []
    videos_data = _get(
        "videos",
        {
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(ids),
            "maxResults": str(len(ids)),
        },
        api_key,
    )
    by_id = {v.video_id: v for v in _items_from_videos_response(videos_data)}
    return [by_id[i] for i in ids if i in by_id]


def fetch_keyword_search(
    api_key: str,
    *,
    query: str,
    region: str = "KR",
    days: int = 30,
    max_results: int = 50,
) -> list[VideoItem]:
    """키워드로 영상 검색 (관련도 순)."""
    if not api_key.strip():
        raise YouTubeApiError("YouTube API 키가 없습니다.")
    ids = _search_video_ids(
        api_key,
        query=query,
        region=region,
        days=days,
        max_results=max_results,
        order="relevance",
        require_query=True,
    )
    return _videos_by_ids(api_key, ids)


def fetch_top_by_views(
    api_key: str,
    *,
    query: str = "",
    region: str = "KR",
    days: int = 30,
    max_results: int = 50,
) -> list[VideoItem]:
    """키워드(선택) + 기간 내 업로드 영상을 조회수 순으로 검색."""
    if not api_key.strip():
        raise YouTubeApiError("YouTube API 키가 없습니다.")
    ids = _search_video_ids(
        api_key,
        query=query,
        region=region,
        days=days,
        max_results=max_results,
        order="viewCount",
        require_query=False,
    )
    return _videos_by_ids(api_key, ids)
