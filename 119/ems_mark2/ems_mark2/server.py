"""mark2 MCP 서버 — Long-Context 파이프라인.

지침서 전문(절단)을 system 프롬프트로 주입한 뒤 CRAG → Reader → CoVe 를 수행한다.

execute_ems_pipeline(suspect, hospital_dept)
"""

import json

import uvicorn
from openai import OpenAI
from mcp.server.fastmcp import FastMCP

from . import config
from .data import DataManager
from .utils import safe_json_parse

mcp = FastMCP("ems-commander-mark2")

db_instance = None
client = None
expert_client = None
model_name = None
expert_model = None


def _init():
    global db_instance, client, expert_client, model_name, expert_model
    if db_instance is None:
        db_instance = DataManager()
        base, model_name = config.commander_endpoint()
        client = OpenAI(base_url=base, api_key=config.API_KEY)
        ebase, expert_model = config.expert_endpoint()
        expert_client = OpenAI(base_url=ebase, api_key=config.API_KEY)


@mcp.tool()
def execute_ems_pipeline(suspect: str, hospital_dept: str) -> str:
    """Args:
        suspect: 의심 질환명
        hospital_dept: 이송 진료과
    """
    try:
        _init()
    except Exception as e:
        return json.dumps({"error": f"초기화 실패: {e}"}, ensure_ascii=False)

    full_text = db_instance.get_full_text()[:config.MAX_CONTEXT_CHARS]
    if not full_text:
        return json.dumps({"error": "지침서가 로드되지 않았습니다. GUIDELINE_PATH 확인."}, ensure_ascii=False)

    hospitals = db_instance.find_hospitals(hospital_dept)
    h_info = "\n".join([f"- {h['name']} ({h['dist_km']}km): {h.get('status','')}" for h in hospitals]) or "추천 병원 없음"

    base_system_prompt = f"""당신은 대한민국 119 구급대원 현장 처치 보조 AI입니다.
아래 [현장응급처치 표준지침(발췌)]에 근거해서만 답변하세요.

[현장응급처치 표준지침(발췌)]
{full_text}
"""
    print(f"\n[Tool] 파이프라인 시작 (Context: {len(full_text)} chars, suspect={suspect})")

    # 1. CRAG — 전문 내에 관련 알고리즘이 있는지 판단
    print("   └─ [1.CRAG] 관련성 평가 중...")
    crag_prompt = f"""환자 증상: "{suspect}"
위 지침(발췌) 안에 이 증상과 관련된 처치 내용이 있는지 JSON으로 판단하세요.
format: {{ "is_relevant": true/false, "reason": "..." }}"""
    try:
        res = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": base_system_prompt},
                      {"role": "user", "content": crag_prompt}],
            temperature=0.0, max_tokens=200,
        )
        crag = safe_json_parse(res.choices[0].message.content)
        if not crag.get("is_relevant"):
            return json.dumps({
                "suspect": suspect,
                "draft_report": f"⚠️ 관련 지침 없음: {crag.get('reason')}",
                "validation_result": "N/A",
            }, ensure_ascii=False)
    except Exception as e:
        print(f"   ⚠️ CRAG 오류 (계속 진행): {e}")

    # 2. Reader — 보고서 작성
    print("   └─ [2.Reader] 보고서 작성 중...")
    gen_prompt = f"""[상황] {suspect} / 이송과: {hospital_dept}
[병원] {h_info}

지침에 근거하여 [환자평가], [응급처치(약물 용량 필수)], [병원이송], [주의사항]을
개조식 보고서로 작성하세요."""
    try:
        draft = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": base_system_prompt},
                      {"role": "user", "content": gen_prompt}],
            temperature=0.0, max_tokens=700,
        ).choices[0].message.content.strip()
    except Exception as e:
        return json.dumps({"error": f"보고서 생성 실패: {e}"}, ensure_ascii=False)
    print("       └─ [3.작성] 초안 완료")

    # 3. CoVe — 의학적 검증
    print("   └─ [4.Expert] 의학적 검증 중...")
    cove_prompt = f"""당신은 응급의학 전문의입니다. 아래 보고서에 의학적 오류(약물 용량, 금기증 등)가 있는지 검증하세요.
오류가 없으면 "[승인] 의학적 오류 없음", 있으면 "[경고] 오류내용"을 출력하세요.

[보고서]
{draft}"""
    try:
        validation = expert_client.chat.completions.create(
            model=expert_model,
            messages=[{"role": "system", "content": base_system_prompt},
                      {"role": "user", "content": cove_prompt}],
            temperature=0.0, max_tokens=500,
        ).choices[0].message.content.strip()
    except Exception:
        validation = "검증 실패"
    print("       └─ [4.검증] 완료")

    return json.dumps({
        "suspect": suspect,
        "draft_report": draft,
        "validation_result": validation,
        "meta": {"context_chars": len(full_text), "hospitals": [h["name"] for h in hospitals]},
    }, ensure_ascii=False)


def main():
    print(f"🚀 EMS Commander(mark2) MCP 서버 시작 (http://{config.MCP_HOST}:{config.MCP_PORT})")
    uvicorn.run(mcp.sse_app(), host=config.MCP_HOST, port=config.MCP_PORT)


if __name__ == "__main__":
    main()
