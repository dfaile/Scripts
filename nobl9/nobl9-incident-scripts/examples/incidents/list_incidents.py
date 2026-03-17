#!/usr/bin/env python3
"""List disruptions (Mar 16 API).

Uses GET /status-page/disruptions?state=impacting|cleared&limit=&offset=
Returns paginated ListDisruptionsResult: disruptions[], total, limit, offset.
Disruption shape: id (encoded), startTime, endTime, isCleared, originComponent,
affectedComponents, severity, source, etc.

Optionally use --timeline to get disruptions grouped by day via POST /disruptions/timeline.

Usage:
    python list_incidents.py [--impacting | --cleared] [--limit N] [--timeline]

Options:
    --impacting: state=impacting (only impacting)
    --cleared: state=cleared (only cleared)
    (no flag): no state filter (all disruptions)
    --limit N: max results (default 50)
    --timeline: use POST /disruptions/timeline for day-grouped view

Examples:
    python list_incidents.py --impacting
    python list_incidents.py --cleared --limit 20
    python list_incidents.py --timeline

Environment Variables:
    NOBL9_API_TOKEN or NOBL9_CLIENT_ID+NOBL9_CLIENT_SECRET, NOBL9_ORG (required)
"""
import sys
import argparse

from examples.common import get_config, StatusPageClient, pretty_print, APIError


def list_disruptions(
    client: StatusPageClient,
    state: str = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List disruptions (paginated). state=impacting|cleared or None for all."""
    params = {"limit": str(limit), "offset": str(offset)}
    if state:
        params["state"] = state
    return client.get_disruptions(params=params)


def get_disruptions_timeline(client: StatusPageClient, impacting_only: bool = None) -> dict:
    """Get disruptions grouped by day (POST /disruptions/timeline)."""
    body = {}
    if impacting_only is not None:
        body["impactingOnly"] = impacting_only
    return client.get_disruptions_timeline(body if body else {})


def print_disruptions_summary(data: dict, use_timeline: bool = False) -> None:
    """Print summary from ListDisruptionsResult or timeline result."""
    if use_timeline:
        days = data.get("days") or []
        if not days:
            print("No disruptions in timeline.")
            return
        total = sum(d.get("count", 0) for d in days)
        print(f"\nTotal disruptions: {total} across {len(days)} days")
        print("\nDisruption Timeline:")
        print("-" * 80)
        for day in days[:14]:
            print(f"\n📅 {day.get('date')}: {day.get('count')} disruption(s)")
            for disruption in (day.get("disruptions") or [])[:5]:
                origin = (disruption.get("originComponent") or {}).get("name", "?")
                res = "✅" if disruption.get("isCleared") else "🔴"
                print(f"  {res} {origin} - {disruption.get('severity')}  start={disruption.get('startTime')}")
        return

    disruptions = data.get("disruptions") or []
    total = data.get("total", len(disruptions))
    limit = data.get("limit", 0)
    offset = data.get("offset", 0)
    print(f"\nDisruptions: showing {len(disruptions)} (offset {offset}, limit {limit}), total {total}")
    print("-" * 80)
    if not disruptions:
        print("No disruptions found.")
        return
    for disruption in disruptions:
        origin = disruption.get("originComponent") or {}
        origin_name = origin.get("name", "?")
        res = "✅" if disruption.get("isCleared") else "🔴"
        print(f"\n  {res} id={disruption.get('id')}  {disruption.get('severity')}  origin: {origin_name}")
        print(f"     start={disruption.get('startTime')}  end={disruption.get('endTime')}")
        if disruption.get("title"):
            print(f"     title: {disruption.get('title')}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="List disruptions (Mar 16 API)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--impacting", action="store_true", help="state=impacting (impacting only)")
    group.add_argument("--cleared", action="store_true", help="state=cleared only")
    parser.add_argument("--limit", type=int, default=50, help="Max results (default 50)")
    parser.add_argument("--timeline", action="store_true", help="Use POST /disruptions/timeline (day-grouped)")
    args = parser.parse_args()

    try:
        config = get_config()
        client = StatusPageClient(config)

        if args.timeline:
            impacting_only = None
            if args.impacting:
                impacting_only = True
            elif args.cleared:
                impacting_only = False
            print("Fetching disruptions timeline...")
            result = get_disruptions_timeline(client, impacting_only=impacting_only)
            print_disruptions_summary(result, use_timeline=True)
        else:
            state = None
            if args.impacting:
                state = "impacting"
                print("Fetching impacting disruptions...")
            elif args.cleared:
                state = "cleared"
                print("Fetching cleared disruptions...")
            else:
                print("Fetching all disruptions...")
            result = list_disruptions(client, state=state, limit=args.limit)
            print_disruptions_summary(result)

        print("\n\nFull response:")
        print("=" * 80)
        pretty_print(result)

    except APIError as e:
        print(f"API Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Configuration Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
