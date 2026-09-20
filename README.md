# AI 동물 YouTube Shorts 스타터 (Python + MoviePy)

이 프로젝트는 **세로형 9:16 YouTube Shorts**를 로컬에서 렌더링하는 시작 템플릿입니다.  
기본 예시는 `길 잃은 아기 오리와 고양이` 한국어 AI 스토리(약 33초)로 구성되어 있습니다.

## 기본 출력

- 해상도: **1080×1920 (9:16)**
- 프레임: **30fps**
- 길이: 약 **20~35초**
- 장면별 캡션, 상단 타이틀, 페이드, 선택형 BGM 지원
- 출력 파일: `output/kitten_duckling_shorts.mp4`

## 1) 실행 환경 준비

### 필수
- Python 3.10+
- FFmpeg (시스템 설치)

Ubuntu 예시:
```bash
sudo apt-get update
sudo apt-get install -y ffmpeg fonts-nanum
```

의존성 설치:
```bash
pip install -r requirements.txt
```

## 2) 로컬 렌더링

```bash
python main.py
```

성공하면 `output/` 폴더에 MP4가 생성됩니다.

## 3) `config.json` 편집 방법

핵심 필드:
- `video.width`, `video.height`, `video.fps`
- `project_title`, `subtitle`
- `bgm` (선택)
- `output`
- `scenes[]` (`source`, `caption`, `duration`, `zoom`)

### 장면 이미지/클립 교체
- 이미지: `assets/images/...`
- 영상 클립: `assets/clips/...` (`.mp4`, `.mov`, `.mkv`, `.webm`, `.m4v`)

예시:
```json
{
  "source": "assets/images/my_scene_01.png",
  "caption": "여기에 원하는 한국어 자막",
  "duration": 4.8,
  "zoom": 1.04
}
```

### BGM 추가
1. 원하는 음원을 `assets/audio/` 아래에 저장
2. `config.json`의 `bgm` 경로를 해당 파일로 변경
3. 음원이 없으면 무음으로 렌더링됩니다.

## 4) 이미지가 없을 때 동작 (플레이스홀더)

- `assets/images/...` 경로의 파일이 없거나 열 수 없으면,
  코드가 자동으로 임시 장면(플레이스홀더)을 생성해 렌더링을 계속합니다.
- 단, 영상 클립 확장자(`.mp4` 등)로 지정한 장면 파일이 없으면 오류를 표시합니다.

## 5) AI 콘텐츠/저작권 가이드

- AI로 만든 스토리는 **실제 사건처럼 오해되지 않게** 제목/설명에 AI 생성 콘텐츠임을 명시하세요.
- 타인의 영상·이미지·음원을 무단 사용하지 말고, **직접 제작했거나 라이선스가 확인된 자산만** 사용하세요.
- 자동 업로드 기능은 포함하지 않습니다. 출력 파일을 직접 확인 후 업로드하세요.
