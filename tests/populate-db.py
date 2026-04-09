"""
Populate the TTMM database with dummy profiles for testing/demo purposes.

Usage:
    python tests/populate-db.py                  # uses default localhost:8000
    python tests/populate-db.py --base-url http://your-host:8000
"""
import httpx
import sys
import argparse
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"

PROFILES = [
    {
        "name": "Andrey",
        "level": "advanced",
        "available_time": [
            {"type": "weekly", "day": "Monday", "start_time": "18:00", "end_time": "20:00"},
            {"type": "weekly", "day": "Wednesday", "start_time": "18:00", "end_time": "20:00"},
            {"type": "weekly", "day": "Saturday", "start_time": "10:00", "end_time": "12:00"},
        ],
        "desired_place": ["Sport complex", "4th dorm"],
        "contact_info": {"telegram": "@andrey_ttmm", "phone": "+7-999-123-4567"},
        "preferences": ["singles"],
        "additional_info": "Aggressive playstyle, love fast rallies. Looking for serious practice partners!"
    },
    {
        "name": "Ivan",
        "level": "intermediate",
        "available_time": [
            {"type": "weekly", "day": "Tuesday", "start_time": "16:00", "end_time": "18:00"},
            {"type": "weekly", "day": "Thursday", "start_time": "16:00", "end_time": "18:00"},
            {"type": "weekly", "day": "Sunday", "start_time": "14:00", "end_time": "16:00"},
        ],
        "desired_place": ["Sport complex"],
        "contact_info": {"telegram": "@ivan_ttmm", "email": "ivan@example.com"},
        "preferences": ["singles", "1-2 hours"],
        "additional_info": "Playing for 2 years, good at defense. Happy to practice with anyone!"
    },
    {
        "name": "Grigoriy",
        "level": "beginner",
        "available_time": [
            {"type": "weekly", "day": "Monday", "start_time": "12:00", "end_time": "14:00"},
            {"type": "weekly", "day": "Friday", "start_time": "15:00", "end_time": "17:00"},
        ],
        "desired_place": ["4th dorm", "Popova Technopark"],
        "contact_info": {"telegram": "@grigoriy_ttmm"},
        "additional_info": "Just started playing last semester. Looking for patient partners to improve together."
    },
    {
        "name": "Maxim",
        "level": "professional",
        "available_time": [
            {"type": "weekly", "day": "Monday", "start_time": "09:00", "end_time": "11:00"},
            {"type": "weekly", "day": "Wednesday", "start_time": "09:00", "end_time": "11:00"},
            {"type": "weekly", "day": "Friday", "start_time": "09:00", "end_time": "11:00"},
        ],
        "desired_place": ["Sport complex", "Popova Technopark"],
        "contact_info": {"telegram": "@max2t2m", "phone": "+7-999-765-4321", "email": "max_ttmm@example.com"},
        "preferences": ["singles", "doubles", "2+ hours"],
        "additional_info": "Former national team player. Available for coaching and competitive practice."
    },
    {
        "name": "Dmitry",
        "level": "intermediate",
        "available_time": [
            {"type": "weekly", "day": "Tuesday", "start_time": "19:00", "end_time": "21:00"},
            {"type": "weekly", "day": "Thursday", "start_time": "19:00", "end_time": "21:00"},
            {"type": "weekly", "day": "Saturday", "start_time": "16:00", "end_time": "18:00"},
        ],
        "desired_place": ["anywhere"],
        "contact_info": {"telegram": "@dmitry_ttmm", "whatsapp": "+7-999-111-2233"},
        "additional_info": "Casual player, enjoy fun matches. Flexible on location and time!"
    },
    {
        "name": "Yuki Tanaka",
        "level": "advanced",
        "available_time": [
            {"type": "weekly", "day": "Monday", "start_time": "17:00", "end_time": "19:00"},
            {"type": "weekly", "day": "Wednesday", "start_time": "17:00", "end_time": "19:00"},
            {"type": "weekly", "day": "Friday", "start_time": "17:00", "end_time": "19:00"},
            {"type": "exact", "date": "2026-04-15", "start_time": "10:00", "end_time": "12:00"},
        ],
        "desired_place": ["Sport complex", "4th dorm"],
        "contact_info": {"telegram": "@yuki_tt", "email": "yuki@example.com"},
        "preferences": ["singles", "doubles", "1-2 hours"],
        "additional_info": "Played in Japan for 5 years, now studying here. Strong forehand, working on backhand."
    },
    # {
    #     "name": "Olga Smirnova",
    #     "level": "beginner",
    #     "available_time": [
    #         {"type": "weekly", "day": "Saturday", "start_time": "12:00", "end_time": "14:00"},
    #         {"type": "weekly", "day": "Sunday", "start_time": "12:00", "end_time": "14:00"},
    #     ],
    #     "desired_place": ["4th dorm"],
    #     "contact_info": {"telegram": "@olga_sm", "phone": "+7-999-333-4455"},
    #     "additional_info": "Never played before but really want to learn! Looking for friendly beginners to start with."
    # },
    # {
    #     "name": "Tom Bradley",
    #     "level": "intermediate",
    #     "available_time": [
    #         {"type": "weekly", "day": "Monday", "start_time": "20:00", "end_time": "22:00"},
    #         {"type": "weekly", "day": "Wednesday", "start_time": "20:00", "end_time": "22:00"},
    #         {"type": "weekly", "day": "Friday", "start_time": "20:00", "end_time": "22:00"},
    #     ],
    #     "desired_place": ["Sport complex", "Popova Technopark"],
    #     "contact_info": {"telegram": "@tom_bradley", "whatsapp": "+7-999-555-6677"},
    #     "preferences": ["singles", "1-2 hours"],
    #     "additional_info": "Evening player! Good serve game, looking for challenging matches after classes."
    # },
]


def populate(base_url: str):
    """Create profiles via the REST API."""
    print(f"🚀 Populating database at {base_url}")

    created = []
    for i, profile in enumerate(PROFILES, 1):
        try:
            resp = httpx.post(f"{base_url}/api/v1/profiles", json=profile, timeout=10)
            if resp.status_code == 201:
                data = resp.json()
                created.append(data)
                print(f"  ✅ [{i}/{len(PROFILES)}] Created: {data['name']} ({data['level']})")
            else:
                print(f"  ❌ [{i}/{len(PROFILES)}] Failed: {profile['name']} — {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"  ❌ [{i}/{len(PROFILES)}] Error: {profile['name']} — {e}")

    print(f"\n✨ Done! {len(created)}/{len(PROFILES)} profiles created.")
    if created:
        print("\n📋 Created profiles:")
        for p in created:
            print(f"   • {p['name']} — {p['level']} (ID: {p['id']})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Populate TTMM database with dummy profiles")
    parser.add_argument("--base-url", default=BASE_URL, help=f"API base URL (default: {BASE_URL})")
    args = parser.parse_args()
    populate(args.base_url)
