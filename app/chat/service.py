import logging
from typing import AsyncGenerator

import google.generativeai as genai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.models import Conversation, Message
from app.config import settings

logger = logging.getLogger(__name__)

# Gemini setup
genai.configure(api_key=settings.GEMINI_API_KEY)


class ChatService:

    # History Management 

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
        messages.reverse()
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
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        conv = result.scalar_one_or_none()
        if not conv:
            from fastapi import HTTPException
            raise HTTPException(404, "Conversation nahi mili ya access nahi hai")
        return conv

    #  Gemini Chat (replaces OpenAI) 

    async def chat_openai(
        self,
        user_message: str,
        history: list[dict],
        model: str = "gemini-2.0-flash",
        system_prompt: str = None,
    ) -> dict:
       
        try:
            gemini_model = genai.GenerativeModel(
                model_name="gemini-2.0-flash",
                system_instruction=system_prompt or "You are a helpful AI assistant.",
            )

            # History ko Gemini format mein convert karo
            gemini_history = [
                {
                    "role": "user" if msg["role"] == "user" else "model",
                    "parts": [msg["content"]]
                }
                for msg in history[-6:]
            ]

            chat = gemini_model.start_chat(history=gemini_history)
            response = chat.send_message(user_message)

            return {
                "content":       response.text,
                "tokens_used":   0,   
                "model":         "gemini-2.0-flash",
                "finish_reason": "stop",
            }

        except Exception as e:
            logger.error(f"Gemini API Error: {e}")
            raise

    #  Gemini Streaming 

    async def stream_openai(
        self,
        user_message: str,
        history: list[dict],
        model: str = "gemini-2.0-flash",
        system_prompt: str = None,
        rag_context: str = None,
    ) -> AsyncGenerator[str, None]:
       
        try:
            base_system = system_prompt or "You are a helpful AI assistant."
            if rag_context:
                base_system += f"\n\nCONTEXT:\n{rag_context}"

            gemini_model = genai.GenerativeModel(
                model_name="gemini-2.0-flash",
                system_instruction=base_system,
            )

            gemini_history = [
                {
                    "role": "user" if msg["role"] == "user" else "model",
                    "parts": [msg["content"]]
                }
                for msg in history[-6:]
            ]

            chat = gemini_model.start_chat(history=gemini_history)

            # Streaming
            response = chat.send_message(user_message, stream=True)

            full_response = ""
            for chunk in response:
                if chunk.text:
                    full_response += chunk.text
                    yield chunk.text

            logger.info(f"Streaming complete. Total chars: {len(full_response)}")

        except Exception as e:
            logger.error(f"Gemini Streaming Error: {e}")
            yield f"\n[Error: {str(e)}]"

    # ── Gemini Chat (replaces Anthropic) ──────────────────────────────────────

    async def chat_anthropic(
        self,
        user_message: str,
        history: list[dict],
        system_prompt: str = None,
    ) -> dict:
       
        return await self.chat_openai(
            user_message=user_message,
            history=history,
            model="gemini-2.0-flash",
            system_prompt=system_prompt,
        )

    async def stream_anthropic(
        self,
        user_message: str,
        history: list[dict],
        system_prompt: str = None,
    ) -> AsyncGenerator[str, None]:
       
        async for chunk in self.stream_openai(
            user_message=user_message,
            history=history,
            system_prompt=system_prompt,
        ):
            yield chunk


# Singleton
chat_service = ChatService()