"""파이프라인 LLM 에이전트 4종.

ProtocolSelector  : 의심질환 → 지침 키워드 선정
RetrievalEvaluator: CRAG, 로드된 지침이 질환과 관련 있는지 yes/no 필터
ReaderAgent       : 지침 근거 현장 처치 보고서 작성
ExpertAgent       : CoVe, 보고서의 의학적 정합성 검증
"""

from openai import OpenAI

from . import config
from .utils import safe_json_parse


class ProtocolSelector:
    def __init__(self):
        base_url, self.model = config.selector_endpoint()
        self.client = OpenAI(base_url=base_url, api_key=config.API_KEY)

    def select_targets(self, protocol_desc, suspect_hint=None):
        suspect = suspect_hint or "의심 질환 미상"
        system_prompt = f"""
당신은 119 구급대 현장 지휘관 AI입니다.
현재 환자의 질환은 {suspect}입니다.
아래 제공된 [보유 지침 목록] 중에서 {suspect}에 가장 적합한 '지침 키워드'를 선택해야 합니다.

[보유 지침 목록 (키워드 나열)]
{protocol_desc}

[중요 규칙]
1. 반드시 위 목록에 **실제로 존재하는 단어**만 'target_files'에 담아야 합니다.
2. 없는 단어를 지어내거나 영어를 사용하지 마십시오. (예: 'Cardiac Arrest' (X) -> '심정지' (O))
3. 여러 개가 관련되면 리스트에 모두 담으세요.

[임무]
1. 제공된 ktas_suspect를 suspect로 사용하세요.
2. suspect와 연관된 지침 키워드를 위 목록에서 찾아 'target_files'에 담으세요.
3. 만약 연관된 지침이 없다면 'target_files'를 빈 리스트로 반환하세요.

[출력 형식 (JSON Only)]
{{
    "suspect": "의심 질환명",
    "target_files": ["키워드1", "키워드2", "키워드3"]
}}
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"ktas_suspect={suspect}"},
        ]
        res = self.client.chat.completions.create(model=self.model, messages=messages, temperature=0.0)
        content = res.choices[0].message.content.strip()
        try:
            return safe_json_parse(content)
        except Exception:
            # JSON 외 잡설이 섞이면 1회 재시도
            retry_messages = messages + [
                {"role": "assistant", "content": content},
                {"role": "user", "content": "JSON만 다시 출력하세요. 다른 문장은 포함하지 마세요."},
            ]
            retry_res = self.client.chat.completions.create(
                model=self.model, messages=retry_messages, temperature=0.0
            )
            return safe_json_parse(retry_res.choices[0].message.content.strip())


class RetrievalEvaluator:
    def __init__(self):
        base_url, self.model = config.evaluator_endpoint()
        self.client = OpenAI(base_url=base_url, api_key=config.API_KEY)

    def evaluate_relevance(self, suspect, docs):
        valid_docs = []
        print(f"[CRAG] 선택된 지침 {len(docs)}건 적합성 평가 중...")
        for doc in docs:
            prompt = f"""
당신은 문서 평가자입니다.
현재 환자의 질환은 '{suspect}'입니다.
아래 문서가 현재 환자와 관련이 있는지 판단하세요.

[문서 제목] {doc['source']}
[문서 내용 일부] {doc['content'][:100]}...

관련이 있다면 "yes", 전혀 엉뚱하다면 "no"라고만 답하세요.
"""
            try:
                res = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                )
                judgment = res.choices[0].message.content.strip().lower()
                if "yes" in judgment:
                    valid_docs.append(doc)
                else:
                    print(f"      🗑️ 문서 기각: {doc['source']} (주제 불일치)")
            except Exception:
                valid_docs.append(doc)  # 평가 실패 시 안전하게 포함
        print(f"   ✅ [CRAG] 평가 완료: {len(valid_docs)}건 유효")
        return valid_docs


class ReaderAgent:
    def __init__(self):
        base_url, self.model = config.reader_endpoint()
        self.client = OpenAI(base_url=base_url, api_key=config.API_KEY)

    def synthesize_report(self, suspect, protocols):
        if not protocols:
            return "[시스템 경고] 선택된 지침 파일이 없거나 CRAG 평가에서 기각되었습니다."

        context = "### [선택된 표준 지침]\n" + "\n".join(
            [f"- (파일: {p['source']})\n{p['content']}" for p in protocols]
        )
        prompt = f"""
[상황] 환자는 '{suspect}' 상태입니다.
{suspect}와 [참고 자료]를 바탕으로 구급 대원에게 조언하세요.

[참고 자료]
{context}

[작성 양식]
1. **현장 처치**: 핵심 처치 순서 및 약물 투여 지침 (반드시 지침에 근거할 것)
2. **주의/금기**: 절대 하면 안 되는 행동
"""
        try:
            res = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            return f"보고서 생성 실패: {e}"


class ExpertAgent:
    def __init__(self):
        base_url, self.model = config.expert_endpoint()
        self.client = OpenAI(base_url=base_url, api_key=config.API_KEY)

    def validate_with_cove(self, draft_report, suspect, original_protocols):
        if "선택된 지침 파일이" in draft_report:
            return "⚠️ [검증 불가] 참조된 지침이 없습니다."

        print("   🛡️ [CoVe] 의학적 정합성 검증 중...")
        evidence_text = "\n".join([p["content"] for p in original_protocols])
        cove_prompt = f"""
You are a Medical Safety Auditor.
[Suspect]: {suspect}
[Draft]: {draft_report}
[Evidence Protocol]: {evidence_text}

Verify specific claims in Draft against Evidence.
If Safe: output "[승인] 의학적 오류 없음".
If Unsafe: output "[경고] (Specific Reason)".
Answer in Korean.
"""
        try:
            res = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": cove_prompt}],
                temperature=0.0,
            )
            return res.choices[0].message.content.strip()
        except Exception:
            return "검증 실패"
