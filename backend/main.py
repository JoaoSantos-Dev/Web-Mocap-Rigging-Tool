import json
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
PROCESSED_DIR = BASE_DIR / "processed"
RIGGED_DIR = BASE_DIR / "rigged"
SCRIPT_PATH = BASE_DIR / "scripts" / "convert_to_glb.py"
RIG_SCRIPT_PATH = BASE_DIR / "scripts" / "generate_rig.py"
ALLOWED_EXTENSIONS = {".obj", ".fbx", ".glb", ".gltf"}
REQUIRED_MARKERS = {
    "chin",
    "pelvis",
    "leftShoulder",
    "rightShoulder",
    "leftElbow",
    "rightElbow",
    "leftWrist",
    "rightWrist",
    "leftKnee",
    "rightKnee",
    "leftAnkle",
    "rightAnkle",
}

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
RIGGED_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Mixamo Pessoal API")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MarkerPoint(BaseModel):
    x: float
    y: float
    z: float


class RigRequest(BaseModel):
    modelFilename: str
    markers: dict[str, MarkerPoint]
    exportFormat: Literal["glb", "fbx"] = "glb"


def resolve_blender_command() -> str | None:
    command = os.getenv("BLENDER_PATH", "blender")
    if "/" in command or "\\" in command:
        return command if Path(command).exists() else None
    return shutil.which(command)


def build_blender_environment() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)

    virtual_env = env.pop("VIRTUAL_ENV", None)
    if virtual_env:
        venv_bin = Path(virtual_env) / ("Scripts" if os.name == "nt" else "bin")
        path_parts = env.get("PATH", "").split(os.pathsep)
        env["PATH"] = os.pathsep.join(
            part for part in path_parts if Path(part).resolve() != venv_bin.resolve()
        )

    return env


def validate_processed_model_filename(filename: str) -> Path:
    if Path(filename).name != filename or Path(filename).suffix.lower() != ".glb":
        raise HTTPException(status_code=400, detail="Nome de modelo convertido inválido.")

    model_path = PROCESSED_DIR / filename
    if not model_path.exists():
        raise HTTPException(status_code=404, detail="Modelo convertido não encontrado.")

    return model_path


def validate_rigged_filename(filename: str) -> Path:
    suffix = Path(filename).suffix.lower()
    if Path(filename).name != filename or suffix not in {".glb", ".fbx"}:
        raise HTTPException(status_code=400, detail="Nome de arquivo rigado inválido.")

    file_path = RIGGED_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo rigado não encontrado.")

    return file_path


def validate_required_markers(markers: dict[str, MarkerPoint]) -> None:
    missing = sorted(REQUIRED_MARKERS - set(markers))
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Marcadores obrigatórios ausentes: {', '.join(missing)}.",
        )


def validate_filename(filename: str | None) -> tuple[str, str]:
    if not filename:
        raise HTTPException(status_code=400, detail="Nenhum arquivo foi enviado.")

    safe_name = Path(filename).name
    extension = Path(safe_name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        accepted = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=400,
            detail=f"Formato inválido. Envie um arquivo nos formatos: {accepted}.",
        )

    return safe_name, extension


async def save_upload(file: UploadFile, destination: Path) -> None:
    try:
        with destination.open("wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                buffer.write(chunk)
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Não foi possível salvar o arquivo enviado: {exc}",
        ) from exc
    finally:
        await file.close()


def run_blender(command: list[str], output_path: Path, failure_message: str) -> subprocess.CompletedProcess[str]:
    blender_command = resolve_blender_command()
    if not blender_command:
        raise HTTPException(
            status_code=500,
            detail=(
                "Blender não encontrado. Instale o Blender e garanta que o comando "
                "'blender' esteja disponível no PATH, ou defina BLENDER_PATH."
            ),
        )

    try:
        result = subprocess.run(
            [blender_command, *command],
            capture_output=True,
            check=False,
            env=build_blender_environment(),
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired as exc:
        output_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=500,
            detail="O processamento no Blender demorou demais e foi interrompido pelo servidor.",
        ) from exc
    except OSError as exc:
        output_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=500,
            detail=f"Não foi possível executar o Blender: {exc}",
        ) from exc

    log = (result.stderr or result.stdout or "Sem saída do Blender.")[-4000:]
    if result.returncode != 0:
        output_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"{failure_message}. Log: {log}")

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise HTTPException(
            status_code=500,
            detail=f"O Blender terminou sem gerar um arquivo válido. Log: {log}",
        )

    return result


@app.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/api/convert")
async def convert_model(file: UploadFile = File(...)) -> dict[str, str | bool]:
    original_filename, extension = validate_filename(file.filename)

    conversion_id = uuid.uuid4().hex
    upload_filename = f"{conversion_id}{extension}"
    processed_filename = f"{conversion_id}.glb"
    upload_path = UPLOAD_DIR / upload_filename
    output_path = PROCESSED_DIR / processed_filename

    await save_upload(file, upload_path)

    command = [
        "--background",
        "--python",
        str(SCRIPT_PATH),
        "--",
        str(upload_path),
        str(output_path),
    ]

    run_blender(command, output_path, "Falha ao converter o modelo com Blender")

    file_url = f"/api/models/{processed_filename}"
    return {
        "success": True,
        "originalFilename": original_filename,
        "processedFilename": processed_filename,
        "downloadUrl": file_url,
        "fileUrl": file_url,
    }


@app.post("/api/rig")
def generate_rig(request: RigRequest) -> dict[str, str | bool]:
    model_path = validate_processed_model_filename(request.modelFilename)
    validate_required_markers(request.markers)

    rig_id = uuid.uuid4().hex
    markers_payload = {
        name: point.model_dump()
        for name, point in request.markers.items()
        if name in REQUIRED_MARKERS
    }

    temp_markers_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            delete=False,
        ) as temp_markers:
            json.dump({"markers": markers_payload}, temp_markers)
            temp_markers_path = Path(temp_markers.name)

        preview_filename = f"{rig_id}_rig.glb"
        preview_path = RIGGED_DIR / preview_filename
        run_blender(
            [
                "--background",
                "--python",
                str(RIG_SCRIPT_PATH),
                "--",
                str(model_path),
                str(temp_markers_path),
                str(preview_path),
                "glb",
            ],
            preview_path,
            "Falha ao gerar rig GLB com Blender",
        )

        if request.exportFormat == "glb":
            rigged_filename = preview_filename
            file_url = f"/api/rigged/{rigged_filename}"
        else:
            rigged_filename = f"{rig_id}_rig.fbx"
            output_path = RIGGED_DIR / rigged_filename
            run_blender(
                [
                    "--background",
                    "--python",
                    str(RIG_SCRIPT_PATH),
                    "--",
                    str(model_path),
                    str(temp_markers_path),
                    str(output_path),
                    "fbx",
                ],
                output_path,
                "Falha ao gerar rig FBX com Blender",
            )
            file_url = f"/api/rigged/{rigged_filename}"

        return {
            "success": True,
            "riggedFilename": rigged_filename,
            "fileUrl": file_url,
            "exportFormat": request.exportFormat,
            "previewFilename": preview_filename,
            "previewUrl": f"/api/rigged/{preview_filename}",
        }
    finally:
        if temp_markers_path:
            temp_markers_path.unlink(missing_ok=True)


@app.get("/api/models/{filename}")
def get_model(filename: str) -> FileResponse:
    if Path(filename).name != filename or Path(filename).suffix.lower() != ".glb":
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido.")

    file_path = PROCESSED_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Modelo convertido não encontrado.")

    return FileResponse(
        file_path,
        media_type="model/gltf-binary",
        filename=filename,
    )


@app.get("/api/rigged/{filename}")
def get_rigged_model(filename: str) -> FileResponse:
    file_path = validate_rigged_filename(filename)
    suffix = file_path.suffix.lower()
    media_type = "model/gltf-binary" if suffix == ".glb" else "application/octet-stream"

    return FileResponse(
        file_path,
        media_type=media_type,
        filename=filename,
    )
