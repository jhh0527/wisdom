# 검신귀환록 — 프로젝트 구조

유튜브 무협 소설용 Cursor 작업 공간. **바이블 + 사건 ID + 장 맵**으로 관리한다.

```
검신귀환록/
├── README.md
├── CURSOR_RULES.md
├── WRITE_RULES.md       ← 젠스파크 작성 헌법
├── REVIEW_PROMPT.md
├── events.md            ← 사건 ID·선후 (장 번호 없음)
├── chapter_map.md       ← 장 ↔ 사건 ID ↔ 유튜브 제목
├── world.md
├── characters.md
├── martial_arts.md
├── timeline.md
├── relationships.md
├── foreshadowing.md
├── review.md
├── briefs/
│   └── _TEMPLATE.md     ← 장별 BRIEF (젠스파크 주입력)
├── 1부/ … 5부/          ← 부별 줄거리·본문
└── art/
```

## 추천 작업 흐름

### 이미 쓴 부 (예: 2부)

1. 본문을 원본으로 `events.md` 갱신
2. `chapter_map.md`·부 줄거리·유튜브 제목을 본문에 맞춤
3. `timeline` / `foreshadowing` / `characters` 동기화

### 새로 쓸 장 (젠스파크)

1. `events.md`에 이 장 ID가 있는지 확인 (없으면 승인 후 추가)
2. `briefs/CHAPTER_NN.md` 작성 (`_TEMPLATE` 복사)
3. 젠스파크 **새 채팅**에 `WRITE_RULES` + BRIEF + 인물 발췌 + 직전 장 꼬리만 첨부
4. 산출 후 비트·신규사건·글자 수 점검 → 본문 파일 저장
5. 제목은 본문 확정 후 `chapter_map`에만 확정

### 검수

`REVIEW_PROMPT.md` 단계를 한 번에 하나. 사건 순서·사망 시점은 `events.md` 기준.

## 추상 품질

감동·긴장·빌드업은 설정 검수와 분리해 `REVIEW_PROMPT.md`의 「문예 리뷰」를 쓴다.
