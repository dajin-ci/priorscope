"""
PriorScope

app.py

전체 Workflow를 관리하는 Orchestrator

Step 1. 내 논문   -> My Paper Agent    -> my_paper.json
Step 2. 기존 논문 -> Prior Paper Agent -> prior_paper.json
Step 3. compare_builder -> Compare_Input.pdf
Step 4. Compare Agent   -> compare_result.json
Step 5. similarity      -> similarity.json (임베딩 유사도, 실패해도 계속)
Step 6. validator       -> validated_result.json

변수 이름(RESUME_*, JD_*, MATCHING_*)은 스타터 그대로 쓰고,
config.py와 .env의 값만 PriorScope용으로 바꿨다.
"""

import json

from config import (

    validate_config,
    print_config,

    RESUME_FILE,
    JD_FILE,

    RESUME_JSON,
    JD_JSON,

    MATCHING_PDF,
    MATCHING_RESULT,
    VALIDATED_RESULT,

    FONT_PATH
)

from upload import upload_file

from resume_agent import (
    analyze_resume
)

from jd_agent import (
    analyze_jd
)


##################################################
# Lab 3
##################################################

from compare_builder import (
    create_compare_input,
    load_json
)

##################################################
# Lab 4
##################################################

from matching_agent import (
    analyze_matching
)

from file_manager import (
    save_json
)

##################################################
# Lab 5 (PriorScope)
##################################################

from validator import (
    validate
)

##################################################
# 임베딩 유사도 (멘토링 10/27)
##################################################

from similarity import (
    UpstageEmbedder,
    compute_similarity,
    DEFAULT_OUT as SIMILARITY_RESULT
)

##################################################
# Common Document Process
##################################################

def process_document(

    step,
    document_name,

    input_file,

    analyzer,

    output_json

):

    print()

    print("=" * 60)
    print(step)
    print("=" * 60)

    ##################################################
    # Upload
    ##################################################

    try:

        file_id = upload_file(
            input_file
        )

        print()

        print(f"{document_name} Upload Complete")

    except Exception as e:

        print()

        print("=" * 60)
        print("ERROR")
        print("=" * 60)
        print(e)

        return None

    ##################################################
    # Agent
    ##################################################

    try:

        result = analyzer(
            file_id
        )

        save_json(

            result,

            output_json

        )

        print()

        print(f"{document_name} JSON 저장 완료")

        print(output_json)

        return result

    except Exception as e:

        print()

        print("=" * 60)
        print("ERROR")
        print("=" * 60)
        print(e)

        return None



##################################################
# Matching Builder
##################################################

def build_matching_pdf():

    print()

    print("=" * 60)

    print("Step 3. Compare Builder")

    print("=" * 60)

    try:

        my_paper = load_json(RESUME_JSON)

        prior_paper = load_json(JD_JSON)

        ids = create_compare_input(

            my_paper,

            prior_paper,

            MATCHING_PDF,

            FONT_PATH

        )

        pdf_path = MATCHING_PDF

        print()

        print("Compare_Input.pdf 생성 완료")

        print(f"M {len(ids['M'])}개, P {len(ids['P'])}개")

        print(pdf_path)

        return pdf_path

    except Exception as e:

        print()

        print("=" * 60)

        print("ERROR")

        print("=" * 60)

        print(e)

        return None

##################################################
# Matching Analysis
##################################################

def process_matching(
    matching_pdf
):

    print()

    print("=" * 60)

    print("Step 4. Compare Analysis")

    print("=" * 60)

    try:

        ##################################################
        # Upload
        ##################################################

        file_id = upload_file(
            matching_pdf
        )

        ##################################################
        # Agent
        ##################################################

        result = analyze_matching(
            file_id
        )

        ##################################################
        # Save
        ##################################################

        save_json(

            result,

            MATCHING_RESULT

        )

        print()

        print("Compare Result 저장 완료")

        print(MATCHING_RESULT)

        return result

    except Exception as e:

        print()

        print("=" * 60)

        print("ERROR")

        print("=" * 60)

        print(e)

        return None


##################################################
# Similarity (보조 지표)
##################################################

def process_similarity():

    print()

    print("=" * 60)

    print("Step 5. Embedding Similarity")

    print("=" * 60)

    try:

        result = compute_similarity(

            load_json(RESUME_JSON),

            load_json(JD_JSON),

            UpstageEmbedder()

        )

        save_json(result, SIMILARITY_RESULT)

        print()

        print(f"Similarity 저장 완료 (M {len(result['m_ids'])} × P {len(result['p_ids'])})")

        print(SIMILARITY_RESULT)

        return result

    except Exception as e:

        # 보조 지표라 멈추지 않는다. 예전 실행의 파일이 남아 섞이지 않도록 지운다.
        if SIMILARITY_RESULT.exists():
            SIMILARITY_RESULT.unlink()

        print()

        print("유사도 계산 실패 → 유사도 없이 검증을 계속합니다.")

        print(e)

        return None


##################################################
# Validation (PriorScope)
##################################################

def process_validation(similarity=None):

    print()

    print("=" * 60)

    print("Step 6. Validation")

    print("=" * 60)

    try:

        validated = validate(

            load_json(RESUME_JSON),

            load_json(JD_JSON),

            load_json(MATCHING_RESULT),

            similarity=similarity

        )

        with open(VALIDATED_RESULT, "w", encoding="utf-8") as f:

            json.dump(validated, f, ensure_ascii=False, indent=2)

        print()

        print("Validated Result 저장 완료")

        print(VALIDATED_RESULT)

        return validated

    except Exception as e:

        print()

        print("=" * 60)

        print("ERROR")

        print("=" * 60)

        print(e)

        return None


##################################################
# Result
##################################################

def print_result():

    print()

    print("=" * 60)

    print("Project Complete")

    print("=" * 60)

    print()

    print("Generated Files")

    print("-" * 60)

    print(RESUME_JSON)

    print(JD_JSON)

    print(MATCHING_PDF)

    print(MATCHING_RESULT)

    print(SIMILARITY_RESULT)

    print(VALIDATED_RESULT)

    print("-" * 60)


##################################################
# Main
##################################################

def main():

    print()

    print("=" * 60)

    print("PriorScope")

    print("=" * 60)

    ##################################################
    # Config
    ##################################################

    validate_config()

    print_config()

    ##################################################
    # My Paper Analysis
    ##################################################

    resume = process_document(

        step="Step 1. My Paper Analysis",

        document_name="My Paper",

        input_file=RESUME_FILE,

        analyzer=analyze_resume,

        output_json=RESUME_JSON

    )

    if resume is None:

        return

    ##################################################
    # Prior Paper Analysis
    ##################################################

    jd = process_document(

        step="Step 2. Prior Paper Analysis",

        document_name="Prior Paper",

        input_file=JD_FILE,

        analyzer=analyze_jd,

        output_json=JD_JSON

    )

    if jd is None:

        return

    ##################################################
    # Matching Builder
    ##################################################

    matching_pdf = build_matching_pdf()

    if matching_pdf is None:

        return

    ##################################################
    # Matching Analysis
    ##################################################

    matching_result = process_matching(

        matching_pdf

    )

    if matching_result is None:

        return

    ##################################################
    # Similarity
    ##################################################

    similarity = process_similarity()

    ##################################################
    # Validation
    ##################################################

    validated = process_validation(similarity)

    if validated is None:

        return

    ##################################################
    # Result
    ##################################################

    print_result()

##################################################

if __name__ == "__main__":

    main()