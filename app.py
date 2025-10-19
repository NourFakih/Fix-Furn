import os
from pathlib import Path

import gradio as gr
from dotenv import load_dotenv
import google.generativeai as genai
from google.generativeai import types
from google.protobuf.json_format import MessageToDict
from google.protobuf.struct_pb2 import ListValue as ProtoListValue, Struct as ProtoStruct, Value as ProtoValue

from tools import (
    estimate_repair,
    lookup_product,
    record_customer_interest,
    record_feedback,
    record_service_feedback,
)

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set. Create a .env file based on .env.example.")

genai.configure(api_key=API_KEY)

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
SYSTEM_PROMPT = Path("me/system_prompt.txt").read_text(encoding="utf-8")
SUMMARY = Path("me/business_summary.txt").read_text(encoding="utf-8")

FUNCTION_DECLARATIONS = [
    {
        "name": "lookup_product",
        "description": (
            "Search the Fix&Furn curated catalog and IKEA Saudi Arabia reference dataset. "
            "Return relevant catalog_match/catalog_results and ikea_results including item_id, name, "
            "category, price_sar, dimensions_cm, availability, and link when available."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keyword, color, category, SKU, or IKEA item ID to search for.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "estimate_repair",
        "description": "Estimate repair price and turnaround tiers based on issue, material, and size_category.",
        "parameters": {
            "type": "object",
            "properties": {
                "issue": {
                    "type": "string",
                    "description": "Issue such as scratch, broken_glass, wobble, loose_joint, hinge_alignment, drawer_stick, upholstery_tear, refinish, repaint.",
                },
                "material": {
                    "type": "string",
                    "description": "Primary material (wood, glass, metal, fabric, or any).",
                },
                "size_category": {
                    "type": "string",
                    "description": "Furniture size bucket: small, medium, or large.",
                },
            },
            "required": ["issue"],
        },
    },
    {
        "name": "record_customer_interest",
        "description": "Capture customer details when they are ready to buy or book a repair.",
        "parameters": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "Customer email address."},
                "name": {"type": "string", "description": "Customer full name."},
                "message": {"type": "string", "description": "Short note about the product or repair request."},
            },
            "required": ["email", "name", "message"],
        },
    },
    {
        "name": "record_feedback",
        "description": "Log customer questions that the assistant could not resolve.",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Unanswered or unclear customer request."}
            },
            "required": ["question"],
        },
    },
    {
        "name": "record_service_feedback",
        "description": "Capture post-service feedback about the overall experience, product satisfaction, or repair quality.",
        "parameters": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "Customer email to match the service record."},
                "name": {"type": "string", "description": "Customer full name."},
                "service_type": {
                    "type": "string",
                    "description": "What we delivered (e.g., purchase, repair, delivery, install).",
                },
                "satisfaction": {
                    "type": "string",
                    "description": "Quick sentiment summary (e.g., happy, neutral, unhappy, 1-5).",
                },
                "comments": {
                    "type": "string",
                    "description": "Optional free-text feedback on the experience.",
                },
            },
            "required": ["email", "name", "service_type", "satisfaction"],
        },
    },
]

MODEL = genai.GenerativeModel(
    model_name=MODEL_NAME,
    system_instruction=f"{SYSTEM_PROMPT}\n\n{SUMMARY}",
    tools=[{"function_declarations": FUNCTION_DECLARATIONS}],
)

GENERATION_CONFIG = types.GenerationConfig(temperature=0.2)
TOOL_CONFIG = {"function_calling_config": {"mode": "AUTO"}}


def _content(role: str, text: str):
    if not text:
        return None
    return {"role": role, "parts": [{"text": text}]}


def _convert_history(history):
    converted = []
    for user, assistant in history:
        if user:
            converted.append(_content("user", user))
        if assistant:
            converted.append(_content("model", assistant))
    return [msg for msg in converted if msg is not None]


def _call_tool(name: str, args: dict):
    try:
        if name == "lookup_product":
            return lookup_product(**args)
        if name == "estimate_repair":
            return estimate_repair(**args)
        if name == "record_customer_interest":
            return record_customer_interest(**args)
        if name == "record_feedback":
            return record_feedback(**args)
        if name == "record_service_feedback":
            return record_service_feedback(**args)
        return {"ok": False, "msg": f"Unknown tool '{name}'."}
    except TypeError as exc:
        return {"ok": False, "msg": f"Invalid arguments for {name}: {exc}"}


def _first_function_call(response):
    for candidate in response.candidates or []:
        if not candidate or not candidate.content:
            continue
        for part in candidate.content.parts:
            if part.function_call:
                return part.function_call
    return None


def _proto_to_python(value):
    if value is None:
        return None
    if isinstance(value, ProtoValue):
        kind = value.WhichOneof("kind")
        if kind == "struct_value":
            return {k: _proto_to_python(v) for k, v in value.struct_value.fields.items()}
        if kind == "list_value":
            return [_proto_to_python(v) for v in value.list_value.values]
        if kind == "string_value":
            return value.string_value
        if kind == "number_value":
            return value.number_value
        if kind == "bool_value":
            return value.bool_value
        if kind == "null_value":
            return None
        return MessageToDict(value, preserving_proto_field_name=True)
    if isinstance(value, ProtoStruct):
        return {k: _proto_to_python(v) for k, v in value.fields.items()}
    if isinstance(value, ProtoListValue):
        return [_proto_to_python(v) for v in value.values]
    if isinstance(value, dict):
        return {k: _proto_to_python(v) for k, v in value.items()}
    if hasattr(value, "items"):
        return {k: _proto_to_python(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_proto_to_python(v) for v in value]
    return value


def _function_args_to_dict(function_call):
    args = getattr(function_call, "args", None)
    if args is None:
        return {}
    if isinstance(args, dict):
        return {k: _proto_to_python(v) for k, v in args.items()}
    if hasattr(args, "_pb"):
        try:
            return _proto_to_python(args._pb)
        except Exception:
            pass
    if hasattr(args, "ListFields"):
        try:
            return _proto_to_python(args)
        except Exception:
            pass
    if hasattr(args, "items"):
        return {k: _proto_to_python(v) for k, v in args.items()}
    converted = _proto_to_python(args)
    return converted if isinstance(converted, dict) else {}


def _send_function_response(chat, name: str, payload: dict):
    message = {
        "role": "tool",
        "parts": [
            {
                "function_response": {
                    "name": name,
                    "response": payload,
                }
            }
        ],
    }
    return chat.send_message(message, generation_config=GENERATION_CONFIG, tool_config=TOOL_CONFIG)


def chat_fn(message, history):
    history_msgs = _convert_history(history)
    chat = MODEL.start_chat(history=history_msgs)
    response = chat.send_message(
        message,
        generation_config=GENERATION_CONFIG,
        tool_config=TOOL_CONFIG,
    )

    while True:
        function_call = _first_function_call(response)
        if not function_call:
            break

        args = _function_args_to_dict(function_call)
        tool_result = _call_tool(function_call.name, args)
        response = _send_function_response(chat, function_call.name, tool_result)

    text = response.text or ""
    return text.strip()


TITLE = "Fix&Furn Mini - Furniture Sales & Repair Concierge"
demo = gr.ChatInterface(chat_fn, title=TITLE)

if __name__ == "__main__":
    demo.launch()
