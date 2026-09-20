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

1. `config.json`, `assets/` 등 렌더링에 필요한 파일을 수정한 뒤 **반드시 커밋/푸시**합니다.
2. GitHub 저장소 상단에서 **Actions** 탭을 엽니다.
3. 왼쪽 워크플로 목록에서 **Render animal video (수동 실행)** 을 클릭합니다.
4. 오른쪽에서 **Run workflow** 버튼을 누른 뒤 `run_mode`를 선택합니다.
   - `render`: 영상 렌더링(MP4)
   - `prompts`: 장면 프롬프트 JSON 생성
   - `both`: 프롬프트 생성 + 영상 렌더링
5. 실행할 브랜치를 확인하고 **Run workflow**를 누릅니다.
6. 실행이 끝나면 run 상세 화면의 **Artifacts**에서 결과를 다운로드합니다.
   - 영상: `rendered-animal-video`
   - 프롬프트: `scene-image-prompts`

참고:
- 실행 시간은 장면 수/길이에 따라 보통 몇 분 정도 걸릴 수 있습니다.
- 워크플로는 저장소에 커밋된 `config.json`과 에셋 파일 기준으로 렌더링합니다.

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

## 6. 장면용 AI 이미지 프롬프트 자동 생성

`config.json`의 `scenes`를 읽어서 장면별 이미지 생성 프롬프트를 자동으로 만듭니다.

```bash
python main.py --generate-image-prompts
```

생성 결과:

```text
output/scene_image_prompts.json
```

옵션으로 출력 경로를 직접 지정할 수 있습니다.

```bash
python main.py --generate-image-prompts --prompts-output output/my_prompts.json
```

`--prompts-output` 경로는 프로젝트 폴더 내부 경로만 사용할 수 있습니다(상대 경로는 실행 위치 기준, 절대 경로도 가능).

GitHub Actions에서도 동일하게 생성할 수 있습니다.

1. **Actions** → **Render animal video (수동 실행)** → **Run workflow**
2. `run_mode`를 `prompts`(또는 `both`)로 선택
3. 완료 후 **Artifacts**에서 `scene-image-prompts` 다운로드

## 7. 쇼츠 배치 생성 (여러 편 자동 제작)

여러 개의 설정 파일을 한 번에 순차 렌더링할 수 있습니다.

1) 프로젝트 루트에 배치 설정 파일(예: `batch_config.json`)을 만듭니다.

```json
{
  "jobs": [
    {
      "name": "beach-episode-1",
      "config": "config.json"
    },
    {
      "name": "beach-episode-2",
      "config": "configs/episode2.json",
      "overrides": {
        "output": "output/episode2.mp4"
      }
    }
  ]
}
```

2) 배치 렌더링 실행:

```bash
python main.py --batch-render --batch-file batch_config.json
```

옵션:
- `--batch-file`을 생략하면 기본값으로 `batch_config.json`을 사용합니다.
- `--batch-file` 경로는 명령 실행 위치(현재 디렉터리) 기준 상대 경로이며, 프로젝트 폴더 내부 파일만 허용됩니다.
- `overrides`는 각 작업의 설정을 덮어쓸 때 사용합니다(예: `output`, `project_title`, `subtitle`).
- `jobs[].config` 경로는 **배치 파일 위치 기준 상대 경로**로 해석됩니다.

## 저작권 주의

다른 유튜브 영상의 실제 영상/음원/자막을 그대로 복사하지 말고,  
직접 만든 이미지·AI 생성 콘텐츠·사용 허가가 있는 BGM을 사용하세요.
