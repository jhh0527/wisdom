# NOVEL PACK stub — Agent replaces this block inside image.wuxiz.txt copy

Agent procedure:
1. Read `2_5_sceneImage/md/image.wuxiz.txt`
2. Keep everything OUTSIDE BEGIN_NOVEL_PACK … END_NOVEL_PACK
3. Insert a new pack built from NOVEL_BRIEF (outline below)
4. Write to `workspace/{slug}/art/image.prompt.txt`

```
>>>>>>>> BEGIN_NOVEL_PACK >>>>>>>>

################################################################################
# [팩-1] Character Bible
################################################################################
>>>>>>>> BEGIN_CHARACTER_BIBLE >>>>>>>>

【작품 메타】
- 작품명: {TITLE}
- character_data: characters.json
- 주인공 영문명: …
- 주인공 LOOK 나이: …
- ★ §0-L 차별 · Contrast · Character Anchor ★

0-L. 차별 매트릭스 (BRIEF 축으로 표 작성)
| 인물 | 눈 | 피부·체형 | 머리 | 복색 |

0-A. (주인공) Face Identity / State / LOOK / Anti-default / Anchor
0-B… (조연) LOOK / Anti-default / Anchor / contrast axes

<<<<<<<< END_CHARACTER_BIBLE <<<<<<<<

################################################################################
# [팩-2] Novel Visuals
################################################################################
>>>>>>>> BEGIN_NOVEL_VISUALS >>>>>>>>
(BRIEF 세계 키워드 → 영문 소품·장소·이펙트)
<<<<<<<< END_NOVEL_VISUALS <<<<<<<<

################################################################################
# [팩-3] Examples
################################################################################
>>>>>>>> BEGIN_NOVEL_EXAMPLES >>>>>>>>
매칭표 예시 2~3행 + 무효 예시 2줄
<<<<<<<< END_NOVEL_EXAMPLES <<<<<<<<

<<<<<<<< END_NOVEL_PACK <<<<<<<<
```
