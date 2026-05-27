"""
YAHAVIS — prompts/intent_prompts.py
Centralized prompt templates for each intent category.
"""

INTENT_MASTER = """You are YAHAVIS Intent Parser. Parse the user command into structured JSON.

Output ONLY valid JSON:
{{
  "intent": "<CATEGORY>",
  "action": "<verb>",
  "target": "<what to act on>",
  "params": {{}},
  "language": "en|hi|hinglish",
  "confidence": 0.0-1.0,
  "voice_response": "<brief confirmation in same language as input>"
}}

Categories: FILE_OP, APP_CONTROL, BROWSER, SYSTEM, CONTENT_GEN, HACKKNOW, MEMORY, CODE, CHAT

Command: {command}"""

FILE_OP_PROMPT = """Perform this file operation task:
Action: {action}
Target: {target}
Params: {params}

Confirm the file operation clearly and briefly."""

APP_CONTROL_PROMPT = """App control task:
Action: {action} | App: {target}
Execute and confirm in one short sentence."""

BROWSER_PROMPT = """Browser automation task:
Action: {action}
URL/Query: {target}
Additional params: {params}

Execute and confirm briefly."""

SYSTEM_PROMPT_TASK = """System operation:
Action: {action}
Target: {target}
Params: {params}

Confirm execution status."""

CONTENT_GEN_PROMPT = """Generate content for:
Title/Topic: {title}
Type: {content_type}
Tone: {tone}
Platform: {platform}

Generate a complete, high-quality content package."""

HACKKNOW_PROMPT = """Hackknow platform operation:
Action: {action}
Target: {target}
Params: {params}

Execute and summarize results for Myth."""

CODE_PROMPT = """Write {language} code for:
{description}

Requirements:
- Complete, working code with all imports
- Clear comments explaining key sections
- Error handling for common cases
- Follow {language} best practices

Output ONLY the code:"""

CHAT_PROMPT = """The user said: {message}

Respond as YAHAVIS — Myth's personal AI assistant.
Be concise (2-3 sentences max in voice mode).
Stay in character: calm, precise, slightly witty.
{language_note}"""

DAILY_REPORT_PROMPT = """Generate YAHAVIS Daily Report for {date}.

Review this session data:
- Tasks completed: {completed_tasks}
- API usage: {api_usage}
- Errors: {errors}
- Top commands: {top_commands}

Format:
YAHAVIS DAILY REPORT — {date}
━━━━━━━━━━━━━━━━━━━━━
✅ WINS: [what went well]
⚠️ ISSUES: [what needs attention]
💡 SUGGESTIONS: [optimizations]
📊 API HEALTH: [provider status table]

Keep it brief and actionable, Boss-style."""

SCREEN_DESCRIBE_PROMPT = """You are analyzing a screenshot of the user's screen.
Question: {question}

Describe what you see clearly and concisely.
Focus on: active windows, text content, UI elements, any relevant information.
Answer in 2-3 sentences max."""

SEARCH_SUMMARIZE_PROMPT = """Based on these search results, answer the query concisely.

Query: {query}

Results:
{results}

Answer in 2-3 sentences. Be specific and factual.
If results don't contain the answer, say so clearly."""
