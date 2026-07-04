import argparse
import json
import os
import sys
from datetime import datetime, timezone

from azure.data.tables import TableServiceClient
from dotenv import load_dotenv


def _json_safe(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        try:
            dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except Exception:
            return str(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    try:
        if hasattr(value, "isoformat"):
            return value.isoformat()
    except Exception:
        pass
    return str(value)


def _get_table_service():
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "").strip()
    if connection_string:
        return TableServiceClient.from_connection_string(conn_str=connection_string)

    account = os.getenv("AZURE_STORAGE_ACCOUNT", "").strip()
    if not account:
        raise RuntimeError(
            "Missing Azure storage configuration. Set AZURE_STORAGE_CONNECTION_STRING "
            "or AZURE_STORAGE_ACCOUNT."
        )

    from azure.identity import DefaultAzureCredential

    credential = DefaultAzureCredential()
    return TableServiceClient(
        endpoint=f"https://{account}.table.core.windows.net",
        credential=credential,
    )


def _normalize_select(select_text: str):
    if not select_text:
        return None
    fields = []
    seen = set()
    for part in select_text.split(","):
        field = part.strip()
        if not field or field in seen:
            continue
        seen.add(field)
        fields.append(field)
    return fields or None


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Run a read-only Azure Table query against LoginAudit or ResumeRevisions."
    )
    parser.add_argument(
        "table",
        choices=["LoginAudit", "ResumeRevisions"],
        help="Azure table to query",
    )
    parser.add_argument(
        "--filter",
        default="",
        help="Azure Table/OData filter expression, e.g. \"PartitionKey eq '123'\"",
    )
    parser.add_argument(
        "--select",
        default="",
        help="Comma-separated fields to return, e.g. PartitionKey,RowKey,timestamp",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=25,
        help="Maximum number of rows to print (default: 25, max recommended: 100)",
    )
    parser.add_argument(
        "--output",
        choices=["json", "jsonl"],
        default="json",
        help="Output format",
    )
    args = parser.parse_args()

    try:
        service = _get_table_service()
        table_client = service.get_table_client(args.table)
        select_fields = _normalize_select(args.select)
        safe_top = max(1, int(args.top or 25))

        if args.filter.strip():
            pager = table_client.query_entities(
                query_filter=args.filter.strip(),
                select=select_fields,
                results_per_page=min(safe_top, 1000),
            )
        else:
            pager = table_client.list_entities(
                select=select_fields,
                results_per_page=min(safe_top, 1000),
            )

        rows = []
        for entity in pager:
            rows.append(_json_safe(dict(entity)))
            if len(rows) >= safe_top:
                break

        if args.output == "jsonl":
            for row in rows:
                print(json.dumps(row, ensure_ascii=False))
        else:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "error": str(exc),
                    "table": args.table,
                    "filter": args.filter,
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
