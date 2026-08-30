# 1_1_volumePlotToPrompt 사용자매뉴얼

**부 줄거리**를 젠스파크로 쓸 때 쓰는 **합본 프롬프트**를 만들고, 결과를 `N부/제N부줄거리.md`에 저장하는 GUI입니다.

현재 버전: **1.0.0**

장 본문(9~11천자)용은 `1_3_plotToPrompt`를 사용합니다. 이 프로그램은 **부 단위 줄거리**만 다룹니다.

---

## 1. 실행

| 방법 | 경로 |
|------|------|
| 권장 | `1_1_volumePlotToPrompt/dist/1_1_volumePlotToPrompt_gui.exe` |
| 소스 | `1_1_volumePlotToPrompt/run_volume_plot_gui.py` (개발용, `VOLUME_PLOT_GUI_SOURCE=1`) |

창 제목: `1_1_volumePlotToPrompt 1.0.0`

---

## 2. 하는 일

1. 작품 폴더·**부 번호**·(선택) 장 범위·목표 입력  
2. **합본 만들기** → 이전 부·바이블 발췌 + 작성 지시  
3. **합본 복사** → 젠스파크 붙여넣기  
4. 모델이 `<<<VOLUME_START>>>` … `<<<VOLUME_END>>>` 로 감싼 마크다운 출력  
5. **START/END로 저장** (또는 클립보드 감시) → `{작품}/{N}부/제{N}부줄거리.md`  
6. 이후 Cursor `@wuxia-add-plot` · `@wuxia-check-plot`으로 맵·정합

---

## 3. 합본에 들어가는 것

| 블록 | 내용 |
|------|------|
| WRITE_RULES | 발췌 (없으면 내장 부 줄거리 규칙) |
| characters | 앞부분 발췌 |
| foreshadowing | 발췌 |
| events | 파일 **끝** 부분 (최근 블록) |
| 직전 부 | 마스터 줄기 + **말미 2장** |
| 그 이전 부 | 각 **초압축 요약**(~800자) |
| 작성 지시 | 장 범위·목표·START/END 필수 |

체크박스로 WRITE_RULES / characters / foreshadowing / events를 끌 수 있습니다.

---

## 4. 필수 구분자

```
<<<VOLUME_START>>>
# 제N부 …
(유튜브 표 · 마스터 줄기 · ## 제N장 …)
<<<VOLUME_END>>>
```

---

## 5. 권장 흐름

```
합본 만들기 · 복사
  → 젠스파크 부 줄거리 작성
  → START/END 복사 · 저장
  → @wuxia-check-plot (직전 부 참고)
  → @wuxia-add-plot (맵·events·BRIEF 반영)
  → 장별 1_3_plotToPrompt
```

정합성 **검증**은 이 GUI가 하지 않습니다. Cursor `@wuxia-check-plot`을 사용하세요.

---

## 6. 자주 하는 질문

**Q. 1부 줄거리가 md가 아닌데?**  
`1부/제1부 시놉시스.txt` 등 `*줄거리*`·`*시놉*` 파일을 자동으로 찾습니다. 저장은 항상 `제N부줄거리.md`입니다.

**Q. 허브 탭?**  
`wuxia_hub`에 `1_1 volumePlot` 탭이 있습니다. 허브 exe 갱신은 「허브 빌드」 요청 시에만 합니다.

**Q. 장 본문도 되나요?**  
아니요. `1_3_plotToPrompt`를 쓰세요.
