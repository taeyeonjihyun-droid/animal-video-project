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
   - 배치 ZIP: `batch-rendered-videos-zip` (batch/batch-both 모드에서 생성된 MP4가 있을 때)
   - 배치 요약: `batch-execution-summary` (batch/batch-prompts/batch-both에서 `batch_summary_report=true`일 때)
   - 배치 로그: `batch-run-logs` (batch/batch-prompts/batch-both 실행 시)
   - 배치 모드 사용 시 `batch_file` 입력(기본 `batch.json`)으로 파일 경로를 지정할 수 있습니다.
   - 배치 모드(`batch`, `batch-prompts`, `batch-both`)에서는 `batch_retry_count`로 job별 실패 재시도 횟수(0~3)를 지정할 수 있습니다.
   - 배치 모드(`batch`, `batch-prompts`, `batch-both`)에서는 `batch_summary_report`로 실행 시간/성공 개수 요약 JSON 생성 여부를 선택할 수 있습니다.
   - 배치 렌더링에서 일부 job이 실패해도 **나머지 job은 계속 실행**되며, 성공한 MP4와 로그가 먼저 업로드된 뒤 워크플로가 실패로 표시됩니다.

참고:
- 실행 시간은 장면 수/길이에 따라 보통 몇 분 정도 걸릴 수 있습니다.
- 워크플로는 저장소에 커밋된 `config.json`과 에셋 파일 기준으로 렌더링합니다.

## 2. PC에서 실행

Python 3.10 이상 권장.

```bash
pip install -r requirements.txt
python main.py
python main.py --config config.json
python batch.py --batch-config batch.json
```

단일 렌더링 완성 파일:

```text
output/animal_trip.mp4
```

배치 실행 시에는 `batch.json`에 정의된 각 job의 MP4가 `output/` 아래에 생성됩니다.

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
python main.py --config config.json --generate-image-prompts
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

여러 개의 설정 파일을 한 번에 순차 렌더링할 수 있습니다. 기본 예시 파일은 프로젝트 루트의 `batch.json`입니다.

### 7-1. `batch.json` 형식

각 job은 최소 `config`를 가져야 하며, 필요하면 `overrides.output`으로 결과 파일명을 개별 지정할 수 있습니다.

```json
{
  "jobs": [
    {
      "name": "short-01",
      "config": "config.json",
      "overrides": {
        "project_title": "아기 동물 쇼츠 1편",
        "subtitle": "첫 번째 세로 쇼츠 예시",
        "output": "output/short-01.mp4"
      }
    },
    {
      "name": "short-02",
      "config": "config.json",
      "overrides": {
        "project_title": "아기 동물 쇼츠 2편",
        "subtitle": "두 번째 세로 쇼츠 예시",
        "output": "output/short-02.mp4"
      }
    },
    {
      "name": "short-03",
      "config": "config.json",
      "overrides": {
        "project_title": "아기 동물 쇼츠 3편",
        "subtitle": "세 번째 세로 쇼츠 예시",
        "output": "output/short-03.mp4"
      }
    }
  ]
}
```

추가 옵션:

- `jobs[].config`: **배치 파일 위치 기준 상대 경로** 또는 저장소 내부 절대 경로
- `jobs[].overrides`: 원본 설정 일부를 job별로 덮어쓰기
- `jobs[].overrides` 안의 경로형 값(`output`, `image_prompt_output`, `bgm`, `scenes[].source`)은 **배치 파일 위치 기준 상대 경로**로 써도 자동 보정됩니다.
- `prompt_filename_pattern`: `batch-prompts` 모드에서 프롬프트 파일명 규칙 지정  
  사용 가능 변수: `{index}`, `{index2}`, `{job}`, `{job_slug}`, `{config}`, `{stem}`

여러 job이 같은 출력명을 가리키거나 이미 파일이 존재하면 `_02`, `_03`처럼 번호를 붙여 덮어쓰기를 막습니다.

### 7-2. 로컬 명령

단일 렌더링:

```bash
python main.py
python main.py --config config.json
```

배치 렌더링:

```bash
python batch.py --batch-config batch.json
```

기존 CLI도 그대로 사용할 수 있습니다.

```bash
python main.py --batch-render --batch-file batch.json
```

실패 재시도:

```bash
python batch.py --batch-config batch.json --retry-failed 2
```

요약 리포트 저장:

```bash
python batch.py --batch-config batch.json --summary-report output/batch_render_summary.json
```

### 7-3. GitHub Actions에서 배치 실행하는 정확한 순서

1. `config.json`, `batch.json`, 필요한 `assets/` 파일을 **커밋/푸시**합니다.
2. GitHub 저장소 상단에서 **Actions** 탭을 엽니다.
3. 왼쪽에서 **Render animal video (수동 실행)** 워크플로를 클릭합니다.
4. 오른쪽 상단 **Run workflow** 버튼을 누릅니다.
5. `run_mode`에서 원하는 모드를 고릅니다.
   - `render`: 기본 단일 렌더링
   - `batch`: 여러 편 일괄 렌더링
   - `batch-prompts`: 여러 편 프롬프트 JSON만 생성
   - `batch-both`: 프롬프트 생성 + 여러 편 렌더링
6. 배치 모드라면 `batch_file`에 사용할 배치 파일 경로를 입력합니다(기본 `batch.json`).
7. 필요하면 `batch_retry_count`와 `batch_summary_report`를 설정합니다.
8. 브랜치를 확인한 뒤 **Run workflow**를 클릭합니다.
9. 실행이 끝나면 run 상세 화면 하단 **Artifacts**에서 결과를 다운로드합니다.
   - `rendered-animal-video`: 생성된 MP4 묶음
   - `batch-rendered-videos-zip`: 배치 MP4 ZIP
   - `batch-run-logs`: 배치 로그
   - `batch-execution-summary`: 배치 요약 JSON

### 7-4. 일부 job이 실패할 때 동작

- 각 job은 독립적으로 검증·실행됩니다.
- 한 job이 실패해도 **뒤의 job은 계속 실행**됩니다.
- 콘솔과 요약 JSON에 성공/실패 여부, 출력 경로, 오류 메시지가 함께 남습니다.
- 모든 job이 끝난 뒤 하나라도 실패가 있으면 **프로세스 종료 코드는 1**이므로 로컬 명령과 GitHub Actions 모두 실패로 표시됩니다.
- GitHub Actions에서는 실패로 끝나더라도 **성공한 MP4와 로그 아티팩트가 먼저 업로드**됩니다.

### 7-5. 운영 팁

- 원본 `config.json`, `batch.json`, 추가 설정 파일, `assets/`는 반드시 Git에 커밋해 두세요.
- 생성된 `output/*.mp4` 파일은 용량이 크므로 **커밋하지 않는 것을 권장**합니다.
- `--summary-report`를 사용하면 `schema_version`, `retry_successes`, `job_results`, `stopped_on_failure` 필드가 포함된 JSON 요약을 남길 수 있습니다.

### `batch-execution-summary` JSON 예시

성공 케이스(1개 job 성공):

```json
{
  "schema_version": "1.2",
  "mode": "batch-render",
  "batch_file": "/home/runner/work/animal-video-project/animal-video-project/batch_config.json",
  "total_jobs": 1,
  "success_count": 1,
  "failure_count": 0,
  "failed_jobs": [],
  "retry_successes": [],
  "job_results": [
    {
      "job": "batch-01",
      "status": "success",
      "attempts_used": 1,
      "max_attempts": 1,
      "retried": false,
      "succeeded_on_attempt": 1,
      "output_path": "/home/runner/work/animal-video-project/animal-video-project/output/test.mp4",
      "error": null
    }
  ],
  "stopped_on_failure": false,
  "duration_seconds": 0.123,
  "generated_at": "2026-09-21T13:00:00+00:00"
}
```

실패 케이스(1개 job 실패):

```json
{
  "schema_version": "1.2",
  "mode": "batch-render",
  "batch_file": "/home/runner/work/animal-video-project/animal-video-project/batch_config.json",
  "total_jobs": 1,
  "success_count": 0,
  "failure_count": 1,
  "failed_jobs": ["fail-job"],
  "retry_successes": [],
  "job_results": [
    {
      "job": "fail-job",
      "status": "failure",
      "attempts_used": 2,
      "max_attempts": 2,
      "retried": true,
      "succeeded_on_attempt": null,
      "output_path": "/home/runner/work/animal-video-project/animal-video-project/output/test.mp4",
      "error": "always fail"
    }
  ],
  "stopped_on_failure": true,
  "duration_seconds": 0.456,
  "generated_at": "2026-09-21T13:00:10+00:00"
}
```

### 스키마 마이그레이션 노트 (1.1 → 1.2)

- `schema_version` 값이 `1.2`로 변경되었습니다.
- 신규 필드가 추가되었습니다.
  - `job_results`: job 단위 최종 실행 결과 상세
  - `stopped_on_failure`: 실패로 배치가 중단되었는지 여부
- 기존 `retry_successes` 필드는 유지되며, 재시도 후 성공한 job만 별도 요약합니다.

### batch-both 수동 실행 테스트 시 아티팩트 샘플 캡처 형식

아래와 같이 **Run 상세 > Artifacts**에서 확인할 수 있습니다.

```text
rendered-animal-video
batch-rendered-videos-zip
batch-scene-image-prompts
batch-execution-summary
batch-run-logs
```

## 저작권 주의

다른 유튜브 영상의 실제 영상/음원/자막을 그대로 복사하지 말고,  
직접 만든 이미지·AI 생성 콘텐츠·사용 허가가 있는 BGM을 사용하세요.
