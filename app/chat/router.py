import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import get_current_user
from app.cache.service import cache_service
from app.chat.service import chat_service
from app.database import get_db
from app.rag.service import rag_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat"])


#  Schemas 
class CreateConversationRequest(BaseModel):
    title: str = "New Conversation"
    model: str = "gpt-4o-mini"


class SendMessageRequest(BaseModel):
    message: str
    use_rag: bool = False
    model: str = "gpt-4o-mini"


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    title: str
    model_used: str


class MessageResponse(BaseModel):
    response: str
    tokens_used: int
    model: str
    cached: bool = False


def get_user_id(current_user: dict) -> int:
    return int(current_user["sub"])


#  Endpoints 
@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=201,
    summary="Create Conversation",
    description="Naya conversation thread banao",
)
async def create_conversation(
    data: CreateConversationRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await chat_service.create_conversation(
        user_id=get_user_id(current_user),
        title=data.title,
        model=data.model,
        db=db,
    )
    return ConversationResponse.model_validate(conv)


@router.get(
    "/conversations",
    response_model=list[ConversationResponse],
    summary="List Conversations",
    description="Apni saari conversations dekho",
)
async def list_conversations(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    convs = await chat_service.get_user_conversations(get_user_id(current_user), db)
    return [ConversationResponse.model_validate(c) for c in convs]


@router.post(
    "/conversations/{conversation_id}",
    response_model=MessageResponse,
    summary="Send Message",
    description="""Normal (non-streaming) message bhejo

use_rag=True → pehle documents search, phir LLM ko context do
use_rag=False → seedha LLM se jawab""",
)
async def send_message(
    conversation_id: int,
    data: SendMessageRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = get_user_id(current_user)

    allowed, remaining = await cache_service.check_rate_limit(user_id)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Bohot zyada requests. 1 ghante mein 50 allowed hain.",
        )

    history = await chat_service.get_conversation_history(conversation_id, db)

    rag_context = None
    if data.use_rag:
        results = await rag_service.search_documents(
            query=data.message,
            user_id=user_id,
            db=db,
        )
        if results:
            rag_context = "\n\n".join([r["content"] for r in results])

    result = await chat_service.chat_openai(
        user_message=data.message,
        history=history,
        model=data.model,
    )

    await chat_service.save_messages(
        conversation_id=conversation_id,
        user_message=data.message,
        assistant_message=result["content"],
        tokens_used=result["tokens_used"],
        model=data.model,
        db=db,
    )

    return MessageResponse(
        response=result["content"],
        tokens_used=result["tokens_used"],
        model=result["model"],
        cached="from_cache" in result,
    )


@router.post(
    "/conversations/{conversation_id}/stream",
    summary="Stream Message",
    description="""ChatGPT-like Experience

How it works:

The client sends a request

The server returns a StreamingResponse

As the LLM generates tokens → the server sends them to the client in real-time

The client displays the text instantly as it arrives
SSE (Server-Sent Events) Format:

data: Hello

data: how

data: are

data: you?

data: [DONE]
""",
)
async def stream_message(
    conversation_id: int,
    data: SendMessageRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = get_user_id(current_user)

    allowed, _ = await cache_service.check_rate_limit(user_id)
    if not allowed:
        raise HTTPException(429, "Rate limit exceed ho gaya")

    history = await chat_service.get_conversation_history(conversation_id, db)

    rag_context = None
    if data.use_rag:
        results = await rag_service.search_documents(
            query=data.message,
            user_id=user_id,
            db=db,
        )
        rag_context = "\n\n".join([r["content"] for r in results]) if results else None

    collected_response = []

    async def event_generator():
        nonlocal collected_response

        async for chunk in chat_service.stream_openai(
            user_message=data.message,
            history=history,
            model=data.model,
            rag_context=rag_context,
        ):
            collected_response.append(chunk)
            event_data = json.dumps({"chunk": chunk, "done": False})
            yield f"data: {event_data}\n\n"

        yield f"data: {json.dumps({'chunk': '', 'done': True})}\n\n"

        full_response = "".join(collected_response)
        try:
            await chat_service.save_messages(
                conversation_id=conversation_id,
                user_message=data.message,
                assistant_message=full_response,
                tokens_used=len(full_response) // 4,
                model=data.model,
                db=db,
            )
        except Exception as e:
            logger.error(f"Message save error: {e}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )