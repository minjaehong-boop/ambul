"""AI EMS Commander — mark2 (Long-Context) 배포판.

지침서 전문을 system 프롬프트에 주입하고 CRAG→Reader→CoVe 를 수행한다.
전문이 매우 길어 컨텍스트를 초과하므로 MAX_CONTEXT_CHARS 로 절단한다(README 참고).
"""

__version__ = "0.1.0"
