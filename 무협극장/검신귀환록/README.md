# 검신귀환록 — 프로젝트 구조

유튜브 무협 소설용 Cursor 작업 공간. **한 개의 긴 파일** 대신 바이블 + 장별 파일로 관리한다.

```
검신귀환록/
├── README.md
├── CURSOR_RULES.md      ← 작품 규칙
├── REVIEW_PROMPT.md     ← 검수 프롬프트 (복붙용)
├── world.md
├── characters.md
├── martial_arts.md
├── timeline.md
├── relationships.md
├── foreshadowing.md
├── review.md            ← 검수 결과 누적
├── art/
│   └── character_sheet_prompt.md
└── chapters/
    ├── 001.md … 012.md  ← 1부
    └── 013.md …         ← 이후 장
```

루트의 `.cursor/rules/`에 일관성·장 작성 규칙이 등록되어 있다.

## 추천 작업 흐름

1. **쓸 때**: Agent에게 「013장 작성. 바이블 참조」 — Rules가 자동 참조를 유도한다.
2. **고칠 때**: 충돌이 보이면 `review.md`에 남기거나 바로 수정.
3. **검수할 때**: `REVIEW_PROMPT.md`의 7단계를 **한 번에 하나**씩 Agent에 돌린다.

## 추상 품질

감동·긴장·빌드업은 설정 검수와 분리해 `REVIEW_PROMPT.md`의 「문예 리뷰」를 쓴다.
