# Garmin Data Cache

Local cache of Garmin data fetched via the `user-garmin` MCP server.
Populated and consumed by the `training-status` skill.

## Purpose

Avoid re-fetching data that has already been pulled. Every response from `user-garmin`
is written here as raw JSON, keyed by date or activity id. When the skill needs data,
it checks here first and only calls the MCP when the file is missing.

## Layout

```
garmin-data/
├── README.md
├── activities/            # get_activities_by_date results, one file per day
│   └── YYYY-MM-DD.json
├── activity-details/      # get_activity + get_activity_splits, keyed by activity id
│   ├── <activity_id>.json         # from get_activity
│   └── <activity_id>.splits.json  # from get_activity_splits
├── sleep/                 # get_sleep_summary, one file per date
│   └── YYYY-MM-DD.json
├── hrv/                   # get_hrv_trend, one file per date (the day whose "5min_high" it represents)
│   └── YYYY-MM-DD.json
├── stress/                # get_stress_summary
│   └── YYYY-MM-DD.json
├── body-battery/          # get_body_battery
│   └── YYYY-MM-DD.json
├── training-readiness/    # get_training_readiness
│   └── YYYY-MM-DD.json
└── max-metrics/           # get_max_metrics (VO2max snapshots)
    └── YYYY-MM-DD.json
```

## Rules

1. **Read before fetch.** Before calling `user-garmin`, check if the file exists in the
   right subfolder.
2. **Only today's data is provisional.** Today's sleep and HRV can be re-fetched; they
   change intra-day as Garmin updates. All prior dates are immutable — trust the cache.
3. **Save the raw response.** No transformation. Store the JSON exactly as returned so
   nothing is lost.
4. **HRV trend responses are exploded per date.** `get_hrv_trend` returns an array of
   day-level entries — write one file per date in `hrv/`, not one file per range.
5. **Multi-day activity fetches are split too.** `get_activities_by_date` for a range
   should be written as one `activities/YYYY-MM-DD.json` per date the response covers.

## Metadata

Each JSON file may include a top-level `_fetched_at` ISO timestamp added by the writer.
The Garmin payload itself is stored under `data`, so files look like:

```json
{
  "_fetched_at": "2026-08-15T08:12:44+04:00",
  "data": { ...raw MCP response... }
}
```

Older files (backfilled from conversation history) may not have `_fetched_at`; treat
those as authoritative regardless.
