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
   - `batch`: 배치 설정 파일 기준 여러 영상 순차 렌더링
   - `batch-prompts`: 배치 설정 파일 기준 각 job의 프롬프트 JSON만 순차 생성
   - `batch-both`: 배치 설정 파일 기준 프롬프트 JSON 생성 + 영상 순차 렌더링
5. 실행할 브랜치를 확인하고 **Run workflow**를 누릅니다.
6. 실행이 끝나면 run 상세 화면의 **Artifacts**에서 결과를 다운로드합니다.
   - 영상: `rendered-animal-video`
   - 프롬프트: `scene-image-prompts`
   - 배치 프롬프트: `batch-scene-image-prompts` (batch-prompts/batch-both 모드 성공 시)
   - 배치 ZIP: `batch-rendered-videos-zip` (batch/batch-both 모드 성공 시)
   - 배치 요약: `batch-execution-summary` (batch/batch-prompts/batch-both에서 `batch_summary_report=true`일 때)
   - 배치 로그: `batch-run-logs` (batch/batch-prompts/batch-both 실행 시)
   - 배치 모드 사용 시 `batch_file` 입력(기본 `batch_config.json`)으로 파일 경로를 지정할 수 있습니다.
   - 배치 모드(`batch`, `batch-prompts`, `batch-both`)에서는 `batch_retry_count`로 job별 실패 재시도 횟수(0~3)를 지정할 수 있습니다.
   - 배치 모드(`batch`, `batch-prompts`, `batch-both`)에서는 `batch_summary_report`로 실행 시간/성공 개수 요약 JSON 생성 여부를 선택할 수 있습니다.

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
  "prompt_filename_pattern": "{index2}_{job_slug}_prompts.json",
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

`prompt_filename_pattern`(선택)을 사용하면 `batch-prompts` 모드에서 job별 프롬프트 파일명을 자동 규칙으로 만들 수 있습니다.  
사용 가능한 변수: `{index}`, `{index2}`, `{job}`, `{job_slug}`, `{config}`, `{stem}`

2) 배치 렌더링 실행:

```bash
python main.py --batch-render --batch-file batch_config.json
```

실패 재시도를 적용하려면:

```bash
python main.py --batch-render --batch-file batch_config.json --retry-failed 2
```

실행 요약 리포트를 저장하려면:

```bash
python main.py --batch-render --batch-file batch_config.json --summary-report output/batch_render_summary.json
```

GitHub Actions에서 배치 실행:

1. **Actions** → **Render animal video (수동 실행)** → **Run workflow**
2. `run_mode`를 `batch`로 선택
3. 필요하면 `batch_file` 입력값을 수정(예: `configs/batch_week1.json`)
4. 필요하면 `batch_retry_count`를 설정(예: `2`)
5. 필요하면 `batch_summary_report`를 설정(기본 `true`)
6. 완료 후 **Artifacts**에서 결과 다운로드
   - `rendered-animal-video`: `render`/`both` 모드에서는 단일 MP4, `batch`/`batch-both` 모드에서는 `output/` 접두사를 제거한 정규화 상대경로 구조의 여러 MP4 파일
   - `batch-rendered-videos-zip`: 배치 결과 MP4 ZIP 묶음
7. 실패 시 run 요약 화면에 **배치 실패 원인 요약 로그**가 자동으로 출력되며, `batch-failure-log` 아티팩트로 원본 로그를 받을 수 있습니다.

GitHub Actions에서 배치 프롬프트만 생성:

1. **Actions** → **Render animal video (수동 실행)** → **Run workflow**
2. `run_mode`를 `batch-prompts`로 선택
3. 필요하면 `batch_file` 입력값을 수정(예: `configs/batch_week1.json`)
4. 필요하면 `batch_retry_count`를 설정(예: `2`)
5. 필요하면 `batch_summary_report`를 설정(기본 `true`)
6. 완료 후 **Artifacts**에서 `batch-scene-image-prompts` 다운로드

GitHub Actions에서 배치 프롬프트+렌더링 함께 실행:

1. **Actions** → **Render animal video (수동 실행)** → **Run workflow**
2. `run_mode`를 `batch-both`로 선택
3. 필요하면 `batch_file` 입력값을 수정(예: `configs/batch_week1.json`)
4. 필요하면 `batch_retry_count`를 설정(예: `2`)
5. 필요하면 `batch_summary_report`를 설정(기본 `true`)
6. 완료 후 **Artifacts**에서 아래 결과를 함께 다운로드
   - `rendered-animal-video`
   - `batch-rendered-videos-zip`
   - `batch-scene-image-prompts`
   - `batch-execution-summary` (`batch_summary_report=true`일 때)
   - `batch-run-logs`

옵션:
- `--batch-file`을 생략하면 기본값으로 `batch_config.json`을 사용합니다.
- `--batch-file` 경로는 명령 실행 위치(현재 디렉터리) 기준 상대 경로이며, 프로젝트 폴더 내부 파일만 허용됩니다.
- `--retry-failed`는 배치 작업 실패 시 job별 재시도 횟수를 지정합니다(0 이상의 정수).
- `--summary-report`를 지정하면 배치 실행 시간/성공 개수/실패 개수 요약 JSON을 저장합니다.
  - 고정 스키마 버전 필드: `schema_version` (현재 `1.2`)
  - 재시도 성공 결과 필드: `retry_successes` (`job`, `succeeded_on_attempt`)
  - job 단위 실행 결과 필드: `job_results` (`job`, `status`, `attempts_used`, `max_attempts`, `retried`, `succeeded_on_attempt`, `output_path`, `error`)
  - 중도 중단 여부 필드: `stopped_on_failure`
- `prompt_filename_pattern`을 지정하면 `batch-prompts` 모드에서 파일명 규칙을 커스터마이즈할 수 있습니다(파일명만 허용, `.json` 자동 보정).
- `overrides`는 각 작업의 설정을 덮어쓸 때 사용합니다(예: `output`, `project_title`, `subtitle`).
- `jobs[].config` 경로는 **배치 파일 위치 기준 상대 경로**로 해석됩니다.
- 여러 작업에서 최종 출력 경로가 중복되거나, 이미 같은 경로의 파일이 존재하면(기본값/`overrides.output` 포함) 파일명에 `_02`처럼 번호를 붙여 덮어쓰기를 방지합니다.

## 저작권 주의

다른 유튜브 영상의 실제 영상/음원/자막을 그대로 복사하지 말고,  
직접 만든 이미지·AI 생성 콘텐츠·사용 허가가 있는 BGM을 사용하세요.
