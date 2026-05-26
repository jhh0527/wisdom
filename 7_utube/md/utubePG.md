# 7_utube — YouTube 인기·고조회 영상 조회

YouTube Data API v3로 **인기 급상승**·**조회수 TOP** 영상을 조회합니다.

## API 키

1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트 생성
2. **YouTube Data API v3** 활성화
3. API 키 발급
4. 아래 중 하나로 설정:
   - `7_utube/config/youtube_api.json` (`youtube_api.example.json` 참고)
   - 환경변수 `YOUTUBE_API_KEY`

## 실행

```bash
cd 7_utube
python run_utube_gui.py
```

### CLI

```bash
# 한국 인기 급상승 25개
python -m utube trending --region KR --max 25

# 최근 30일 조회수 순 (검색어 선택)
python -m utube search -q "요리" --days 30 --max 50

# CSV 저장
python -m utube trending --max 50 --csv output/youtube_trending.csv
```

## GUI 기능

- 컬럼 헤더 클릭 → 정렬 (같은 헤더 재클릭 시 오름·내림 전환, ▲▼ 표시)
- **엑셀 저장** → `.xlsx` (숫자·URL 하이퍼링크, 자동 필터)
- CSV 저장, YouTube 열기, URL 복사

## 모드

| 모드 | 설명 |
|------|------|
| 인기 급상승 | `videos.list` + `chart=mostPopular` (지역·카테고리) |
| 조회수 TOP 검색 | `search.list` + `order=viewCount` (기간·검색어) |

## 의존성

```bash
pip install -r requirements.txt
```

## 빌드

```bat
7_utube\build\build.bat
```

산출물: `7_utube/dist/7_utube_gui.exe`
