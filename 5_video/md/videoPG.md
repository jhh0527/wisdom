# 공통
변경된 프로그램이 있으면 빌드 파일을 수정한다.


# 5_video 프로그램 수정
이미지효과 버튼 클릭시 하위의 큐도 클릭한 이미지를 사용하는 구간에만 동일 효과를 적용한다.
이미지효과 적용 속도는 천천히 진행하도록 한다.


# 4_pngToJpg 프로그램 수정
png 파일을 jpg 파일로 변환한다.
변환시 파일크기를 줄여서 유튜브 업로드용으로 변환한다.


# 4_srtToImage 프로그램 수정






# 산출물 위치
영상파일은 다음 경로에 위치시킨다.
C:\cursor\wisdom-1\5_video\output (O)
C:\Users\PC\AppData\Local\Temp (x)

동영상 생성시 각각의 파일 설정은 아래가 디폴트로 되게 한다.
-음성: C:\cursor\wisdom-1\3_ttsToVoice\output\all.mp3
-자막: C:\cursor\wisdom-1\3_ttsToVoice\output\all.srt
-이미지 : C:\cursor\wisdom-1\4_srtToImage\output\
-출력 : C:\cursor\wisdom-1\5_video\output\

# 이미지 효과
미지랜덤효과 버튼을 추가하고 클릭시 srt 번호 마다 다음과 같이 지정된다.
이미지가 바뀔때마다 아래 순으로 이미지효과가 변경된다.
 좌팬-> 우팬 -> 상팬 -> 하팬-> 줌인 -> 줌아웃-> 고정
 큐마다 이미지효과가 변경되지 않는다.
 
 예: 
1 | SRT001.jpg | 좌팬 | SRT1 맵핑
1 | SRT001.jpg | 좌팬 | 이전 유지
1 | SRT001.jpg | 좌팬 | 이전 유지
1 | SRT001.jpg | 좌팬 | 이전 유지
1 | SRT006.jpg | 우팬 | SRT6 맵핑
1 | SRT006.jpg | 우팬 | 이전 유지
1 | SRT006.jpg | 우팬 | 이전 유지
1 | SRT006.jpg | 우팬 | 이전 유지
...

