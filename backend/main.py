import json
import os
from contextlib import asynccontextmanager

import websockets
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth import authenticate, create_token, verify_token

load_dotenv()

ROSBRIDGE_URL = os.getenv("ROSBRIDGE_URL", "ws://localhost:9090")

# MVP: in-memory task store. Replaced with persistent store post-MVP.
_tasks: dict[str, dict] = {}
_task_counter = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Snoopi API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for production
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    username: str
    password: str


class TaskRequest(BaseModel):
    type: str
    distance_m: float


class TaskResponse(BaseModel):
    id: str
    type: str
    distance_m: float
    status: str


async def _publish(topic: str, msg_type: str, data: dict) -> bool:
    """Send a single publish message to rosbridge and close the connection."""
    try:
        async with websockets.connect(ROSBRIDGE_URL, open_timeout=3) as ws:
            await ws.send(json.dumps({
                "op": "publish",
                "topic": topic,
                "type": msg_type,
                "msg": data,
            }))
        return True
    except Exception:
        return False


@app.post("/auth/login")
async def login(req: LoginRequest):
    user = authenticate(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(user["username"], user["display_name"])
    return {"token": token, "user": user}


@app.get("/auth/me")
async def me(authorization: str = Header(default=None)):
    return _require_auth(authorization)


def _require_auth(authorization: str | None) -> dict:
    """Verify Bearer token and return user dict, or raise 401."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    user = verify_token(authorization.removeprefix("Bearer "))
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


@app.get("/health")
async def health():
    """Backend health check. Reports whether rosbridge is reachable."""
    try:
        async with websockets.connect(ROSBRIDGE_URL, open_timeout=2):
            rosbridge_status = "reachable"
    except Exception:
        rosbridge_status = "unreachable"
    return {"status": "ok", "rosbridge": rosbridge_status}


@app.post("/tasks", response_model=TaskResponse)
async def create_task(req: TaskRequest, authorization: str = Header(default=None)):
    _require_auth(authorization)
    global _task_counter
    if req.type != "walk":
        raise HTTPException(status_code=400, detail="Only 'walk' tasks supported in MVP")
    if req.distance_m <= 0:
        raise HTTPException(status_code=400, detail="distance_m must be positive")

    _task_counter += 1
    task_id = str(_task_counter)
    _tasks[task_id] = {
        "id": task_id,
        "type": req.type,
        "distance_m": req.distance_m,
        "status": "pending",
    }

    await _publish(
        topic="/snoopi/task_command",
        msg_type="std_msgs/msg/String",
        data={"data": json.dumps({"type": req.type, "distance_m": req.distance_m, "task_id": task_id})},
    )
    _tasks[task_id]["status"] = "dispatched"
    return _tasks[task_id]


@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return _tasks[task_id]


@app.post("/estop")
async def estop(authorization: str = Header(default=None)):
    """Publish emergency stop command to ROS2 via rosbridge."""
    _require_auth(authorization)
    ok = await _publish(
        topic="/snoopi/estop",
        msg_type="std_msgs/msg/Bool",
        data={"data": True},
    )
    return {"status": "sent" if ok else "failed", "rosbridge_reachable": ok}
