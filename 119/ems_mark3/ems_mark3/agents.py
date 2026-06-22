"""mark3 파이프라인 LLM 에이전트 — CRAG / Reader / Expert."""

from openai import OpenAI

from . import config


class RetrievalEvaluator:
    """CRAG — 지휘관이 고른 파일이 의심질환과 실제 관련 있는지 yes/no 필터."""

    def __init__(self):
        base_url, self.model = config.evaluator_endpoint()
        self.client = OpenAI(base_url=base_url, api_key=config.API_KEY)

    def evaluate_relevance(self, suspect, docs):
        valid_docs = []
        print(f"[CRAG] 선택된 지침 {len(docs)}건 적합성 평가 중...")
        for doc in docs:
            prompt = f"""
            당신은 문서 평가자입니다.
            현재 환자의 의심 질환은 '{suspect}'입니다.
            아래 문서가 이 질환의 처치법을 다루고 있는지 판단하세요.

            [문서 제목] {doc['source']}
            [문서 내용 일부] {doc['content'][:]}...

            관련이 밀접하게 있다면 "yes", 관련이 없다면 "no"라고만 답하세요.
            """
            try:
                res = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0, max_tokens=10,
                )
                if "yes" in res.choices[0].message.content.strip().lower():
                    valid_docs.append(doc)
                else:
                    print(f"      🗑️ 문서 기각: {doc['source']} (주제 불일치)")
            except Exception:
                valid_docs.append(doc)
        print(f"   ✅ [CRAG] 평가 완료: {len(valid_docs)}건 유효")
        return valid_docs


class ReaderAgent:
    def __init__(self):
        base_url, self.model = config.reader_endpoint()
        self.client = OpenAI(base_url=base_url, api_key=config.API_KEY)

    def synthesize_report(self, suspect, protocols, hospitals):
        if not protocols:
            return "[시스템 경고] 선택된 지침 파일이 없거나 CRAG 평가에서 기각되었습니다. 수동으로 프로토콜을 확인하십시오."

        context = "### [선택된 표준 지침]\n" + "\n".join(
            [f"- (파일: {p['source']})\n{p['content'][:]}" for p in protocols]
        )
        context += "\n### [이송 가능 병원]\n" + "\n".join(
            [f"- {h['name']} ({h['dist_km']}km): {h['status']}" for h in hospitals]
        )
        prompt = f"""
        [상황] 환자는 '{suspect}' 의심 상태입니다.
        [지침]을 바탕으로 구급활동 보고서를 작성하세요.

        [참고 자료]
        {context}

        [작성 양식]
        1. **현장 처치**: 핵심 처치 순서 및 약물 투여 지침
        2. **주의/금기**: 절대 하면 안 되는 행동
        3. **병원 추천**: 위 목록 중 최적의 병원 2곳
        """
        try:
            res = self.client.chat.completions.create(
                model=self.model, messages=[{"role": "user", "content": prompt}],
                temperature=0.0, max_tokens=700,
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
        evidence_text = "\n".join([p["content"][:1000] for p in original_protocols])[:2500]
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
                model=self.model, messages=[{"role": "user", "content": cove_prompt}],
                temperature=0.0, max_tokens=500,
            )
            return res.choices[0].message.content.strip()
        except Exception:
            return "검증 실패"
