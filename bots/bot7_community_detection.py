"""
Bot 7: Section Community Detection (V6-ADAPTIVE)
------------------------------------------------
Detect semantic communities of SECTIONS using:
- Explicit cross-section references
- Shared salient entities
- Adaptive logic for small vs large documents

NO LLMs
NO embeddings
Graph-only logic
"""

import networkx as nx
import community.community_louvain as community_louvain
from typing import Dict, Any, List

from database.neo4j_client import Neo4jClient


# ==================================================
# Graph Construction
# ==================================================

def get_section_graph(neo4j: Neo4jClient, doc_id: str) -> nx.Graph:
    """
    Build a Section–Section graph using:
    1. Explicit cross-section references (strong signal)
    2. Shared CORE / IMPORTANT entities (soft signal)
    """

    G = nx.Graph()

    with neo4j.driver.session() as session:

        # ------------------
        # Sections
        # ------------------
        sections = session.run("""
            MATCH (s:Section {doc_id: $doc_id})
            RETURN s.section_id AS id, s.title AS title
        """, doc_id=doc_id)

        for r in sections:
            G.add_node(r["id"], title=r["title"])

        # ------------------
        # Explicit references (strong)
        # ------------------
        refs = session.run("""
            MATCH (s1:Section {doc_id: $doc_id})
                  -[:REFERS_TO]->(:Reference)
                  -[:POINTS_TO]->(s2:Section {doc_id: $doc_id})
            RETURN s1.section_id AS src, s2.section_id AS tgt
        """, doc_id=doc_id)

        for r in refs:
            G.add_edge(
                r["src"],
                r["tgt"],
                weight=3.0,
                source="reference"
            )

        # ------------------
        # Shared salient entities (soft)
        # ------------------
        shared = session.run("""
            MATCH (s1:Section {doc_id: $doc_id})
                  -[:MENTIONS]->(e:Entity)
                  <-[:MENTIONS]-(s2:Section {doc_id: $doc_id})
            WHERE e.salience IN ['CORE', 'IMPORTANT']
              AND s1.section_id < s2.section_id
            RETURN s1.section_id AS src,
                   s2.section_id AS tgt,
                   count(DISTINCT e) AS shared
        """, doc_id=doc_id)

        for r in shared:
            if r["shared"] >= 1:
                G.add_edge(
                    r["src"],
                    r["tgt"],
                    weight=1.0 + min(r["shared"], 3),
                    source="entity"
                )

    return G


# ==================================================
# Community Persistence
# ==================================================

def _persist_communities(
    neo4j: Neo4jClient,
    communities: Dict[int, List[str]],
    doc_id: str,
    modularity: float,
    mode: str,
) -> Dict[str, Any]:
    """
    Persist communities and section memberships.
    """

    with neo4j.driver.session() as session:
        for cid, sections in communities.items():

            session.run("""
                MERGE (c:Community {
                    community_id: $cid,
                    doc_id: $doc_id
                })
                SET c.size = $size,
                    c.modularity = $modularity,
                    c.mode = $mode
            """, cid=str(cid),
                 doc_id=doc_id,
                 size=len(sections),
                 modularity=modularity,
                 mode=mode)

            for sid in sections:
                session.run("""
                    MATCH (s:Section {
                        doc_id: $doc_id,
                        section_id: $sid
                    })
                    MATCH (c:Community {
                        doc_id: $doc_id,
                        community_id: $cid
                    })
                    MERGE (c)-[:CONTAINS]->(s)
                """, doc_id=doc_id, sid=sid, cid=str(cid))

    print(f"✅ Communities persisted ({mode} mode)")

    return {
        "status": "ok",
        "mode": mode,
        "communities": len(communities),
        "modularity": modularity,
    }


# ==================================================
# Community Detection (Adaptive)
# ==================================================

def detect_section_communities(
    neo4j: Neo4jClient,
    doc_id: str = "doc-1",
) -> Dict[str, Any]:
    """
    Adaptive community detection:
    - Small docs (≤15 sections): heuristic mode
    - Large docs (>15 sections): modularity-gated mode
    """

    G = get_section_graph(neo4j, doc_id)

    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()

    print(f"📊 Section graph: {n_nodes} nodes, {n_edges} edges")

    if n_nodes == 0:
        return {
            "status": "empty",
            "reason": "no sections found"
        }

    # ==================================================
    # SMALL DOCUMENT MODE (TRIAL / POC)
    # ==================================================
    if n_nodes <= 15:
        print("🧪 Small-document mode enabled")

        if n_edges == 0:
            # Fully disconnected → single fallback community
            print("⚠️ No edges found — creating single fallback community")
            communities = {0: list(G.nodes())}
            modularity = 0.0
        else:
            partition = community_louvain.best_partition(G, weight="weight")
            modularity = community_louvain.modularity(
                partition, G, weight="weight"
            )

            communities: Dict[int, List[str]] = {}
            for sid, cid in partition.items():
                communities.setdefault(cid, []).append(sid)

        return _persist_communities(
            neo4j,
            communities,
            doc_id,
            modularity,
            mode="small",
        )

    # ==================================================
    # NORMAL DOCUMENT MODE (PRODUCTION)
    # ==================================================
    if n_edges < n_nodes:
        print("⚠️ Graph too sparse — skipping community detection")
        return {
            "status": "skipped",
            "reason": "graph too sparse",
            "nodes": n_nodes,
            "edges": n_edges,
        }

    partition = community_louvain.best_partition(G, weight="weight")
    modularity = community_louvain.modularity(partition, G, weight="weight")

    print(f"📐 Modularity: {modularity:.3f}")

    if modularity < 0.15:
        print("⚠️ Low modularity — rejecting communities")
        return {
            "status": "rejected",
            "modularity": modularity,
        }

    communities: Dict[int, List[str]] = {}
    for sid, cid in partition.items():
        communities.setdefault(cid, []).append(sid)

    # Remove singleton communities
    communities = {
        cid: secs
        for cid, secs in communities.items()
        if len(secs) >= 2
    }

    return _persist_communities(
        neo4j,
        communities,
        doc_id,
        modularity,
        mode="normal",
    )


# ==================================================
# Debug
# ==================================================

if __name__ == "__main__":
    with Neo4jClient() as client:
        if client.verify_connection():
            result = detect_section_communities(client)
            print(result)
