"""
LLM Tool definitions and execution for the TTMM agent.

Each tool has a JSON schema for the LLM and an async executor function.
"""

import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Import CRUD and models from the app package
# We'll resolve these at runtime to avoid circular imports

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_profiles",
            "description": "Search and filter player profiles. Returns profiles matching the given criteria.",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {
                        "type": "string",
                        "enum": ["beginner", "intermediate", "advanced", "professional"],
                        "description": "Filter by skill level",
                    },
                    "place": {
                        "type": "string",
                        "description": "Filter by desired place (partial match)",
                    },
                    "day": {
                        "type": "string",
                        "description": "Filter by available day",
                    },
                    "time_from": {
                        "type": "string",
                        "description": "Filter by time range start (HH:MM)",
                    },
                    "time_to": {
                        "type": "string",
                        "description": "Filter by time range end (HH:MM)",
                    },
                    "name": {
                        "type": "string",
                        "description": "Search by player name",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_profile",
            "description": "Get detailed information about a specific profile by name or ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "profile_id": {"type": "string", "description": "Profile UUID"},
                    "name": {"type": "string", "description": "Player name (if ID unknown)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_profile",
            "description": "Get the current user's profile information.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_my_profile",
            "description": "Update the current user's profile. All fields are optional.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Player name"},
                    "level": {
                        "type": "string",
                        "enum": ["beginner", "intermediate", "advanced", "professional"],
                        "description": "Skill level",
                    },
                    "places": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of desired places",
                    },
                    "available_time": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of time slots [{day, start_time, end_time}]",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_request",
            "description": "Send a match request to another player. Requires user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_name": {
                        "type": "string",
                        "description": "Name of the player to send request to",
                    },
                    "target_id": {
                        "type": "string",
                        "description": "UUID of the target player",
                    },
                },
                "required": ["target_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_requests",
            "description": "Get match requests received by or sent by the current user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["received", "sent", "all"],
                        "description": "Which requests to retrieve",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "approve_request",
            "description": "Approve a pending match request by its UUID. Use this when the request_id is known.",
            "parameters": {
                "type": "object",
                "properties": {
                    "request_id": {
                        "type": "string",
                        "description": "UUID of the match request",
                    },
                },
                "required": ["request_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "approve_request_by_name",
            "description": "Approve a pending match request from a specific player by their name. Use this when only the player name is known.",
            "parameters": {
                "type": "object",
                "properties": {
                    "player_name": {
                        "type": "string",
                        "description": "Name of the player who sent the request",
                    },
                },
                "required": ["player_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_contacts",
            "description": "Get contact info for a mutually approved match request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "request_id": {
                        "type": "string",
                        "description": "UUID of the approved match request",
                    },
                },
                "required": ["request_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stats",
            "description": "Get system statistics: total players, level distribution.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

# Tools that require explicit user confirmation before execution
CONFIRMATION_TOOLS = {"send_request", "approve_request", "approve_request_by_name"}


# ─── Tool executors ───────────────────────────────────────────────

def _get_crud():
    """Lazy import to avoid circular dependency"""
    from app import crud
    return crud


async def execute_tool(db: AsyncSession, tool_name: str, arguments: dict, user_id = None) -> str:
    """Execute a named tool with given arguments and return a human-readable result."""
    try:
        handler = _HANDLERS.get(tool_name)
        if not handler:
            return f"Unknown tool: {tool_name}"
        return await handler(db, arguments, user_id)
    except Exception as e:
        return f"Error executing {tool_name}: {str(e)}"


async def _search_profiles(db, args, user_id):
    crud = _get_crud()
    profiles = await crud.get_all_profiles(db)
    results = []

    for p in profiles:
        if args.get("level") and p.level != args["level"]:
            continue
        if args.get("place"):
            places = p.desired_place if isinstance(p.desired_place, list) else []
            if not any(args["place"].lower() in pl.lower() for pl in places):
                continue
        if args.get("name"):
            if args["name"].lower() not in p.name.lower():
                continue
        if args.get("day") or args.get("time_from") or args.get("time_to"):
            slots = p.available_time or []
            matched = False
            for slot in slots:
                slot_day = (slot.get("day") or "").lower() if isinstance(slot, dict) else ""
                slot_end = slot.get("end_time", "") if isinstance(slot, dict) else ""
                slot_start = slot.get("start_time", "") if isinstance(slot, dict) else ""
                if args.get("day") and slot_day != args["day"].lower():
                    continue
                if args.get("time_from") and slot_end < args["time_from"]:
                    continue
                if args.get("time_to") and slot_start > args["time_to"]:
                    continue
                if args.get("day") or args.get("time_from") or args.get("time_to"):
                    matched = True
            if args.get("day") or args.get("time_from") or args.get("time_to"):
                if not matched:
                    continue

        results.append({
            "id": str(p.id),
            "name": p.name,
            "level": p.level,
            "places": p.desired_place if isinstance(p.desired_place, list) else [],
            "available_time": p.available_time or [],
        })

    if not results:
        return "No players found matching your criteria."

    lines = [f"Found {len(results)} player(s):\n"]
    for r in results:
        lines.append(f"• **{r['name']}** ({r['level']})")
        if r["places"]:
            lines.append(f"  Places: {', '.join(r['places'])}")
        if r["available_time"]:
            times = [f"{s.get('day') or ''} {s.get('start_time', '')}-{s.get('end_time', '')}" for s in r["available_time"]]
            lines.append(f"  Times: {', '.join(times)}")
        lines.append("")

    return "\n".join(lines)


async def _get_profile(db, args, user_id):
    crud = _get_crud()
    if args.get("profile_id"):
        import uuid as _uuid
        try:
            pid = _uuid.UUID(args["profile_id"])
        except ValueError:
            return f"Invalid profile ID: {args['profile_id']}"
        profile = await crud.get_profile(db, pid)
    elif args.get("name"):
        all_profiles = await crud.get_all_profiles(db)
        profile = next((p for p in all_profiles if p.name.lower() == args["name"].lower()), None)
    else:
        return "Please provide either profile_id or name."

    if not profile:
        return "Profile not found."

    info = [
        f"**{profile.name}**",
        f"Level: {profile.level}",
        f"Places: {', '.join(profile.desired_place) if isinstance(profile.desired_place, list) and profile.desired_place else 'Not set'}",
    ]
    if profile.available_time:
        times = [f"{s['day']} {s['start_time']}-{s['end_time']}" for s in profile.available_time]
        info.append(f"Available: {', '.join(times)}")
    if profile.additional_info:
        for k, v in profile.additional_info.items():
            info.append(f"{k}: {v}")

    return "\n".join(info)


async def _get_my_profile(db, args, user_id):
    if not user_id:
        return "You need to be logged in to view your profile."
    crud = _get_crud()
    profile = await crud.get_profile(db, user_id)
    if not profile:
        return "No profile found. Create one first!"

    import uuid as _uuid
    return await _get_profile(db, {"profile_id": str(profile.id)}, user_id)


async def _update_my_profile(db, args, user_id):
    if not user_id:
        return "You need to be logged in to update your profile."

    updates = {}
    if args.get("name"):
        updates["name"] = args["name"]
    if args.get("level"):
        updates["level"] = args["level"]
    if args.get("places") is not None:
        updates["desired_place"] = args["places"]
    if args.get("available_time") is not None:
        updates["available_time"] = args["available_time"]

    if not updates:
        return "No valid fields to update. Available: name, level, places, available_time."

    crud = _get_crud()
    profile = await crud.update_profile(db, user_id, updates)
    if not profile:
        return "Failed to update profile."

    return f"Profile updated!\n• Name: {profile.name}\n• Level: {profile.level}"


async def _send_request(db, args, user_id):
    if not user_id:
        return "You need to be logged in to send requests."

    target_name = args.get("target_name", "")
    target_id = args.get("target_id")

    crud = _get_crud()
    if target_id:
        import uuid as _uuid
        try:
            tid = _uuid.UUID(target_id)
        except ValueError:
            return f"Invalid target ID: {target_id}"
        target = await crud.get_profile(db, tid)
    elif target_name:
        all_profiles = await crud.get_all_profiles(db)
        target = next((p for p in all_profiles if p.name.lower() == target_name.lower()), None)
    else:
        return "Please provide a player name or ID."

    if not target:
        return f"Player '{target_name}' not found."
    if target.id == user_id:
        return "You can't send a request to yourself!"

    existing = await crud.get_match_request(db, user_id, target.id)
    if existing:
        return f"You already have a request for {target.name} (status: {existing.status})."

    request = await crud.create_match_request(db, user_id, target.id)
    if not request:
        return "Failed to send request."

    return f"Match request sent to **{target.name}**! They can approve or decline it."


async def _get_my_requests(db, args, user_id):
    if not user_id:
        return "You need to be logged in to view requests."

    crud = _get_crud()
    direction = args.get("direction", "all")
    lines = []

    if direction in ["received", "all"]:
        received = await crud.get_user_received_requests(db, user_id)
        if received:
            lines.append("## Received Requests")
            for r in received:
                sender = await crud.get_profile(db, r.sender_id)
                sender_name = sender.name if sender else "Unknown"
                lines.append(f"• From **{sender_name}**: {r.status}")

    if direction in ["sent", "all"]:
        sent = await crud.get_user_sent_requests(db, user_id)
        if sent:
            lines.append("\n## Sent Requests")
            for r in sent:
                receiver = await crud.get_profile(db, r.receiver_id)
                receiver_name = receiver.name if receiver else "Unknown"
                lines.append(f"• To **{receiver_name}**: {r.status}")

    if not lines:
        return "No match requests found."

    return "\n".join(lines)


async def _approve_request(db, args, user_id):
    if not user_id:
        return "You need to be logged in to approve requests."

    import uuid as _uuid
    crud = _get_crud()

    # Support both request_id and player_name
    request_id = args.get("request_id")
    player_name = args.get("player_name")

    if request_id:
        try:
            rid = _uuid.UUID(request_id)
        except ValueError:
            return f"Invalid request ID: {request_id}"
        request = await crud.get_match_request_by_id(db, rid)
    elif player_name:
        # Find pending request from this player
        received = await crud.get_user_received_requests(db, user_id)
        request = None
        for req in received:
            if req.status == "pending":
                sender = await crud.get_profile(db, req.sender_id)
                if sender and player_name.lower() in sender.name.lower():
                    request = req
                    player_name = sender.name  # Use actual name for display
                    break
        if not request:
            return f"No pending request found from {player_name}."
        rid = request.id
    else:
        return "Please provide either request_id or player_name."

    if not request:
        return "Request not found."
    if request.receiver_id != user_id and request.sender_id != user_id:
        return "This request doesn't belong to you."
    if request.status != "pending":
        return f"This request is already {request.status}."

    updated = await crud.respond_to_match_request(db, rid, user_id, True)
    if not updated:
        return "Failed to approve request."

    other_id = request.sender_id if user_id == request.receiver_id else request.receiver_id
    player = await crud.get_profile(db, other_id)
    other_name = player.name if player else "Unknown"

    if updated.status == "approved":
        return f"Request approved! You and **{other_name}** can now see each other's contacts."
    return f"Request acknowledged. Status: {updated.status}"


async def _get_contacts(db, args, user_id):
    if not user_id:
        return "You need to be logged in to view contacts."

    import uuid as _uuid
    try:
        rid = _uuid.UUID(args["request_id"])
    except ValueError:
        return f"Invalid request ID: {args['request_id']}"

    crud = _get_crud()
    request = await crud.get_match_request_by_id(db, rid)
    if not request:
        return "Request not found."
    if request.sender_id != user_id and request.receiver_id != user_id:
        return "This request doesn't belong to you."
    if not crud.is_mutually_approved(request):
        return "Contacts are not available yet — both players must approve the match request first."

    sender = await crud.get_profile(db, request.sender_id)
    receiver = await crud.get_profile(db, request.receiver_id)

    lines = ["**Contact info for approved match:**"]
    if sender:
        lines.append(f"\n📱 {sender.name}:")
        if sender.contact_info:
            for k, v in sender.contact_info.items():
                lines.append(f"  • {k}: {v}")
        else:
            lines.append("  No contacts provided")
    if receiver:
        lines.append(f"\n📱 {receiver.name}:")
        if receiver.contact_info:
            for k, v in receiver.contact_info.items():
                lines.append(f"  • {k}: {v}")
        else:
            lines.append("  No contacts provided")

    return "\n".join(lines)


async def _get_stats(db, args, user_id):
    crud = _get_crud()
    profiles = await crud.get_all_profiles(db)
    total = len(profiles)

    if total == 0:
        return "No players registered yet."

    levels = {}
    for p in profiles:
        levels[p.level] = levels.get(p.level, 0) + 1

    lines = [f"**TTMM Statistics:**", f"Total players: {total}\n"]
    for level, count in sorted(levels.items()):
        lines.append(f"• {level}: {count}")

    return "\n".join(lines)


_HANDLER_MAP = {
    "search_profiles": _search_profiles,
    "get_profile": _get_profile,
    "get_my_profile": _get_my_profile,
    "update_my_profile": _update_my_profile,
    "send_request": _send_request,
    "get_my_requests": _get_my_requests,
    "approve_request": _approve_request,
    "approve_request_by_name": _approve_request,
    "get_contacts": _get_contacts,
    "get_stats": _get_stats,
}

_HANDLERS = _HANDLER_MAP
