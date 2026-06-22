"""mark1 파이프라인 LLM 에이전트 — CRAG / Reader / Expert."""

from openai import OpenAI

from . import config


class RetrievalEvaluator:
    """CRAG — 임베딩 검색된 문서가 질의와 관련 있는지 yes/no 필터."""

    def __init__(self):
        base_url, self.model = config.evaluator_endpoint()
        self.client = OpenAI(base_url=base_url, api_key=config.API_KEY)

    def evaluate_relevance(self, query, docs):
        valid_docs = []
        print(f"[CRAG] 검색된 문서 {len(docs)}건 평가 중...")
        for doc in docs:
            prompt = f"""
            당신은 문서 평가자입니다. 아래 문서가 사용자의 질문에 답하는 데 유용한지 판단하세요.

            [질문] {query}
            [문서 내용] {doc['content'][:]}...

            유용하다면 "yes", 아니라면 "no"라고만 답하세요.
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
                    print(f"      🗑️ 문서 기각: {doc.get('page')}페이지 (관련 없음)")
            except Exception:
                valid_docs.append(doc)
        print(f"   ✅ [CRAG] 평가 완료: {len(docs)}건 -> {len(valid_docs)}건 유효")
        return valid_docs


class ReaderAgent:
    """검색·검증된 지침으로 현장 처치 보고서를 작성."""

    def __init__(self):
        base_url, self.model = config.reader_endpoint()
        self.client = OpenAI(base_url=base_url, api_key=config.API_KEY)

    def synthesize_report(self, suspect, protocols, hospitals):
        if not protocols:
            return "[시스템 경고] 관련 지침을 찾을 수 없습니다. AI 판단을 유보하고 의료지도 의사에게 직접 문의하십시오."

        context = "### [지침 발췌]\n" + "\n".join(
            [f"- (Page {p['page']}) {p['content'][:]}" for p in protocols]
        )
        if hospitals:
            context += "\n### [병원 현황]\n" + "\n".join(
                [f"- {h['name']} ({h['dist_km']}km): {h['status']}" for h in hospitals]
            )
        else:
            context += "\n### [병원 현황]\n- 조건에 맞는 병원 없음"

        prompt = f"""
        [상황] 환자는 '{suspect}' 의심 상태입니다.
        [지시]에 따라 아래 [자료]에서 발췌하여 보고서를 작성하세요.
        자료에 없는 내용은 절대로 지어내지 마십시오.

        [자료]
        {context}

        [지시]
        1. 자료에 근거하여 '핵심 처치' 및 '금기사항'을 요약하세요.
        2. 자료에 근거하여 최적의 병원 2곳을 추천하고 이유를 말하세요.
        3. 반드시 한국어로 작성하세요.
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
    """CoVe — 보고서의 의학적 정합성을 원본 지침과 대조 검증."""

    def __init__(self):
        base_url, self.model = config.expert_endpoint()
        self.client = OpenAI(base_url=base_url, api_key=config.API_KEY)

    def validate_with_cove(self, draft_report, suspect, original_protocols):
        if "관련 지침을 찾을 수 없습니다" in draft_report:
            return "⚠️ [확인] 근거 문서 부족으로 AI가 판단을 보류했습니다."

        print("   🛡️ [CoVe] 검증 체인 실행 중...")
        evidence_text = "\n".join([p["content"][:1000] for p in original_protocols])[:2500]
        cove_prompt = f"""
        You are a Medical Safety Auditor.

        [Patient Suspect]: {suspect}
        [AI Draft Report]:
        {draft_report}

        [Trusted Evidence Protocols]:
        {evidence_text}

        [Task]
        1. Identify specific medical claims in the Draft Report (e.g., drug dosage, contraindications).
        2. Verify if these claims are supported by the [Trusted Evidence Protocols].
        3. Check for any contradictions or hallucinations.

        If Safe: output "[승인] 의학적 오류 없음".
        If Unsafe/Hallucination: output "[경고] (Specific Reason based on Evidence)".
        Answer in Korean.
        """
        try:
            res = self.client.chat.completions.create(
                model=self.model, messages=[{"role": "user", "content": cove_prompt}],
                temperature=0.0, max_tokens=500,
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            return f"검수 실패: {e}"
