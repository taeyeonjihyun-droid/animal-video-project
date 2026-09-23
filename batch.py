from __future__ import annotations

import argparse

import main


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Animal video batch renderer")
    parser.add_argument(
        "--batch-config",
        type=str,
        default=None,
        help="배치 설정 JSON 경로 (기본: batch.json / batch_config.json)",
    )
    parser.add_argument(
        "--retry-failed",
        type=int,
        default=0,
        help="실패한 배치 작업별 재시도 횟수 (기본: 0)",
    )
    parser.add_argument(
        "--summary-report",
        type=str,
        default=None,
        help="배치 실행 요약(JSON) 저장 경로",
    )
    args = parser.parse_args()
    if args.retry_failed < 0:
        parser.error("--retry-failed는 0 이상의 정수여야 합니다.")
    return args


if __name__ == "__main__":
    args = parse_args()
    main.build_batch_videos(
        args.batch_config,
        retry_failed=args.retry_failed,
        summary_report_path=args.summary_report,
    )
