"""
Neo4j Database Client (GraphRAG V5)
Persistence-only layer.

STRICT RULES:
- NO graph logic
- NO heuristics
- NO embeddings
- NO chunk-level reasoning
- SECTION is the atomic provenance unit
"""

from typing import Dict, Any, Optional
from neo4j import GraphDatabase

from config.settings import (
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
)


class Neo4jClient:
    """Neo4j persistence client for GraphRAG."""

    def __init__(self, uri=None, username=None, password=None):
        self.uri = uri or NEO4J_URI
        self.username = username or NEO4J_USERNAME
        self.password = password or NEO4J_PASSWORD

        self.driver = GraphDatabase.driver(
            self.uri,
            auth=(self.username, self.password),
        )

    # ==================================================
    # Lifecycle
    # ==================================================

    def close(self):
        self.driver.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def verify_connection(self) -> bool:
        try:
            with self.driver.session() as session:
                session.run("RETURN 1")
            return True
        except Exception as e:
            print(f"Neo4j connection failed: {e}")
            return False

    # ==================================================
    # Indexes & Constraints
    # ==================================================

    def setup_indexes(self):
        """
        Create required indexes and constraints.
        """
        with self.driver.session() as session:
            # ---- Section ----
            session.run("""
                CREATE CONSTRAINT section_unique IF NOT EXISTS
                FOR (s:Section)
                REQUIRE (s.doc_id, s.section_id) IS UNIQUE
            """)

            # ---- Entity ----
            session.run("""
                CREATE INDEX entity_lookup IF NOT EXISTS
                FOR (e:Entity)
                ON (e.doc_id, e.name)
            """)

            # ---- FinancialFact ----
            session.run("""
                CREATE INDEX financial_fact_metric IF NOT EXISTS
                FOR (f:FinancialFact)
                ON (f.metric)
            """)

            # ---- TimePeriod ----
            session.run("""
                CREATE INDEX timeperiod_label IF NOT EXISTS
                FOR (t:TimePeriod)
                ON (t.label)
            """)

            # ---- Community ----
            session.run("""
                CREATE INDEX community_id IF NOT EXISTS
                FOR (c:Community)
                ON (c.community_id)
            """)

        print("✅ Indexes and constraints created")

    # ==================================================
    # Graph reset
    # ==================================================

    def clear_graph(self):
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        print("⚠️ Graph cleared")

    # ==================================================
    # Entities
    # ==================================================

    def create_entity(
        self,
        name: str,
        entity_type: str,
        description: str,
        salience: str = "SUPPORTING",
        doc_id: str = "doc-1",
    ) -> Dict[str, Any]:
        """
        Create or update an Entity node (doc-scoped).
        """
        with self.driver.session() as session:
            rec = session.run(
                """
                MERGE (e:Entity {doc_id: $doc_id, name: $name})
                ON CREATE SET
                    e.type = $type,
                    e.description = $description,
                    e.salience = $salience,
                    e.created_at = datetime()
                ON MATCH SET
                    e.description =
                        CASE WHEN size($description) > size(e.description)
                        THEN $description ELSE e.description END,
                    e.salience =
                        CASE WHEN e.salience = 'SUPPORTING'
                             AND $salience IN ['CORE','IMPORTANT']
                        THEN $salience ELSE e.salience END
                RETURN e.name AS name, e.salience AS salience
                """,
                doc_id=doc_id,
                name=name,
                type=entity_type,
                description=description,
                salience=salience,
            ).single()

        return dict(rec) if rec else None

    def create_relationship(
        self,
        source_name: str,
        target_name: str,
        rel_type: str,
        description: str = "",
        doc_id: str = "doc-1",
    ) -> bool:
        """
        Create an allowed Entity→Entity relationship (doc-scoped).
        """
        allowed = {"DEFINES", "DETAILS", "REFERS_TO", "ASSOCIATED_WITH"}
        rel_type = rel_type.upper()

        if rel_type not in allowed:
            return False

        with self.driver.session() as session:
            session.run(
                f"""
                MATCH (s:Entity {{doc_id:$doc, name:$src}})
                MATCH (t:Entity {{doc_id:$doc, name:$tgt}})
                MERGE (s)-[r:{rel_type}]->(t)
                SET r.description = $desc
                """,
                doc=doc_id,
                src=source_name,
                tgt=target_name,
                desc=description,
            )
        return True

    # ==================================================
    # Sections
    # ==================================================

    def create_section(
        self,
        section_id: str,
        title: str,
        level: int,
        parent_id: Optional[str] = None,
        doc_id: str = "doc-1",
        page_start: Optional[int] = None,
        page_end: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Create a Section node.
        """
        with self.driver.session() as session:
            rec = session.run(
                """
                MERGE (s:Section {doc_id: $doc_id, section_id: $sid})
                ON CREATE SET
                    s.title = $title,
                    s.level = $level,
                    s.page_start = $ps,
                    s.page_end = $pe,
                    s.created_at = datetime()
                RETURN s.section_id AS section_id
                """,
                doc_id=doc_id,
                sid=section_id,
                title=title,
                level=level,
                ps=page_start,
                pe=page_end,
            ).single()

            if parent_id:
                session.run(
                    """
                    MATCH (c:Section {doc_id:$doc, section_id:$cid})
                    MATCH (p:Section {doc_id:$doc, section_id:$pid})
                    MERGE (c)-[:PART_OF]->(p)
                    """,
                    doc=doc_id,
                    cid=section_id,
                    pid=parent_id,
                )

        return dict(rec) if rec else None

    # ==================================================
    # Provenance
    # ==================================================

    def link_entity_to_section(
        self,
        entity_name: str,
        section_id: str,
        doc_id: str = "doc-1",
    ):
        with self.driver.session() as session:
            session.run(
                """
                MATCH (s:Section {doc_id:$doc, section_id:$sid})
                MATCH (e:Entity {doc_id:$doc, name:$name})
                MERGE (s)-[:MENTIONS]->(e)
                """,
                doc=doc_id,
                sid=section_id,
                name=entity_name,
            )

    # ==================================================
    # TimePeriod
    # ==================================================

    def create_timeperiod(
        self,
        label: str,
        year: int,
        period_type: str,
    ):
        with self.driver.session() as session:
            session.run(
                """
                MERGE (t:TimePeriod {label: $label})
                SET t.year = $year, t.period_type = $ptype
                """,
                label=label,
                year=year,
                ptype=period_type,
            )

    def link_section_to_timeperiod(
        self,
        section_id: str,
        label: str,
        doc_id: str = "doc-1",
    ):
        with self.driver.session() as session:
            session.run(
                """
                MATCH (s:Section {doc_id:$doc, section_id:$sid})
                MATCH (t:TimePeriod {label:$label})
                MERGE (s)-[:APPLIES_TO]->(t)
                """,
                doc=doc_id,
                sid=section_id,
                label=label,
            )

    # ==================================================
    # Financial Facts
    # ==================================================

    def create_financial_fact(
        self,
        metric: str,
        value: Any,
        unit: str,
        scale: str,
        period_type: str,
        period_value: str,
        confidence: str,
        doc_id: str = "doc-1",
    ):
        with self.driver.session() as session:
            session.run(
                """
                MERGE (f:FinancialFact {
                    doc_id:$doc,
                    metric:$metric,
                    value:$value,
                    period_value:$pval
                })
                SET f.unit=$unit,
                    f.scale=$scale,
                    f.period_type=$ptype,
                    f.confidence=$conf,
                    f.created_at=datetime()
                """,
                doc=doc_id,
                metric=metric,
                value=value,
                unit=unit,
                scale=scale,
                ptype=period_type,
                pval=period_value,
                conf=confidence,
            )

    def link_section_to_financial_fact(
        self,
        section_id: str,
        metric: str,
        value: Any,
        period_value: str,
        doc_id: str = "doc-1",
    ):
        with self.driver.session() as session:
            session.run(
                """
                MATCH (s:Section {doc_id:$doc, section_id:$sid})
                MATCH (f:FinancialFact {
                    doc_id:$doc,
                    metric:$metric,
                    value:$value,
                    period_value:$pval
                })
                MERGE (s)-[:STATES]->(f)
                """,
                doc=doc_id,
                sid=section_id,
                metric=metric,
                value=value,
                pval=period_value,
            )

    def link_financial_fact_to_entity(
        self,
        metric: str,
        value: Any,
        period_value: str,
        entity_name: str,
        doc_id: str = "doc-1",
    ):
        with self.driver.session() as session:
            session.run(
                """
                MATCH (f:FinancialFact {
                    doc_id:$doc,
                    metric:$metric,
                    value:$value,
                    period_value:$pval
                })
                MATCH (e:Entity {doc_id:$doc, name:$ename})
                MERGE (f)-[:MEASURES]->(e)
                """,
                doc=doc_id,
                metric=metric,
                value=value,
                pval=period_value,
                ename=entity_name,
            )

    # ==================================================
    # Stats
    # ==================================================

    def get_graph_stats(self) -> Dict[str, int]:
        with self.driver.session() as session:
            return {
                "entities": session.run(
                    "MATCH (e:Entity) RETURN count(e) AS c"
                ).single()["c"],
                "sections": session.run(
                    "MATCH (s:Section) RETURN count(s) AS c"
                ).single()["c"],
                "relationships": session.run(
                    "MATCH ()-[r]->() RETURN count(r) AS c"
                ).single()["c"],
                "timeperiods": session.run(
                    "MATCH (t:TimePeriod) RETURN count(t) AS c"
                ).single()["c"],
                "financial_facts": session.run(
                    "MATCH (f:FinancialFact) RETURN count(f) AS c"
                ).single()["c"],
            }


if __name__ == "__main__":
    with Neo4jClient() as client:
        assert client.verify_connection()
        client.setup_indexes()
        print(client.get_graph_stats())
