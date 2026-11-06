"""
bench_pages.py

PDF 페이지 수에 따라 My Paper Agent(1단계 Parse → Extract)가 얼마나 버티고 얼마나 걸리는지 잰다.
긴 PDF(서베이 논문, 학위논문 등) 하나를 앞에서부터 N쪽으로 잘라 1단계만 실행한다.
3·4단계 입력은 추출 결과로 만든 짧은 PDF라 페이지 수 영향은 1·2단계에 몰린다.

사용법
    python bench_pages.py long_paper.pdf --pages 5 10 15 20 30 40 60 --repeat 2 --max-wait 900

결과
    eval/bench/pages_<시각>.csv : pages, repeat, ok, upload_s, job_s, total_s, n_core, n_results, error
    → 화면 안내 기준(PAGE_WARN / PAGE_MAX)과 AGENT_MAX_WAIT 를 이 표로 정한다.
    1단계만 재므로 전체 소요 시간은 대략 (1단계 × 2) + 적합성 + Compare Agent(3회 동시)다.

볼 것
    - 몇 쪽부터 실패하거나 시간이 급격히 늘어나는지
    - n_core가 쪽수에 따라 이상하게 줄거나 늘지 않는지 (요소가 한 문자열로 뭉치는지)
    - n_results가 0이 되는지 (실험 표가 뒤쪽에 있는데 잘려서 안 읽히는지)
    호출마다 크레딧이 든다. 처음엔 --repeat 1로 큰 간격을 보고, 경계 근처만 촘촘히 다시 잰다.
"""

import argparse
import csv
import time
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from agent_client import AgentClient
from config import RESUME_AGENT_ID, RESUME_CONFIG_ID
from ids import as_list
from upload import upload_file

OUT_DIR = Path(__file__).resolve().parent / "eval" / "bench"


def slice_pdf(src, pages, out_path):
    reader = PdfReader(str(src))
    writer = PdfWriter()
    for page in reader.pages[:pages]:
        writer.add_page(page)
    with open(out_path, "wb") as f:
        writer.write(f)
    return out_path


def run_once(pdf_path, max_wait):
    row = {"ok": False, "upload_s": None, "job_s": None, "total_s": None, "n_core": None, "n_results": None, "error": ""}
    client = AgentClient(RESUME_AGENT_ID, RESUME_CONFIG_ID)
    t0 = time.time()
    try:
        file_id = upload_file(pdf_path)
        t1 = time.time()
        row["upload_s"] = round(t1 - t0, 1)
        response = client.wait_until_complete(client.create_job(file_id), max_wait=max_wait)
        result = client.parse_result(response)
        row["job_s"] = round(time.time() - t1, 1)
        row["n_core"] = len(as_list(result.get("core_techniques")))
        row["n_results"] = len(as_list(result.get("experiment_results")))
        row["ok"] = True
    except Exception as e:
        row["error"] = f"{type(e).__name__}: {e}"[:300]
    row["total_s"] = round(time.time() - t0, 1)
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf")
    parser.add_argument("--pages", type=int, nargs="+", default=[5, 10, 20, 30, 40])
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--max-wait", type=int, default=900, help="실제 소요 시간을 보려고 180초보다 길게 잡는다")
    args = parser.parse_args()

    total = len(PdfReader(args.pdf).pages)
    OUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_csv = OUT_DIR / f"pages_{stamp}.csv"
    fields = ["pages", "repeat", "ok", "upload_s", "job_s", "total_s", "n_core", "n_results", "error"]

    print(f"원본 {total}쪽, 측정 {args.pages}, 반복 {args.repeat}")
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for n in args.pages:
            if n > total:
                print(f"{n}쪽: 원본보다 길어 건너뜀")
                continue
            sliced = slice_pdf(args.pdf, n, OUT_DIR / f"slice_{n}p.pdf")
            for r in range(1, args.repeat + 1):
                row = {"pages": n, "repeat": r, **run_once(sliced, args.max_wait)}
                writer.writerow(row)
                f.flush()
                status = "OK " if row["ok"] else "FAIL"
                print(f"{n:>3}쪽 #{r} {status} {row['total_s']:>6}s  core={row['n_core']} results={row['n_results']} {row['error']}")

    print(f"\n저장: {out_csv}")


if __name__ == "__main__":
    main()
