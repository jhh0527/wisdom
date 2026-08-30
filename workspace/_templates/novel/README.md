# {TITLE} — 프로젝트 구조

유튜브 무협 소설용 Cursor 작업 공간. **바이블 + 사건 ID + 장 맵**으로 관리한다.

```
{TITLE}/
├── README.md
├── CURSOR_RULES.md
├── WRITE_RULES.md       ← 젠스파크 작성 헌법
├── REVIEW_PROMPT.md
├── events.md
├── chapter_map.md
├── world.md
├── characters.md
├── martial_arts.md
├── timeline.md
├── relationships.md
├── foreshadowing.md
├── review.md
├── briefs/
│   └── _TEMPLATE.md
├── 1부/
└── art/
    ├── characters.json          ← 2_5_sceneImage 런타임 LOOK
    ├── character_sheet_prompt.md
    └── image.prompt.txt         ← Genspark 씬 지침 (NOVEL PACK)
```

## 추천 작업 흐름

### 새로 쓸 장 (젠스파크)

1. `events.md`에 이 장 ID 확인 (없으면 승인 후 추가)
2. `briefs/CHAPTER_NN.md` 작성 (`_TEMPLATE` 복사)
3. 젠스파크 **새 채팅**에 `WRITE_RULES` + BRIEF + 인물 발췌 + 직전 장 꼬리만 첨부
4. 산출 후 비트·신규사건·글자 수 점검 → 본문 저장
5. 제목은 본문 확정 후 `chapter_map`에만 확정

### 이미지 (2_5_sceneImage)

1. GUI 프롬프트 = `art/image.prompt.txt` (또는 `2_5_sceneImage/md/image.{SLUG}.txt`)
2. 장 시작: `character_sheet_prompt.md` → `png/ref_characters.png`
3. 런타임 LOOK은 `art/characters.json`

### 검수

`REVIEW_PROMPT.md` 단계를 한 번에 하나. 사건 순서는 `events.md` 기준.
