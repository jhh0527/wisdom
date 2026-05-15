프로그램은 루트 하위에 폴더구조로 생성한다.
build는 빌드에 필요한 프로그램 및 파일이 위치한다.
dist는 파이썬 빌드 후 exe 프로그램이 위치한다.
output은 exe 실행 후 산출물이 위치한다.

wisdom 루트의 all 폴더에는 루트 이하에 생성된 모든 프로그램에 빌드를 수행할 수 있는 build 파일, 모든 프로그램을 탭 구조로 실행할 수 있는 exe 파일이 위치한 dist, 실행 파일 실행 후 산출물 폴더 output 디렉토리가 위치한다.
개별 프로그램 파일은 루트 폴더에서 개별 프로그램 디렉토리로 이동한다.

```
wisdom
   |- all
   |   |- build
   |   |- dist
   |   `- output
   |- elevenlabs_tts_subtitle
   |   |- build
   |   |- dist
   |   `- output
   |- image_prompt_pipeline
   |   |- build
   |   |- dist
   |   `- output
   |- knowledge_channel_tts
   |   |- build
   |   |- dist
   |   `- output
   |- manuscript_700_splitter
   |   |- build
   |   |- dist
   |   `- output
   |- tts_audio_pipeline
   |   |- build
   |   |- dist
   |   `- output
   ...
```
