# Animal travel video workflow

This repository now includes a practical, runnable workflow for generating a **15-second animal travel-preparation video package** for an AI video provider.

The target scene is:

- in front of a cozy house in warm early-morning sunlight
- dog, cat, red panda, giant panda, and fennec fox
- all five carrying small travel bags or backpacks
- dog wagging happily, cat checking luggage, red panda packing snacks, giant panda wearing a large sun hat, fennec fox looking around excitedly with moving ears
- gentle teamwork, gathering together, and preparing to depart
- stylized, heartwarming, high-quality 3D animated feature-film look
- no dialogue, no text, no watermarks

## What was added

- `animal_travel_preparation_scene.json`: structured scene specification
- `generate_video_workflow.py`: provider-agnostic workflow runner
- `.env.example`: environment-based configuration template
- `tests/test_generate_video_workflow.py`: lightweight consistency validation

The existing `main.py` MoviePy renderer remains available for local assembly experiments, but the new workflow is the primary path for AI video generation.

## Scene package contents

The structured scene spec includes:

- master prompt
- negative prompt
- character bible
- consistency rules
- a 15-second four-shot plan

## Prerequisites

- Python 3.10+
- `pip install -r requirements.txt`

No extra dependencies are required for the workflow packager.

## Configuration

Copy the example env file if you want local overrides:

```bash
cp .env.example .env
```

Environment variables:

- `VIDEO_PROVIDER`: `dry-run` or `generic-webhook`
- `VIDEO_SCENE_SPEC`: scene spec JSON path  
  default: `animal_travel_preparation_scene.json`
- `VIDEO_OUTPUT_DIR`: output directory  
  default: `output/video_generation_package`
- `VIDEO_API_URL`: required only for `generic-webhook`
- `VIDEO_API_KEY`: optional bearer token for `generic-webhook`
- `VIDEO_API_TIMEOUT`: optional HTTP timeout in seconds

## Dry-run usage

Dry-run generates the complete package without calling an external API:

```bash
python generate_video_workflow.py --dry-run
```

Output files are written to:

```text
output/video_generation_package/
```

Expected files:

- `scene_package.json`
- `provider_request.json`
- `run_summary.json`

## Provider submission usage

If you have a compatible provider endpoint that accepts the generated JSON payload:

```bash
export VIDEO_PROVIDER=generic-webhook
export VIDEO_API_URL="https://your-video-provider.example/api/generate"
export VIDEO_API_KEY="replace-with-your-token"
python generate_video_workflow.py
```

This writes the request package locally and stores the provider response as:

```text
output/video_generation_package/submission_response.json
```

## How to generate the final video

1. Review or edit `animal_travel_preparation_scene.json`.
2. Run `python generate_video_workflow.py --dry-run` to validate the package.
3. Point `VIDEO_PROVIDER=generic-webhook` to your compatible video-generation API.
4. Run `python generate_video_workflow.py` to submit the four-shot package.
5. Retrieve the final rendered video from your provider using the saved response metadata in `output/video_generation_package/submission_response.json`.

## Validation

Run the lightweight tests:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

These checks validate:

- exactly five required characters
- exactly four shots
- total duration of 15 seconds
- shot prompts include the shared consistency anchor

## Existing MoviePy renderer

The repository still includes the original local renderer:

```bash
python main.py
```

It renders to:

```text
output/animal_trip.mp4
```

## Security and secrets

- Do not commit `.env`, API keys, or generated video binaries.
- Generated output is ignored via `.gitignore`.
