#!/usr/bin/env python3
"""Sync Garmin Connect data into garmin-data/ cache."""

import os
import sys
import json
import datetime
from pathlib import Path

try:
    from garminconnect import (
        Garmin,
        GarminConnectAuthenticationError,
        GarminConnectConnectionError,
        GarminConnectTooManyRequestsError,
    )
except ImportError:
    print("garminconnect library not installed. Run: pip install garminconnect", file=sys.stderr)
    sys.exit(1)

EMAIL = os.environ.get("GARMIN_EMAIL")
PASSWORD = os.environ.get("GARMIN_PASSWORD")
TOKENSTORE = os.environ.get("GARMIN_TOKENS_DIR", "/workspace/.garmin_tokens")

if not EMAIL or not PASSWORD:
    print("Error: GARMIN_EMAIL and GARMIN_PASSWORD environment variables must be set.", file=sys.stderr)
    sys.exit(1)

BASE_DIR = Path("/workspace/garmin-data")
ACTIVITIES_DIR = BASE_DIR / "activities"
DETAILS_DIR = BASE_DIR / "activity-details"
SLEEP_DIR = BASE_DIR / "sleep"
HRV_DIR = BASE_DIR / "hrv"
READINESS_DIR = BASE_DIR / "training-readiness"

for d in [ACTIVITIES_DIR, DETAILS_DIR, SLEEP_DIR, HRV_DIR, READINESS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

def get_client():
    token_path = Path(TOKENSTORE)
    token_path.mkdir(parents=True, exist_ok=True)
    
    garmin = Garmin(email=EMAIL, password=PASSWORD, is_cn=False, prompt_mfa=None)
    
    # Try logging in with saved tokens first
    try:
        garmin.login(str(token_path))
        print("Logged in using stored session tokens.")
    except Exception as e:
        print(f"Token login failed ({e}), attempting fresh credentials login...")
        try:
            garmin.login()
            garmin.garth.dump(str(token_path))
            print("Logged in with credentials and saved tokens.")
        except Exception as err:
            print(f"Login failed: {err}", file=sys.stderr)
            sys.exit(1)
            
    return garmin

def save_json(path: Path, data: dict, force: bool = False):
    if path.exists() and not force:
        return
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    payload = {
        "_fetched_at": now,
        "data": data
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"Saved: {path.relative_to(BASE_DIR)}")

def sync(days: int = 7):
    client = get_client()
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=days)
    
    print(f"Syncing Garmin data from {start_date} to {today}...")
    
    # 1. Activities
    try:
        activities = client.get_activities_by_date(start_date.isoformat(), today.isoformat())
        # Group by date
        by_date = {}
        for act in activities:
            start_time = act.get("startTimeLocal", "")
            if start_time:
                date_str = start_time.split(" ")[0].split("T")[0]
            else:
                date_str = today.isoformat()
            by_date.setdefault(date_str, []).append(act)
            
            act_id = act.get("activityId")
            if act_id:
                # Activity detail
                detail_file = DETAILS_DIR / f"{act_id}.json"
                if not detail_file.exists():
                    try:
                        detail = client.get_activity(act_id)
                        save_json(detail_file, detail)
                    except Exception as ex:
                        print(f"Could not fetch details for {act_id}: {ex}")
                
                # Splits
                splits_file = DETAILS_DIR / f"{act_id}.splits.json"
                if not splits_file.exists():
                    try:
                        splits = client.get_activity_splits(act_id)
                        save_json(splits_file, splits)
                    except Exception as ex:
                        pass
        
        for date_str, acts in by_date.items():
            act_file = ACTIVITIES_DIR / f"{date_str}.json"
            save_json(act_file, {"count": len(acts), "activities": acts}, force=(date_str == today.isoformat()))
            
    except Exception as e:
        print(f"Error fetching activities: {e}")

    # 2. Daily metrics (Sleep, HRV, Readiness)
    curr = start_date
    while curr <= today:
        d_str = curr.isoformat()
        is_today = (curr == today)
        
        # Sleep
        sleep_file = SLEEP_DIR / f"{d_str}.json"
        if not sleep_file.exists() or is_today:
            try:
                sleep_data = client.get_sleep_data(d_str)
                save_json(sleep_file, sleep_data, force=is_today)
            except Exception as e:
                pass
                
        # HRV
        hrv_file = HRV_DIR / f"{d_str}.json"
        if not hrv_file.exists() or is_today:
            try:
                hrv_data = client.get_hrv_data(d_str)
                save_json(hrv_file, hrv_data, force=is_today)
            except Exception as e:
                pass
                
        # Training Readiness
        readiness_file = READINESS_DIR / f"{d_str}.json"
        if not readiness_file.exists() or is_today:
            try:
                readiness_data = client.get_training_readiness(d_str)
                save_json(readiness_file, readiness_data, force=is_today)
            except Exception as e:
                pass
                
        curr += datetime.timedelta(days=1)
        
    print("Sync complete.")

if __name__ == "__main__":
    days_to_sync = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    sync(days_to_sync)
