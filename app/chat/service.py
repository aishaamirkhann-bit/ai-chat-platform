"""
chat/service.py — LLM Integration + Streaming + Caching

Yahan sab kuch hota hai:
1. OpenAI / Anthropic call
2. Streaming responses
3. Cache check (pehle cache, phir LLM)
4. Conversation history manage karna
5. Token count track karna

STREAMING — Interview mein yeh zaroor samjhao:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Normal Response:
  Client request bhejta hai → 5 second wait → poora jawab milta hai
  User dekhta hai: cursor ghoomta raha, phir ek dum text aa gaya

Streaming Response:
  Client request bhejta hai → 0.1 sec mein pehla word
  → 0.2 sec mein doosra word → ... → ChatGPT jaisa feel!

Technical implementation:
  Server-Sent Events (SSE) use karte hain
  Content-Type: text/event-stream
  Har chunk aaya → client ko bheja
  AsyncGenerator → yield karta rehta hai
"""

import logging
from typing import AsyncGenerator

import openai
import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.service import cache_service
from app.chat.models import Conversation, Message
from app.config import settings

logger = logging.getLogger(__name__)


# ─── LLM Clients ──────────────────────────────────────────────────────────────
openai_client    = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)


# ─── Chat Service ─────────────────────────────────────────────────────────────
class ChatService:

    # ── History Management ────────────────────────────────────────────────────
    async def get_conversation_history(
        self,
        conversation_id: int,
        db: AsyncSession,
        limit: int = 10,
    ) -> list[dict]:
        """
        DB se purani messages load karo
        LLM ko context dene ke liye zaroori hai

        limit=10 kyun?
        Zyada history → zyada tokens → zyada cost
        Last 10 messages enough hain context ke liye
        """
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = result.scalars().all()
        messages.reverse()  # Chronological order mein karo

        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

    async def save_messages(
        self,
        conversation_id: int,
        user_message: str,
        assistant_message: str,
        tokens_used: int,
        model: str,
        db: AsyncSession,
    ):
        """User aur Assistant dono messages DB mein save karo"""
        user_msg = Message(
            conversation_id=conversation_id,
            role="user",
            content=user_message,
        )
        assistant_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_message,
            tokens_used=tokens_used,
            model_used=model,
        )
        db.add_all([user_msg, assistant_msg])
        await db.commit()

    # ── Conversation CRUD ─────────────────────────────────────────────────────
    async def create_conversation(
        self,
        user_id: int,
        title: str,
        model: str,
        db: AsyncSession,
    ) -> Conversation:
        conv = Conversation(user_id=user_id, title=title, model_used=model)
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        return conv

    async def get_user_conversations(
        self, user_id: int, db: AsyncSession
    ) -> list[Conversation]:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
        )
        return result.scalars().all()

    async def verify_conversation_owner(
        self, conversation_id: int, user_id: int, db: AsyncSession
    ) -> Conversation:
        """Security check — koi doosre ka conversation access na kar sake"""
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == user_id,
                Conversation.user_id == user_id,
            )
        )
        conv = result.scalar_one_or_none()
        if not conv:
            from fastapi import HTTPException
            raise HTTPException(404, "Conversation nahi mili ya access nahi hai")
        return conv

    # ── OpenAI Chat ───────────────────────────────────────────────────────────
    async def chat_openai(
        self,
        user_message: str,
        history: list[dict],
        model: str = "gpt-4o-mini",
        system_prompt: str = None,
    ) -> dict:
        """
        Normal (Non-Streaming) OpenAI call
        Cache check → LLM call → Cache save
        """
        # Step 1: Cache check karo
        cached = await cache_service.get_llm_response(user_message, model)
        if cached:
            return cached

        # Step 2: Messages build karo
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        # Step 3: OpenAI call
        response = await openai_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=1500,
            temperature=0.7,  # 0=deterministic, 1=creative
        )

        result = {
            "content":      response.choices[0].message.content,
            "tokens_used":  response.usage.total_tokens,
            "model":        model,
            "finish_reason": response.choices[0].finish_reason,
        }

        # Step 4: Cache mein save karo
        await cache_service.set_llm_response(user_message, model, result)

        return result

    # ── STREAMING ─────────────────────────────────────────────────────────────
    async def stream_openai(
        self,
        user_message: str,
        history: list[dict],
        model: str = "gpt-4o-mini",
        system_prompt: str = None,
        rag_context: str = None,
    ) -> AsyncGenerator[str, None]:
        """
        STREAMING Response — ChatGPT jaisa feel

        AsyncGenerator kya hai?
        Normal function: ek baar run karo, ek value return karo
        Generator:       baar baar run karo, har baar ek value 'yield' karo

        Yahan har LLM token aata hai → hum turant client ko bhejte hain
        Client mein real-time text dikhta hai

        FastAPI mein StreamingResponse use karte hain is ke saath
        """
        messages = []

        # System prompt (RAG context bhi yahan aata hai)
        base_system = system_prompt or "Aap ek helpful AI assistant hain."
        if rag_context:
            base_system += f"""

Neeche diya gaya context use karo jawab dene ke liye.
Sirf is context se jawab do. Agar context mein nahi hai to
'Mujhe is ke baare mein maloomat nahi' kaho.

CONTEXT:
{rag_context}
"""
        messages.append({"role": "system", "content": base_system})

        # History + current message
        messages.extend(history[-6:])  # Last 6 messages (tokens bachao)
        messages.append({"role": "user", "content": user_message})

        # Streaming call
        full_response = ""
        try:
            stream = await openai_client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=1500,
                stream=True,  # ← Yeh magic line hai!
            )

            async for chunk in stream:
                delta = chunk.choices[0].delta

                if delta.content:
                    full_response += delta.content
                    # Har chunk turant yield karo → client ko milta hai
                    yield delta.content

        except openai.APIError as e:
            logger.error(f"OpenAI API Error: {e}")
            yield f"\n[Error: LLM service unavailable — {str(e)}]"

        # Streaming khatam hone ke baad full response log karo
        logger.info(f"Streaming complete. Total chars: {len(full_response)}")

    # ── Anthropic (Claude) ────────────────────────────────────────────────────
    async def chat_anthropic(
        self,
        user_message: str,
        history: list[dict],
        system_prompt: str = None,
    ) -> dict:
        """Claude API integration"""
        cached = await cache_service.get_llm_response(
            user_message, "claude-sonnet-4-20250514"
        )
        if cached:
            return cached

        response = await anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            system=system_prompt or "Aap ek helpful AI assistant hain.",
            messages=[
                *history[-6:],
                {"role": "user", "content": user_message},
            ],
        )

        result = {
            "content":     response.content[0].text,
            "tokens_used": response.usage.input_tokens + response.usage.output_tokens,
            "model":       "claude-sonnet-4-20250514",
        }
        await cache_service.set_llm_response(
            user_message, "claude-sonnet-4-20250514", result
        )
        return result

    async def stream_anthropic(
        self,
        user_message: str,
        history: list[dict],
        system_prompt: str = None,
    ) -> AsyncGenerator[str, None]:
        """Claude streaming"""
        async with anthropic_client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            system=system_prompt or "Aap ek helpful AI assistant hain.",
            messages=[*history[-6:], {"role": "user", "content": user_message}],
        ) as stream:
            async for text in stream.text_stream:
                yield text


# ─── Singleton ────────────────────────────────────────────────────────────────
chat_service = ChatService()