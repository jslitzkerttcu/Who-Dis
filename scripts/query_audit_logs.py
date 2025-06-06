#!/usr/bin/env python3
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.audit_service import AuditService
import json


def print_searches(days=7):
    """Print recent search activity"""
    audit = AuditService()

    print(f"\n=== Search Activity (Last {days} Days) ===")
    searches = audit.get_recent_searches(limit=100)

    for search in searches:
        print(f"\nTimestamp: {search['timestamp']}")
        print(f"User: {search['user_email']} (Role: {search['user_role']})")
        print(f"Search Query: {search['search_query']}")
        print(f"Results Found: {search['search_results_count']}")
        print(f"Services Used: {search['search_services']}")
        print(f"IP Address: {search['ip_address']}")
        if search["error_message"]:
            print(f"Errors: {search['error_message']}")
        if search["additional_data"]:
            data = json.loads(search["additional_data"])
            print(f"Additional Info: {data}")


def print_user_activity(user_email, days=30):
    """Print activity for a specific user"""
    audit = AuditService()

    print(f"\n=== Activity for {user_email} (Last {days} Days) ===")
    activities = audit.get_user_activity(user_email, days)

    for activity in activities:
        print(f"\nTimestamp: {activity['timestamp']}")
        print(f"Event Type: {activity['event_type']}")
        print(f"Action: {activity['action']}")
        if activity["search_query"]:
            print(f"Search Query: {activity['search_query']}")
        if activity["target_resource"]:
            print(f"Target: {activity['target_resource']}")
        print(f"Success: {activity['success']}")
        if activity["error_message"]:
            print(f"Error: {activity['error_message']}")


def print_statistics(days=30):
    """Print search statistics"""
    audit = AuditService()

    print(f"\n=== Search Statistics (Last {days} Days) ===")
    stats = audit.get_search_statistics(days)

    print(f"Total Searches: {stats['total_searches']}")
    print(f"Unique Users: {stats['unique_users']}")
    print(f"Unique Queries: {stats['unique_queries']}")
    print(f"Average Results per Search: {stats['avg_results']:.2f}")
    print(f"Failed Searches: {stats['failed_searches']}")

    print("\nTop 10 Search Queries:")
    for i, query in enumerate(stats["top_searches"], 1):
        print(f"{i}. '{query['search_query']}' - {query['count']} times")


def print_access_denials(days=7):
    """Print access denial events"""
    audit = AuditService()

    print(f"\n=== Access Denials (Last {days} Days) ===")
    # Query audit log for access denials
    with audit._get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM audit_log
            WHERE event_type = 'access' 
            AND success = 0
            AND timestamp >= datetime('now', ? || ' days')
            ORDER BY timestamp DESC
        """,
            (-days,),
        )

        denials = [dict(row) for row in cursor]

    for denial in denials:
        print(f"\nTimestamp: {denial['timestamp']}")
        print(f"User: {denial['user_email']} (Role: {denial['user_role']})")
        print(f"Resource: {denial['target_resource']}")
        print(f"IP Address: {denial['ip_address']}")


def print_config_changes(days=30):
    """Print configuration changes"""
    audit = AuditService()

    print(f"\n=== Configuration Changes (Last {days} Days) ===")
    changes = audit.get_config_changes(days)

    for change in changes:
        print(f"\nTimestamp: {change['timestamp']}")
        print(f"User: {change['user_email']} (Role: {change['user_role']})")
        print(f"Action: {change['action']}")
        print(f"Config Key: {change['target_resource']}")
        if change["additional_data"]:
            data = json.loads(change["additional_data"])
            if "old_value" in data:
                print(f"Old Value: {data['old_value']}")
            if "new_value" in data:
                print(f"New Value: {data['new_value']}")
        print(f"IP Address: {change['ip_address']}")


def print_errors(days=7):
    """Print application errors"""
    audit = AuditService()

    print(f"\n=== Application Errors (Last {days} Days) ===")
    errors = audit.get_errors(days)

    for error in errors:
        print(f"\nTimestamp: {error['timestamp']}")
        print(f"Error Type: {error['action']}")
        print(f"Error Message: {error['error_message']}")
        print(f"User: {error['user_email']} (Role: {error['user_role']})")
        print(f"Path: {error['target_resource']}")
        print(f"IP Address: {error['ip_address']}")
        if error["additional_data"]:
            data = json.loads(error["additional_data"])
            if "request_method" in data:
                print(f"Method: {data['request_method']}")
            if "url" in data:
                print(f"URL: {data['url']}")

    # Print error statistics
    stats = audit.get_error_statistics(days)
    print("\n=== Error Statistics ===")
    print(f"Total Errors: {stats['total_errors']}")
    print(f"Unique Error Types: {stats['unique_error_types']}")
    print(f"Affected Users: {stats['affected_users']}")
    print(f"Affected Paths: {stats['affected_paths']}")

    if stats["top_errors"]:
        print("\nTop Error Types:")
        for i, error in enumerate(stats["top_errors"], 1):
            print(f"{i}. {error['error_type']} - {error['count']} times")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Query WhoDis audit logs")
    parser.add_argument("--searches", action="store_true", help="Show recent searches")
    parser.add_argument("--user", help="Show activity for specific user")
    parser.add_argument("--stats", action="store_true", help="Show search statistics")
    parser.add_argument("--denials", action="store_true", help="Show access denials")
    parser.add_argument(
        "--config", action="store_true", help="Show configuration changes"
    )
    parser.add_argument("--errors", action="store_true", help="Show application errors")
    parser.add_argument(
        "--days", type=int, default=7, help="Number of days to look back"
    )

    args = parser.parse_args()

    if args.searches:
        print_searches(args.days)
    elif args.user:
        print_user_activity(args.user, args.days)
    elif args.stats:
        print_statistics(args.days)
    elif args.denials:
        print_access_denials(args.days)
    elif args.config:
        print_config_changes(args.days)
    elif args.errors:
        print_errors(args.days)
    else:
        # Default: show everything
        print_searches(args.days)
        print_statistics(args.days)
        print_access_denials(args.days)
