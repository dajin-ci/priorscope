"""CLI와 Streamlit이 같은 적합성 분기와 실행별 저장 정책을 사용한다.

실행: python app.py
결과: runs/<run_id>/ (표시된 경로를 check_run.py --run-dir에 전달)
"""
from config import RESUME_FILE, JD_FILE
from service import StepError, run_compare_service


def main():
    try:
        bundle = run_compare_service(RESUME_FILE.read_bytes(), JD_FILE.read_bytes(), on_step=print)
    except (OSError, StepError) as exc:
        print(f"분석 실패: {exc}")
        return 1
    print(bundle["report"]["title"])
    print(bundle["report"]["summary"])
    print(f"결과 폴더: {bundle['run_dir']}")
    print("최종 레포트: report.json · 적합성 판단: suitability.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
