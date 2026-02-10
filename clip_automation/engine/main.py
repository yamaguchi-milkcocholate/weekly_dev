from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


# Difyからのデータ構造を定義
class Scene(BaseModel):
    scene_index: int
    character_id: str
    image_prompt: str
    audio_text: str


class VideoRequest(BaseModel):
    scenes: list[Scene]


@app.post("/generate-video")
async def generate_video(request: VideoRequest):
    # ここにMoviePyの処理を書いていくことになります
    print(f"受信したシーン数: {len(request.scenes)}")
    for scene in request.scenes:
        print(f"シーン{scene.scene_index}: {scene.audio_text[:20]}...")

    return {
        "status": "success",
        "message": "データを受信しました。次はMoviePyの実装です！",
    }
