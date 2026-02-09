#!/usr/bin/env python3
"""
View FalkorDB graph memory contents.

Usage:
    python scripts/graph_viewer.py stats
    python scripts/graph_viewer.py entities --limit 10
    python scripts/graph_viewer.py entities --user-id josh --type person
    python scripts/graph_viewer.py relationships --limit 10
    python scripts/graph_viewer.py relationships --type works_at
    python scripts/graph_viewer.py entity joshua
    python scripts/graph_viewer.py query "MATCH (n:__Entity__) RETURN n.name LIMIT 5"
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure project root is on sys.path when run directly (not via poetry run)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

DISPLAY_EXCLUDE_PROPS = {"embedding"}


def connect():
    """Connect to FalkorDB using app settings. Returns (graph, graph_name)."""
    try:
        import falkordb
    except ImportError:
        print("Error: falkordb is not installed. Run: pip install falkordb")
        sys.exit(1)

    from clara_core.config import get_settings

    gs = get_settings().memory.graph_store

    if not gs.enabled:
        print("Graph memory is disabled (ENABLE_GRAPH_MEMORY != true).")
        print("Set ENABLE_GRAPH_MEMORY=true in your .env to enable it.")
        sys.exit(1)

    client = falkordb.FalkorDB(
        host=gs.falkordb_host,
        port=gs.falkordb_port,
        password=gs.falkordb_password or None,
    )
    graph = client.select_graph(gs.falkordb_graph_name)
    return graph, gs.falkordb_graph_name


def query(graph, cypher, params=None):
    """Execute Cypher query and return list[dict] with column names as keys."""
    result = graph.query(cypher, params=params or {})
    if not result.result_set:
        return []
    column_names = [col[1] if isinstance(col, (list, tuple)) else col for col in result.header]
    return [dict(zip(column_names, row)) for row in result.result_set]


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def print_table(rows, columns=None):
    """Print rows as an aligned table."""
    if not rows:
        print("  (no results)")
        return

    if columns is None:
        columns = list(rows[0].keys())

    # Compute column widths
    widths = {col: len(col) for col in columns}
    str_rows = []
    for row in rows:
        str_row = {}
        for col in columns:
            val = row.get(col, "")
            if val is None:
                val = ""
            s = str(val)
            if len(s) > 80:
                s = s[:77] + "..."
            str_row[col] = s
            widths[col] = max(widths[col], len(s))
        str_rows.append(str_row)

    # Header
    header = "  ".join(col.ljust(widths[col]) for col in columns)
    print(header)
    print("  ".join("-" * widths[col] for col in columns))

    for sr in str_rows:
        print("  ".join(sr[col].ljust(widths[col]) for col in columns))


def format_node_props(node):
    """Format a FalkorDB Node's properties, excluding embeddings."""
    if hasattr(node, "properties"):
        props = node.properties
    elif isinstance(node, dict):
        props = node
    else:
        return str(node)
    return {k: v for k, v in props.items() if k not in DISPLAY_EXCLUDE_PROPS}


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_stats(args):
    graph, graph_name = connect()
    print(f"Graph: {graph_name}\n")

    # Entity count
    rows = query(graph, "MATCH (n:__Entity__) RETURN count(n) AS count")
    entity_count = rows[0]["count"] if rows else 0
    print(f"Entities: {entity_count}")

    # Relationship count
    rows = query(graph, "MATCH (:__Entity__)-[r]->(:__Entity__) RETURN count(r) AS count")
    rel_count = rows[0]["count"] if rows else 0
    print(f"Relationships: {rel_count}")

    # Unique users
    rows = query(graph, "MATCH (n:__Entity__) RETURN count(DISTINCT n.user_id) AS count")
    user_count = rows[0]["count"] if rows else 0
    print(f"Unique users: {user_count}")

    # Relationship type distribution
    rows = query(
        graph,
        "MATCH (:__Entity__)-[r]->(:__Entity__) "
        "RETURN type(r) AS rel_type, count(r) AS count "
        "ORDER BY count DESC",
    )
    if rows:
        print("\nRelationship types:")
        print_table(rows, ["rel_type", "count"])

    # Entity type distribution
    rows = query(
        graph,
        "MATCH (n:__Entity__) WHERE n.entity_type IS NOT NULL "
        "RETURN n.entity_type AS entity_type, count(n) AS count "
        "ORDER BY count DESC",
    )
    if rows:
        print("\nEntity types:")
        print_table(rows, ["entity_type", "count"])

    # Top entities by mentions
    rows = query(
        graph,
        "MATCH (n:__Entity__) WHERE n.mentions IS NOT NULL "
        "RETURN n.name AS name, n.mentions AS mentions, n.entity_type AS type, n.user_id AS user_id "
        "ORDER BY n.mentions DESC LIMIT 10",
    )
    if rows:
        print("\nTop entities by mentions:")
        print_table(rows, ["name", "mentions", "type", "user_id"])


def cmd_entities(args):
    graph, _ = connect()

    conditions = []
    params = {}

    if args.user_id:
        conditions.append("n.user_id = $user_id")
        params["user_id"] = args.user_id
    if args.type:
        conditions.append("n.entity_type = $entity_type")
        params["entity_type"] = args.type

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    sort_map = {
        "mentions": "n.mentions DESC",
        "name": "n.name ASC",
        "created": "n.created DESC",
    }
    order = sort_map.get(args.sort, "n.name ASC")

    params["limit"] = args.limit

    cypher = (
        f"MATCH (n:__Entity__) {where} "
        f"RETURN n.name AS name, n.entity_type AS type, n.user_id AS user_id, "
        f"n.mentions AS mentions, n.created AS created "
        f"ORDER BY {order} LIMIT $limit"
    )

    rows = query(graph, cypher, params)
    print(f"Entities ({len(rows)} results):\n")
    print_table(rows, ["name", "type", "user_id", "mentions", "created"])


def cmd_relationships(args):
    graph, _ = connect()

    conditions = []
    params = {}

    if args.user_id:
        conditions.append("n.user_id = $user_id")
        params["user_id"] = args.user_id
    if args.type:
        conditions.append("type(r) = $rel_type")
        params["rel_type"] = args.type

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params["limit"] = args.limit

    cypher = (
        f"MATCH (n:__Entity__)-[r]->(m:__Entity__) {where} "
        f"RETURN n.name AS source, type(r) AS relationship, m.name AS target, "
        f"r.mentions AS mentions, n.user_id AS user_id "
        f"ORDER BY r.mentions DESC LIMIT $limit"
    )

    rows = query(graph, cypher, params)
    print(f"Relationships ({len(rows)} results):\n")
    print_table(rows, ["source", "relationship", "target", "mentions", "user_id"])


def cmd_entity(args):
    graph, _ = connect()

    name = args.name.lower().replace(" ", "_")

    conditions = ["n.name = $name"]
    params = {"name": name}
    if args.user_id:
        conditions.append("n.user_id = $user_id")
        params["user_id"] = args.user_id

    where = " AND ".join(conditions)

    # Entity properties
    rows = query(graph, f"MATCH (n:__Entity__) WHERE {where} RETURN n", params)
    if not rows:
        print(f"Entity '{name}' not found.")
        return

    print(f"Entity: {name}\n")
    for row in rows:
        props = format_node_props(row["n"])
        for k, v in props.items():
            print(f"  {k}: {v}")
        if len(rows) > 1:
            print()

    # Outgoing relationships
    out_rows = query(
        graph,
        f"MATCH (n:__Entity__)-[r]->(m:__Entity__) WHERE {where} "
        f"RETURN type(r) AS relationship, m.name AS target, r.mentions AS mentions",
        params,
    )
    if out_rows:
        print(f"\nOutgoing ({len(out_rows)}):")
        print_table(out_rows, ["relationship", "target", "mentions"])

    # Incoming relationships
    in_rows = query(
        graph,
        f"MATCH (m:__Entity__)-[r]->(n:__Entity__) WHERE {where} "
        f"RETURN m.name AS source, type(r) AS relationship, r.mentions AS mentions",
        params,
    )
    if in_rows:
        print(f"\nIncoming ({len(in_rows)}):")
        print_table(in_rows, ["source", "relationship", "mentions"])

    if not out_rows and not in_rows:
        print("\n  (no relationships)")


def cmd_query(args):
    graph, _ = connect()

    params = {}
    if args.params:
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError as e:
            print(f"Error parsing --params JSON: {e}")
            sys.exit(1)

    rows = query(graph, args.cypher, params)
    print(f"Results ({len(rows)}):\n")

    if rows:
        # Auto-detect columns, format node/edge objects
        formatted = []
        for row in rows:
            fmt = {}
            for k, v in row.items():
                if hasattr(v, "properties"):
                    fmt[k] = format_node_props(v)
                else:
                    fmt[k] = v
            formatted.append(fmt)
        print_table(formatted)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="View FalkorDB graph memory contents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # stats
    sub.add_parser("stats", help="Show graph statistics")

    # entities
    p_ent = sub.add_parser("entities", help="List entities")
    p_ent.add_argument("--user-id", "-u", help="Filter by user ID")
    p_ent.add_argument("--type", "-t", help="Filter by entity type")
    p_ent.add_argument("--limit", "-n", type=int, default=50, help="Max results (default: 50)")
    p_ent.add_argument(
        "--sort",
        "-s",
        choices=["mentions", "name", "created"],
        default="name",
        help="Sort order (default: name)",
    )

    # relationships
    p_rel = sub.add_parser("relationships", help="List relationships")
    p_rel.add_argument("--user-id", "-u", help="Filter by user ID")
    p_rel.add_argument("--type", "-t", help="Filter by relationship type")
    p_rel.add_argument("--limit", "-n", type=int, default=50, help="Max results (default: 50)")

    # entity
    p_one = sub.add_parser("entity", help="Show details for a single entity")
    p_one.add_argument("name", help="Entity name (spaces are converted to underscores)")
    p_one.add_argument("--user-id", "-u", help="Filter by user ID")

    # query
    p_q = sub.add_parser("query", help="Execute raw Cypher query")
    p_q.add_argument("cypher", help="Cypher query string")
    p_q.add_argument("--params", "-p", help='JSON parameters (e.g. \'{"name": "josh"}\')')

    args = parser.parse_args()

    dispatch = {
        "stats": cmd_stats,
        "entities": cmd_entities,
        "relationships": cmd_relationships,
        "entity": cmd_entity,
        "query": cmd_query,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
