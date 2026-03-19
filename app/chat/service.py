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


# LLM Clients 
openai_client    = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)


# Chat Service 
class ChatService:

    #  History Management 
    async def get_conversation_history(
        self,
        conversation_id: int,
        db: AsyncSession,
        limit: int = 10,
    ) -> list[dict]:
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

    #  Conversation CRUD 
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

    #  OpenAI Chat 
    async def chat_openai(
        self,
        user_message: str,
        history: list[dict],
        model: str = "gpt-4o-mini",
        system_prompt: str = None,
    ) -> dict:

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

    #  STREAMING 
    async def stream_openai(
        self,
        user_message: str,
        history: list[dict],
        model: str = "gpt-4o-mini",
        system_prompt: str = None,
        rag_context: str = None,
    ) -> AsyncGenerator[str, None]:

        messages = []

        # System prompt (RAG context bhi yahan aata hai)
        base_system = system_prompt or "Aap ek helpful AI assistant hain."
        if rag_context:
            base_system += f"""

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

    #  Anthropic (Claude) 
    async def chat_anthropic(
        self,
        user_message: str,
        history: list[dict],
        system_prompt: str = None,
    ) -> dict:
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
        async with anthropic_client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            system=system_prompt or "Aap ek helpful AI assistant hain.",
            messages=[*history[-6:], {"role": "user", "content": user_message}],
        ) as stream:
            async for text in stream.text_stream:
                yield text


#  Singleton 
chat_service = ChatService()