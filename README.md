# 동물 촌캉스 1분 영상 자동 제작 프로젝트

유튜브용 16:9 영상을 **Python + MoviePy**로 자동 편집하는 프로젝트입니다.

원본 영상을 그대로 복제하는 것이 아니라,  
**강아지 · 고양이 · 팬더 · 토끼가 시골 여행을 하는 새로운 1분 이야기**로 구성했습니다.

## 만들어지는 영상

- 해상도: 1280×720 (16:9)
- 길이: 약 60초
- 8개 장면 × 7.5초
- 자동 자막
- 천천히 확대되는 줌 효과
- 장면 시작/끝 페이드
- 선택 사항: BGM 자동 반복/믹싱
- 출력: `output/animal_trip.mp4`

## 폴더 구조

```text
animal_trip_video_project/
├─ main.py
├─ config.json
├─ requirements.txt
├─ assets/
│  ├─ images/
│  │  ├─ 01_departure.jpg
│  │  ├─ 02_country_road.jpg
│  │  ├─ 03_field.jpg
│  │  ├─ 04_house.jpg
│  │  ├─ 05_snack.jpg
│  │  ├─ 06_play.jpg
│  │  ├─ 07_evening.jpg
│  │  └─ 08_sunset.jpg
│  ├─ clips/
│  ├─ audio/
│  │  └─ bgm.mp3
│  └─ fonts/
├─ output/
└─ .github/workflows/render.yml
```

이미지 파일이 없어도 `main.py`가 임시 장면을 만들어 테스트할 수 있습니다.

## 1. 가장 쉬운 방법: GitHub Actions

휴대폰에서도 가능합니다.

1. 이 프로젝트 전체를 GitHub 저장소에 업로드합니다.
2. `assets/images/` 안에 자신의 장면 이미지 8장을 넣습니다.
3. 필요하면 `assets/audio/bgm.mp3`를 넣습니다.
4. GitHub 저장소의 **Actions** 메뉴를 엽니다.
5. **Render animal trip video**를 선택합니다.
6. **Run workflow**를 누릅니다.
7. 작업 완료 후 `animal-trip-video` 아티팩트를 받습니다.

## 2. PC에서 실행

Python 3.10 이상 권장.

```bash
pip install -r requirements.txt
python main.py
```

완성 파일:

```text
output/animal_trip.mp4
```

## 3. 이미지 대신 짧은 AI 영상 사용

`config.json`의 `source`를 이미지가 아니라 MP4로 바꿔도 됩니다.

예:

```json
{
  "source": "assets/clips/01_departure.mp4",
  "caption": "여행 출발! 오늘은 시골로 떠나요",
  "duration": 7.5,
  "zoom": 1.0
}
```

Veo, Gemini, Runway, Firefly 등에서 만든 짧은 클립을 넣으면  
코드가 순서대로 연결하고 자막과 BGM을 붙입니다.

## 4. 장면 순서

1. 여행 출발
2. 시골길 걷기
3. 들판에서 놀기
4. 시골집 도착
5. 마당 간식 시간
6. 네 동물이 함께 놀기
7. 저녁 산책
8. 노을 엔딩

## 5. 자막/시간 변경

`config.json`만 수정하면 됩니다.

```json
"caption": "여기에 원하는 자막",
"duration": 7.5
```

8개 장면의 `duration` 합이 60이면 1분 영상이 됩니다.

## 저작권 주의

다른 유튜브 영상의 실제 영상/음원/자막을 그대로 복사하지 말고,  
직접 만든 이미지·AI 생성 콘텐츠·사용 허가가 있는 BGM을 사용하세요.
