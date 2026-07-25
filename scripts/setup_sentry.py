#!/usr/bin/env python3
"""Create Sentry issue-alert rules that route to Slack — run once after you have
connected Slack in Sentry (Settings → Integrations → Slack → Add to a channel).

Usage:
    export SENTRY_AUTH_TOKEN=sntrys_...        # the org token from `sentry-cli login`
    export SENTRY_ORG=meet-w7
    export SENTRY_PROJECT=studybuddy
    export SLACK_CHANNEL='#alerts'             # the channel Slack was added to
    python scripts/setup_sentry.py

It auto-discovers your Slack integration, then creates (idempotently, by name):
  • High error volume  — >20 events in 1h
  • New issue          — first seen
  • Regression         — a resolved issue comes back
  • Crash              — an unhandled/fatal error appears

Everything is env-driven; no secrets are written to disk. Safe to re-run.
"""
import json
import os
import sys
import urllib.error
import urllib.request

# EU-region orgs (like meet-w7) live on de.sentry.io. Override via SENTRY_BASE_URL.
BASE = os.environ.get("SENTRY_BASE_URL", "https://de.sentry.io").rstrip("/") + "/api/0"
TOKEN = os.environ.get("SENTRY_AUTH_TOKEN")
ORG = os.environ.get("SENTRY_ORG", "meet-w7")
PROJECT = os.environ.get("SENTRY_PROJECT", "studybuddy")
CHANNEL = os.environ.get("SLACK_CHANNEL", "#alerts")


def _req(method: str, path: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def _slack_integration_id():
    status, data = _req("GET", f"/organizations/{ORG}/integrations/?provider_key=slack")
    if status != 200 or not data:
        return None
    for integ in data:
        if integ.get("status") == "active":
            return integ.get("id")
    return data[0].get("id") if data else None


def _slack_action(integration_id: str):
    return {
        "id": "sentry.integrations.slack.notify_action.SlackNotifyServiceAction",
        "workspace": str(integration_id),
        "channel": CHANNEL,
        "tags": "environment,component",
    }


RULES = [
    {
        "name": "StudyBuddy — High error volume",
        "frequency": 60,
        "conditions": [
            {"id": "sentry.rules.conditions.event_frequency.EventFrequencyCondition",
             "interval": "1h", "value": 20, "comparisonType": "count"}
        ],
    },
    {
        "name": "StudyBuddy — New issue",
        "frequency": 30,
        "conditions": [
            {"id": "sentry.rules.conditions.first_seen_event.FirstSeenEventCondition"}
        ],
    },
    {
        "name": "StudyBuddy — Regression",
        "frequency": 30,
        "conditions": [
            {"id": "sentry.rules.conditions.regression_event.RegressionEventCondition"}
        ],
    },
    {
        "name": "StudyBuddy — Crash / fatal",
        "frequency": 30,
        "conditions": [
            {"id": "sentry.rules.conditions.first_seen_event.FirstSeenEventCondition"}
        ],
        "filters": [
            {"id": "sentry.rules.filters.level.LevelFilter", "match": "gte", "level": "50"}
        ],
    },
]


def main() -> int:
    if not TOKEN:
        print("❌ SENTRY_AUTH_TOKEN not set. export it (the sntrys_… org token) first.")
        return 1

    integ_id = _slack_integration_id()
    if not integ_id:
        print("⚠️  No active Slack integration found on org", ORG)
        print("   → In Sentry: Settings → Integrations → Slack → install & add to a channel,")
        print("     then re-run this script. (Alert rules need the Slack integration id.)")
        return 2
    print(f"✅ Slack integration id: {integ_id} → channel {CHANNEL}")

    _status, existing = _req("GET", f"/projects/{ORG}/{PROJECT}/rules/")
    have = {r.get("name") for r in existing} if isinstance(existing, list) else set()

    action = _slack_action(integ_id)
    created = 0
    for rule in RULES:
        if rule["name"] in have:
            print(f"• exists, skipping: {rule['name']}")
            continue
        payload = {
            "name": rule["name"],
            "actionMatch": "all",
            "filterMatch": "all",
            "frequency": rule["frequency"],
            "environment": None,
            "conditions": rule["conditions"],
            "filters": rule.get("filters", []),
            "actions": [action],
        }
        st, resp = _req("POST", f"/projects/{ORG}/{PROJECT}/rules/", payload)
        if st in (200, 201):
            created += 1
            print(f"✅ created: {rule['name']}")
        else:
            print(f"❌ failed ({st}): {rule['name']} → {resp}")

    print(f"\nDone. {created} rule(s) created; {len(RULES) - created} already present/failed.")
    print("Metric/performance alerts (p95 latency, etc.) can be added the same way")
    print("in Sentry → Alerts → Create Alert → Metric alert → Slack.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
