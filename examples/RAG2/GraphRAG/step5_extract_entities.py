from neo4j_graphrag.experimental.components.entity_relation_extractor import LLMEntityRelationExtractor, OnError
from neo4j_graphrag.experimental.components.neo4j_reader import Neo4jChunkReader
from neo4j_graphrag.experimental.components.kg_writer import Neo4jWriter
from neo4j_graphrag.experimental.components.types import LexicalGraphConfig
from neo4j_graphrag.experimental.components.schema import GraphSchema, NodeType, RelationshipType, Pattern
from neo4j_graphrag.llm.openai_llm import OpenAILLM
from neo4j import GraphDatabase
import asyncio
from pathlib import Path

BASE_DIR = Path(__file__).parent
OPENROUTER_KEY = BASE_DIR.joinpath("openrouter_key.txt").read_text(encoding="utf-8").strip()

URI = "neo4j://localhost:7687"
AUTH = ("neo4j", "galaxy2816*")
DATABASE = "neo4j"

driver = GraphDatabase.driver(URI, auth=AUTH)

llm = OpenAILLM(
    model_name="openai/gpt-4o-mini",
    api_key=OPENROUTER_KEY,
    base_url="https://openrouter.ai/api/v1",
    model_params={"temperature": 0, "response_format": {"type": "json_object"}},
)

reader = Neo4jChunkReader(driver=driver, neo4j_database=DATABASE, fetch_embeddings=True)
extractor = LLMEntityRelationExtractor(
    llm=llm,
    on_error=OnError.IGNORE,
    max_concurrency=2,
    create_lexical_graph=False,
)
writer = Neo4jWriter(driver=driver, neo4j_database=DATABASE)

lexical_graph_config = LexicalGraphConfig()

schema = GraphSchema(
    node_types=(
        NodeType(label="NACRSItem", description="NACRS 코드로 분류되는 응급환자 분류 항목 (예: NACRS 007 전신 쇠약)"),
        NodeType(label="Symptom", description="환자가 호소하는 증상 또는 임상 소견 (예: 호흡곤란, 의식변화, 탈수)"),
        NodeType(label="VitalSign", description="활력징후 관련 분류 (예: 쇼크, 혈역학적 장애, 정상 활력징후)"),
        NodeType(label="Category", description="증상 대분류 (예: 신경계, 호흡기계, 심혈관계)"),
        NodeType(label="Subcategory", description="대분류 하위 세부 항목 (예: 뇌졸중 증상, 발열, 두통)"),
        NodeType(label="TriageLevel", description="KTAS 등급 (1~5)"),
        NodeType(label="SuspectedCondition", description="감별진단 또는 의심해야 할 임상 상태 (예: 뇌졸중 의심, 패혈증 의증)"),
        NodeType(label="AgeGroup", description="환자 연령군 (예: 성인, 소아, 15세 이상, 15세 미만)"),
    ),
    relationship_types=(
        RelationshipType(label="HAS_SYMPTOM", description="NACRSItem이 포함하는 증상/소견"),
        RelationshipType(label="ASSIGNED_TRIAGE", description="증상/소견에 부여되는 KTAS 등급"),
        RelationshipType(label="BELONGS_TO_CATEGORY", description="NACRSItem이 속한 대분류"),
        RelationshipType(label="HAS_SUBCATEGORY", description="대분류와 하위 세부항목의 포함 관계"),
        RelationshipType(
            label="REFER_TO",
            description="문서 본문에서 '~을 의심하면 ~으로 이동/참조하라'고 명시한 cross-reference. 다른 NACRSItem/Subcategory로의 이동 안내가 핵심.",
        ),
        RelationshipType(
            label="RED_FLAG_FOR",
            description="해당 증상이 특정 위험 진단(SuspectedCondition)을 시사함을 나타내는 임상적 경고 관계.",
        ),
        RelationshipType(label="APPLIES_TO_AGE", description="NACRSItem이나 분류가 적용되는 연령군"),
    ),
    patterns=(
        Pattern(source="NACRSItem", relationship="HAS_SYMPTOM", target="Symptom"),
        Pattern(source="NACRSItem", relationship="HAS_SYMPTOM", target="VitalSign"),
        Pattern(source="Symptom", relationship="ASSIGNED_TRIAGE", target="TriageLevel"),
        Pattern(source="VitalSign", relationship="ASSIGNED_TRIAGE", target="TriageLevel"),
        Pattern(source="NACRSItem", relationship="BELONGS_TO_CATEGORY", target="Category"),
        Pattern(source="Category", relationship="HAS_SUBCATEGORY", target="Subcategory"),
        Pattern(source="NACRSItem", relationship="REFER_TO", target="NACRSItem"),
        Pattern(source="NACRSItem", relationship="REFER_TO", target="Subcategory"),
        Pattern(source="Subcategory", relationship="REFER_TO", target="Subcategory"),
        Pattern(source="Symptom", relationship="RED_FLAG_FOR", target="SuspectedCondition"),
        Pattern(source="NACRSItem", relationship="APPLIES_TO_AGE", target="AgeGroup"),
    ),
    additional_node_types=True,
    additional_relationship_types=True,
    additional_patterns=True,
)

EXAMPLES = """
예시 1) 본문: "NACRS 007 전신 쇠약. 만약 뇌졸중을 의심해야 하면 '신경계 - 뇌졸중 증상'으로 이동."
→ 노드: NACRSItem("NACRS 007 전신 쇠약"), SuspectedCondition("뇌졸중 의심"), Subcategory("신경계 - 뇌졸중 증상")
→ 관계: (NACRS 007 전신 쇠약)-[:REFER_TO {condition:"뇌졸중 의심"}]->(신경계 - 뇌졸중 증상)
        (전신 쇠약)-[:RED_FLAG_FOR]->(뇌졸중 의심)

예시 2) 본문: "활력징후 1차 고려사항: 쇼크 → KTAS 1, 혈역학적 장애 → KTAS 2"
→ 노드: VitalSign("쇼크"), VitalSign("혈역학적 장애"), TriageLevel("KTAS 1"), TriageLevel("KTAS 2")
→ 관계: (쇼크)-[:ASSIGNED_TRIAGE]->(KTAS 1), (혈역학적 장애)-[:ASSIGNED_TRIAGE]->(KTAS 2)

중요한 규칙:
- 본문에 "만약 ... 의심", "... 으로 이동", "... 참조" 같은 표현이 있으면 반드시 REFER_TO 관계를 만들 것.
- 모든 노드는 반드시 비어있지 않은 label과 name을 가져야 함.
"""


async def main():
    chunks = await reader.run()
    graph = await extractor.run(
        chunks=chunks,
        lexical_graph_config=lexical_graph_config,
        schema=schema,
        examples=EXAMPLES,
    )

    valid_nodes = [n for n in graph.nodes if n.label and n.label.strip()]
    valid_node_ids = {n.id for n in valid_nodes}
    valid_rels = [
        r for r in graph.relationships
        if r.type and r.type.strip()
        and r.start_node_id in valid_node_ids
        and r.end_node_id in valid_node_ids
    ]
    dropped_nodes = len(graph.nodes) - len(valid_nodes)
    dropped_rels = len(graph.relationships) - len(valid_rels)
    graph.nodes = valid_nodes
    graph.relationships = valid_rels
    print(f"Filtered out {dropped_nodes} invalid nodes, {dropped_rels} invalid relationships.")

    await writer.run(graph=graph, lexical_graph_config=lexical_graph_config)
    print(f"Wrote {len(graph.nodes)} nodes, {len(graph.relationships)} relationships.")


asyncio.run(main())
