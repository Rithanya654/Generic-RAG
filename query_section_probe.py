"""
QUERY ENGINE — GRAPH ONLY (READ-ONLY)
------------------------------------
✔ Queries existing Neo4j graph
✔ No bots
✔ No writes
✔ No scope assumption
"""

import re
from database.neo4j_client import Neo4jClient


METRIC_MAP = {
    "asset": "Assets",
    "assets": "Assets",
    "liability": "Liabilities",
    "liabilities": "Liabilities",
    "equity": "Equity",
    "revenue": "Revenue",
    "profit": "Profit",
    "cash": "CashFlow",
}


def parse_question(question: str):
    q = question.lower()

    metric = None
    for k, v in METRIC_MAP.items():
        if k in q:
            metric = v
            break

    year_match = re.search(r"(19|20)\d{2}", q)
    year = int(year_match.group()) if year_match else None

    if not metric or not year:
        raise ValueError(
            "Try: 'What were total assets in 2024?'"
        )

    return metric, year


def build_cypher(metric: str, year: int) -> str:
    return f"""
    MATCH (f:FinancialFact)
    WHERE f.metric = "{metric}"
      AND f.period_type = "YEAR"
      AND f.period_value = {year}
    RETURN f.value AS value, f.unit AS unit
    """


def run_query(neo4j: Neo4jClient, cypher: str):
    with neo4j.driver.session() as session:
        return [r.data() for r in session.run(cypher)]


def main():
    print("=" * 60)
    print("GRAPH QUERY MODE (READ-ONLY)")
    print("Type a question or 'exit'")
    print("=" * 60)

    with Neo4jClient() as neo4j:
        assert neo4j.verify_connection()

        while True:
            q = input("\n>> ").strip()
            if q.lower() in {"exit", "quit"}:
                break

            try:
                metric, year = parse_question(q)
                cypher = build_cypher(metric, year)

                print("\nCypher:")
                print(cypher.strip())

                results = run_query(neo4j, cypher)

                if not results:
                    print("\nNo results found.")
                    continue

                print("\nResult:")
                for r in results:
                    print(f"{r['value']:>15,.0f} | {r['unit']}")

            except Exception as e:
                print(f"Error: {e}")


if __name__ == "__main__":
    main()
