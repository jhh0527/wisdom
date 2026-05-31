

<!-- YouTube API 키: 7_utube/config/youtube_api.json (git 제외, GUI 자동 로드) -->

# 7_utube 프로그램 수정
- 키워드·조회수 TOP 검색: 검색어 비우면 기간·지역 **전체 검색**



# 4_2pngFileName 프로그램 수정
- **상태** 컬럼에서 대본 번호 선택 → `SRT_XXX.png`로 즉시 파일명 변경



# 3_ttsToVoice
- **원인**: 파트 첫 줄 ``[short pause][breathes][continues]`` 가 API 맨 앞 ``<break>`` 로 들어가 ElevenLabs 첫 음절이 작·깨짐
- **조치**: 선행 쉼은 ffmpeg 무음 삽입, API에는 본문만 전송 (``3_ttsToVoice/ttsToVoicePG.md``)

# 4_1pngToJpg 프로그램 수정



# 5_video 프로그램 수정 


# 5_2_ShortVideo 프로그램
- `5_2_ShortVideo/dist/5_2_shortvideo_gui.exe` — 9:16(1080×1920), **음성 사용** on/off
- 상세: `5_2_ShortVideo/md/shortVideoPG.md`



# 1_textTo700Text 




# 4_pngToJpg 프로그램 수정 (`4_1pngToJpg`)
 

# 4_srtToImage 프로그램 수정