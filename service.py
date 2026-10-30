"""
service.py

PriorScope 화면용 실행 함수 (설계서 2장, 6장)

- 실행마다 runs/<run_id>/ 폴더를 만들어 결과 5개를 저장한다 (동시 실행 시 섞이지 않음).
- 폴더 생성·보관 기간 정리·삭제는 run_storage.py가 맡는다 (멘토링 #2 기밀성).
- 단계가 실패하면 StepError로 즉시 멈춘다. 이전 결과로 대신 채우지 않는다.
- 임베딩 유사도(멘토링 10/27)는 보조 지표라, 실패해도 멈추지 않고 '유사도 없이 검증'한 사실을 결과에 남긴다.
"""

import hashlib
import json
from pathlib import Path

from config import FONT_PATH, validate_config
from upload import upload_file
from resume_agent import analyze_resume
from jd_agent import analyze_jd
from matching_agent import analyze_matching
from compare_builder import create_compare_input
from validator import validate
from ids import as_list
from similarity import UpstageEmbedder, compute_similarity
from run_storage import cleanup_old_runs, new_run_dir


class StepError(Exception):
    """어느 단계에서 왜 실패했는지 담는 오류."""

    def __init__(self, step: str, message: str):
        super().__init__(f"[{step}] {message}")
        self.step = step
        self.message = message


def _save_json(data, path: Path):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_step(step, on_step, func):
    on_step(step)
    try:
        result = func()
    except StepError:
        raise
    except Exception as exc:
        raise StepError(step, f"{type(exc).__name__}: {exc}") from exc
    return result


def _require_dict(step, result):
    if not isinstance(result, dict):
        raise StepError(step, "에이전트 결과가 JSON 객체가 아닙니다.")
    return result


def run_compare_service(my_pdf: bytes, prior_pdf: bytes, on_step=None) -> dict:
    """
    내 논문 PDF bytes, 기존 논문 PDF bytes → 결과 dict

    반환: run_dir, my_paper, prior_paper, compare_result, similarity, verified
    """

    on_step = on_step or (lambda name: None)

    # 입력 점검
    if hashlib.sha256(my_pdf).digest() == hashlib.sha256(prior_pdf).digest():
        raise StepError("입력 확인", "두 칸에 같은 파일이 올라갔습니다. 서로 다른 논문을 올려 주세요.")

    try:
        validate_config()
    except ValueError as exc:
        raise StepError("환경 설정", str(exc)) from exc

    # 보관 기간이 지난 다른 실행 폴더를 먼저 정리한다 (실패해도 분석은 계속).
    try:
        cleanup_old_runs()
    except Exception:  # noqa: BLE001
        pass

    run_dir = new_run_dir()
    my_path = run_dir / "My_Paper.pdf"
    prior_path = run_dir / "Prior_Paper.pdf"
    my_path.write_bytes(my_pdf)
    prior_path.write_bytes(prior_pdf)

    # 1. 내 논문
    step = "1단계 · 내 논문 분석"
    my_paper = _require_dict(step, _run_step(step, on_step, lambda: analyze_resume(upload_file(my_path))))
    _save_json(my_paper, run_dir / "my_paper.json")

    # 2. 기존 논문
    step = "2단계 · 기존 논문 분석"
    prior_paper = _require_dict(step, _run_step(step, on_step, lambda: analyze_jd(upload_file(prior_path))))
    _save_json(prior_paper, run_dir / "prior_paper.json")

    for name, paper in (("내 논문", my_paper), ("기존 논문", prior_paper)):
        if not as_list(paper.get("core_techniques")):
            raise StepError("입력 확인", f"{name}이(가) 논문으로 인식되지 않았습니다 (핵심 기술 요소 0개).")

    # 3. 비교용 PDF
    step = "3단계 · 비교용 PDF 생성"
    compare_pdf = run_dir / "Compare_Input.pdf"
    _run_step(step, on_step, lambda: create_compare_input(my_paper, prior_paper, compare_pdf, FONT_PATH))

    # 4. 비교 분석
    step = "4단계 · 비교 분석"
    compare_result = _require_dict(step, _run_step(step, on_step, lambda: analyze_matching(upload_file(compare_pdf))))
    _save_json(compare_result, run_dir / "compare_result.json")

    # 5. 임베딩 유사도 (보조 지표: 실패해도 계속)
    step = "5단계 · 임베딩 유사도"
    on_step(step)
    similarity, similarity_error = None, None
    try:
        # 캐시를 실행 폴더 안에 둬서, runs/ 삭제 정책 하나로 벡터까지 함께 지워지게 한다.
        embedder = UpstageEmbedder(cache_path=run_dir / "embedding_cache.json")
        similarity = compute_similarity(my_paper, prior_paper, embedder)
        _save_json(similarity, run_dir / "similarity.json")
    except Exception as exc:  # noqa: BLE001
        similarity_error = f"{type(exc).__name__}: {exc}"

    # 6. 검증
    step = "6단계 · 코드 검증"
    verified = _run_step(step, on_step, lambda: validate(my_paper, prior_paper, compare_result, similarity=similarity))
    if similarity_error:
        verified.setdefault("similarity", {})["error"] = similarity_error
    _save_json(verified, run_dir / "validated_result.json")

    on_step("완료")

    return {
        "run_dir": str(run_dir),
        "my_paper": my_paper,
        "prior_paper": prior_paper,
        "compare_result": compare_result,
        "similarity": similarity,
        "verified": verified,
    }
