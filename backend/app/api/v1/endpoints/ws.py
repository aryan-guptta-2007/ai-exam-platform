import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.redis import redis_service
from loguru import logger

router = APIRouter()

@router.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """
    Subscribes to Redis PubSub channel for the specified task_id,
    and streams celery progress updates to the client in real-time.
    """
    await websocket.accept()
    logger.info(f"WebSocket client connected for task channel: {task_id}")
    
    if not redis_service.client:
        await websocket.send_json({
            "event": "error",
            "task_id": task_id,
            "payload": {"message": "Redis broker unavailable."}
        })
        await websocket.close()
        return

    # Subscribe to Redis PubSub
    pubsub = redis_service.client.pubsub()
    channel_name = f"task:{task_id}"
    await pubsub.subscribe(channel_name)
    
    # Send acknowledgment
    await websocket.send_json({
        "event": "connected",
        "task_id": task_id,
        "payload": {"message": f"Subscribed to status channel {channel_name}"}
    })

    try:
        while True:
            # Poll Redis PubSub channel for new messages
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                data = message["data"]
                # Forward published task payloads directly to the WebSocket client
                try:
                    payload = json.loads(data)
                    await websocket.send_json(payload)
                    
                    # If job is complete or errored, close connection
                    event = payload.get("event")
                    status_val = payload.get("payload", {}).get("status")
                    if event == "complete" or status_val in ("done", "error"):
                        logger.info(f"Task {task_id} completed or errored. Closing WebSocket.")
                        break
                except json.JSONDecodeError:
                    await websocket.send_text(str(data))
            
            # Small heartbeat sleep to prevent high CPU utilization
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected from task channel: {task_id}")
    except Exception as e:
        logger.error(f"WebSocket execution error on task channel {task_id}: {e}")
    finally:
        await pubsub.unsubscribe(channel_name)
        await pubsub.close()
