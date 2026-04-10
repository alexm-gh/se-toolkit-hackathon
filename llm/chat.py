"""
LLM-powered chat endpoint for the TTMM agent.

Uses OpenAI-compatible API with tool calling.
Falls back to the rule-based parser if no LLM key is set.
Also handles LLMs that output raw function call patterns in text.
"""

import json
import os
import re
import uuid
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from llm import tools, prompt

# Load .env file from project root
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_project_root, ".env"), override=True)

# ─── LLM Configuration ────────────────────────────────────────────
LLM_API_KEY = os.getenv("LLM_API_KEY", "not-needed")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:42005/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3-coder-flash")
USE_LLM = os.getenv("USE_LLM", "false").lower() in ("true", "1", "yes")

_openai_client = None


def get_openai_client():
    global _openai_client
    if _openai_client is None and USE_LLM:
        from openai import AsyncOpenAI
        _openai_client = AsyncOpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
        )
    return _openai_client


async def moderate_content(text: str) -> tuple[bool, str]:
    """Check if content is appropriate. Returns (is_safe, reason_if_not)."""
    if not USE_LLM or not text or not text.strip():
        return True, ""

    client = get_openai_client()
    if not client:
        return True, ""

    try:
        response = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": """You are a content moderator for a university table tennis matchmaking app.
Check the user's profile text for:
- Profanity or vulgar language
- Threats, harassment, or hate speech
- Spam, gibberish, or completely irrelevant content

If the content is inappropriate, respond with: REJECT: <brief reason>
If the content is fine, respond with: APPROVE""",
                },
                {"role": "user", "content": f"Moderate this profile text:\n\n{text}"},
            ],
            temperature=0.1,
            max_tokens=100,
        )
        result = response.choices[0].message.content.strip()
        if result.upper().startswith("REJECT"):
            reason = result.split(":", 1)[1].strip() if ":" in result else "Inappropriate content detected"
            return False, reason
        return True, ""
    except Exception as e:
        print(f"Content moderation error: {e}")
        return True, ""


# Regex to parse raw function calls from LLM text output
# Matches patterns like: <send_request> key1: value1, key2: value2
def parse_function_calls(text: str) -> list[dict]:
    """Parse raw function calls from LLM text. Handles multiple formats."""
    calls = []
    
    # Format 2: <function=NAME><parameter=KEY>VALUE
    f2_tag = re.compile(r'<function=(\w+)>(.*?)(?=<function=|</function>|\Z)', re.DOTALL)
    f2_param = re.compile(r'<parameter=(\w+)>([^<\n]+)')
    for fm in f2_tag.finditer(text):
        fn = fm.group(1)
        if fn in tools.CONFIRMATION_TOOLS:
            params = {}
            for pm in f2_param.finditer(fm.group(2)):
                k, v = pm.group(1), pm.group(2).strip()
                if v: params[k] = v
            if params:
                calls.append({"tool": fn, **params})
    
    # Format 1: <name> key: value
    f1_tag = re.compile(r'<(\w+)>\s*(.*?)\s*(?=</\1>|\Z)', re.DOTALL)
    f1_param = re.compile(r'(\w+)\s*[:=]\s*([^,}\n]+)')
    for fm in f1_tag.finditer(text):
        fn = fm.group(1)
        if fn in tools.CONFIRMATION_TOOLS:
            params = {}
            for pm in f1_param.finditer(fm.group(2)):
                k = pm.group(1)
                v = pm.group(2).strip().strip(chr(34)).strip(chr(39))
                params[k] = v
            if params and not any(c.get('tool') == fn for c in calls):
                calls.append({"tool": fn, **params})
    
    return calls

class ChatMessage(BaseModel):
    message: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    text: str
    requires_confirmation: bool = False
    action: Optional[dict] = None


# ─── Conversation memory ─────────────────────────────────────────
conversations: dict[str, list] = {}


# ─── Rule-based fallback ─────────────────────────────────────────
async def _rule_based(msg: str, db: AsyncSession, user_id):
    """Minimal rule-based parser as LLM fallback."""
    msg_lower = msg.lower().strip()

    if any(w in msg_lower for w in ["hi", "hello", "hey", "greetings"]):
        if user_id:
            from app import crud
            profile = await crud.get_profile(db, user_id)
            name = profile.name if profile else "there"
            return {"text": f"Hey {name}! 👋 How can I help you today?"}
        return {"text": "Hey! 👋 How can I help you? Type 'help' for commands."}

    if any(w in msg_lower for w in ["help", "what can you do", "commands"]):
        return {"text": """I can help with:
🔍 **Search** — "find intermediate players"
👤 **Profiles** — "show Alice's profile"
✏️ **Update** — "change my level to advanced"
📩 **Requests** — "send request to Alice"
📋 **My requests** — "show my requests"
✅ **Approve** — "approve request from Bob"
📞 **Contacts** — "show contacts for Alice"
📊 **Stats** — "show statistics"
Type any natural language request!"""}

    if any(w in msg_lower for w in ["stats", "statistics", "how many"]):
        result = await tools.execute_tool(db, "get_stats", {}, user_id)
        return {"text": result}

    if any(w in msg_lower for w in ["find", "search", "who", "list players"]):
        args = {}
        for level in ["beginner", "intermediate", "advanced", "professional"]:
            if level in msg_lower:
                args["level"] = level
                break
        for place in ["dorm", "sport", "technopark", "popova"]:
            if place in msg_lower:
                args["place"] = place
                break
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            if day in msg_lower:
                args["day"] = day.capitalize()
                break
        result = await tools.execute_tool(db, "search_profiles", args, user_id)
        return {"text": result}

    if any(w in msg_lower for w in ["show my profile", "my profile", "my info"]):
        result = await tools.execute_tool(db, "get_my_profile", {}, user_id)
        return {"text": result}

    if any(w in msg_lower for w in ["update my", "change my", "set my", "edit my"]):
        updates = {}
        for level in ["beginner", "intermediate", "advanced", "professional"]:
            if f"level to {level}" in msg_lower:
                updates["level"] = level
        if "place" in msg_lower or "places" in msg_lower:
            for kw in ["places to ", "place to "]:
                idx = msg_lower.find(kw)
                if idx >= 0:
                    places_str = msg[idx + len(kw):].split(" and ")
                    updates["places"] = [p.strip().strip("?.!,;").strip() for p in places_str]
                    break
        if updates:
            result = await tools.execute_tool(db, "update_my_profile", updates, user_id)
            return {"text": result}
        return {"text": "Try: 'change my level to advanced' or 'set my places to 4th dorm'."}

    if any(w in msg_lower for w in ["send request", "request to", "play with", "match with"]):
        for prep in ["to ", "with "]:
            idx = msg_lower.find(prep)
            if idx >= 0:
                target = msg[idx + len(prep):].split()[0].strip("?.!,;").capitalize()
                if target:
                    return {
                        "text": f"I'll send a match request to **{target}**. Confirm?",
                        "requires_confirmation": True,
                        "action": {"tool": "send_request", "target_name": target},
                    }

    if any(w in msg_lower for w in ["my requests", "show requests", "pending requests"]):
        direction = "all"
        if "received" in msg_lower:
            direction = "received"
        elif "sent" in msg_lower:
            direction = "sent"
        result = await tools.execute_tool(db, "get_my_requests", {"direction": direction}, user_id)
        return {"text": result}

    if any(w in msg_lower for w in ["approve", "accept request"]):
        for prep in ["from ", "by "]:
            idx = msg_lower.find(prep)
            if idx >= 0:
                name = msg[idx + len(prep):].split()[0].strip("?.!,;").capitalize()
                if name and user_id:
                    from app import crud
                    received = await crud.get_user_received_requests(db, user_id)
                    for req in received:
                        if req.status == "pending":
                            sender = await crud.get_profile(db, req.sender_id)
                            if sender and name.lower() in sender.name.lower():
                                return {
                                    "text": f"Found pending request from **{sender.name}**. Approve?",
                                    "requires_confirmation": True,
                                    "action": {"tool": "approve_request_by_name", "player_name": sender.name},
                                }

    if any(w in msg_lower for w in ["contacts", "contact info"]):
        for prep in ["for "]:
            idx = msg_lower.find(prep)
            if idx >= 0:
                name = msg[idx + len(prep):].split()[0].strip("?.!,;").capitalize()
                if name and user_id:
                    from app import crud
                    received = await crud.get_user_received_requests(db, user_id)
                    sent = await crud.get_user_sent_requests(db, user_id)
                    for r in received + sent:
                        other_id = r.receiver_id if r.sender_id == user_id else r.sender_id
                        other = await crud.get_profile(db, other_id)
                        if other and name.lower() in other.name.lower():
                            if r.status == "approved":
                                result = await tools.execute_tool(db, "get_contacts", {"request_id": str(r.id)}, user_id)
                                return {"text": result}
                            return {"text": f"Match with {other.name} is not approved yet (status: {r.status})."}

    return {"text": "I didn't quite understand. Try: 'find intermediate players', 'send request to [name]', 'show my requests', or type 'help'."}


# ─── LLM-powered chat ─────────────────────────────────────────────
async def process_message_llm(message: str, db: AsyncSession, user_id = None, session_id: str = None) -> dict:
    if not USE_LLM:
        return await _rule_based(message, db, user_id)

    client = get_openai_client()
    if not client:
        return {"text": "LLM is not configured. Set LLM_API_KEY to enable AI agent."}

    sid = session_id or "default"
    if sid not in conversations:
        conversations[sid] = []

    # Build user context
    user_context = ""
    if user_id:
        from app import crud
        profile = await crud.get_profile(db, user_id)
        if profile:
            user_context = f"Current user: {profile.name} (ID: {profile.id}), level: {profile.level}"

    system_msg = {"role": "system", "content": prompt.build_system_prompt(user_context)}
    conversations[sid].append({"role": "user", "content": message})

    messages = [system_msg] + conversations[sid][-20:]

    try:
        response = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            tools=tools.TOOLS,
            tool_choice="auto",
            temperature=0.7,
            max_tokens=4096,
        )

        choice = response.choices[0]
        assistant_msg = choice.message

        # Check if the model wants to call tools via OpenAI's tool_calls field
        if assistant_msg.tool_calls:
            tool_results = []
            requires_confirmation = False
            confirmation_action = None

            for tc in assistant_msg.tool_calls:
                func_name = tc.function.name
                func_args = json.loads(tc.function.arguments)

                if func_name in tools.CONFIRMATION_TOOLS:
                    requires_confirmation = True
                    confirmation_action = {"tool": func_name, **{k: v for k, v in func_args.items() if v}}
                    break

                result = await tools.execute_tool(db, func_name, func_args, user_id)
                tool_results.append({
                    "tool_call_id": tc.id,
                    "role": "tool",
                    "name": func_name,
                    "content": result,
                })

            if requires_confirmation:
                confirmation_text = assistant_msg.content or ""
                if not confirmation_text:
                    if confirmation_action["tool"] == "send_request":
                        target = confirmation_action.get("target_name", "this player")
                        confirmation_text = f"I'll send a match request to **{target}**. Both of you need to approve before contacts are shared. Confirm?"
                    elif confirmation_action["tool"] in ("approve_request", "approve_request_by_name"):
                        player = confirmation_action.get("player_name", confirmation_action.get("from_player", "this request"))
                        confirmation_text = f"I'll approve the request from **{player}**. Confirm?"

                conversations[sid].append({"role": "assistant", "content": confirmation_text})
                return {
                    "text": confirmation_text,
                    "requires_confirmation": True,
                    "action": confirmation_action,
                }

            if tool_results:
                conversations[sid].append({
                    "role": "assistant",
                    "content": assistant_msg.content or "",
                    "tool_calls": [tc.model_dump() for tc in assistant_msg.tool_calls],
                })
                for tr in tool_results:
                    conversations[sid].append(tr)

                messages2 = [system_msg] + conversations[sid][-20:]
                response2 = await client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=messages2,
                    temperature=0.7,
                    max_tokens=4096,
                )

                final_text = response2.choices[0].message.content or ""
                conversations[sid].append({"role": "assistant", "content": final_text})
                return {"text": final_text}

            # Tool calls existed but none executed (all were confirmation-type that got skipped somehow)
            # This shouldn't happen, but handle gracefully
            response_text = assistant_msg.content or "Tool call acknowledged."
            conversations[sid].append({"role": "assistant", "content": response_text})
            return {"text": response_text}

        # No tool calls via OpenAI API — check for raw function call patterns in text
        response_text = assistant_msg.content or ""
        raw_calls = parse_function_calls(response_text)
        
        if raw_calls:
              # Execute non-confirmation tools immediately, show confirmation for others
              executed_results = []
              confirmation_call = None
              
              for call in raw_calls:
                  if call["tool"] in tools.CONFIRMATION_TOOLS:
                      confirmation_call = call
                  else:
                      # Execute immediately for non-confirmation tools
                      exec_args = {k: v for k, v in call.items() if k != "tool"}
                      result = await tools.execute_tool(db, call["tool"], exec_args, user_id)
                      executed_results.append({"tool": call["tool"], "result": result})
              
              if confirmation_call:
                  # Show confirmation bar for confirmation-required tools
                  if confirmation_call["tool"] == "send_request":
                      target = confirmation_call.get("target_name", "this player")
                      clean_text = f"I'll send a match request to **{target}**. Both of you need to approve before contacts are shared. Confirm?"
                  elif confirmation_call["tool"] == "approve_request_by_name":
                      player = confirmation_call.get("player_name", "this player")
                      clean_text = f"I'll approve the request from **{player}**. Confirm?"
                  else:
                      clean_text = "Please confirm this action."
                  
                  conversations[sid].append({"role": "assistant", "content": clean_text})
                  return {
                      "text": clean_text,
                      "requires_confirmation": True,
                      "action": confirmation_call,
                  }
              
              # No confirmation needed - return executed results
              if executed_results:
                  # Combine all results into a natural response
                  result_texts = []
                  for er in executed_results:
                      result_texts.append(er["result"])
                  combined = "\n\n".join(result_texts)
                  conversations[sid].append({"role": "assistant", "content": combined})
                  return {"text": combined}
        
        
        conversations[sid].append({"role": "assistant", "content": response_text})
        return {"text": response_text}

    except Exception as e:
        print(f"LLM error: {e}")
        return await _rule_based(message, db, user_id)


# ─── Routes ───────────────────────────────────────────────────────
router = APIRouter(prefix="/api/v1", tags=["agent"])


@router.post("/moderate")
async def moderate_endpoint(data: dict):
    """Content moderation endpoint — called by the main app."""
    text = data.get("text", "")
    is_safe, reason = await moderate_content(text)
    return {"is_safe": is_safe, "reason": reason}


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(data: ChatMessage, db: AsyncSession = Depends(get_db)):
    """Send a message to the TTMM agent (LLM-powered, with rule-based fallback)."""
    user_id = None
    if data.user_id:
        try:
            user_id = uuid.UUID(data.user_id)
        except ValueError:
            pass

    result = await process_message_llm(data.message, db, user_id, data.session_id)
    return ChatResponse(
        text=result.get("text", ""),
        requires_confirmation=result.get("requires_confirmation", False),
        action=result.get("action"),
    )


@router.get("/chat/status")
async def chat_status():
    """Check if LLM is configured and reachable."""
    status = {
        "llm_enabled": USE_LLM,
        "base_url": LLM_BASE_URL if USE_LLM else None,
        "model": LLM_MODEL if USE_LLM else None,
        "fallback": "rule-based" if not USE_LLM else None,
    }

    if USE_LLM:
        client = get_openai_client()
        if client:
            try:
                import asyncio
                async def _check():
                    models = await client.models.list()
                    return True
                status["reachable"] = True
            except Exception as e:
                status["reachable"] = False
                status["error"] = str(e)

    return status
