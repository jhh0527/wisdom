# 5_2_ShortVideo

`5_video` 기반 **세로 쇼츠(9:16)** 합성 GUI.

## 기능

- 화면 **1080×1920 (9:16)** 고정
- **음성 사용** 체크: 켜면 `3_ttsToVoice` MP3 + SRT, 끄면 SRT 타임라인만으로 무음 합성
- 입력: SRT, 이미지 폴더(`4_srtToImage` 등), 선택 MP3
- 출력: `{작업폴더}/5_2_ShortVideo/output/shorts_yyyymmdd.mp4`

## 실행

- GUI: `5_2_ShortVideo/dist/5_2_shortvideo_gui.exe`
- 소스: `run_shortvid_gui.py`

## 빌드

`5_2_ShortVideo/build/build.bat` → `dist/5_2_shortvideo_gui.exe`

FFmpeg는 PATH 또는 `wisdom/tools/ffmpeg/bin` 필요.
