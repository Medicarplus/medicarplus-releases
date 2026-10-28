"""
Genera los 7 segmentos narrados en español usando Fal.ai ElevenLabs v3 TTS
(voz Liam, multilingüe, dinámica/entusiasta) para el vídeo demo.

CONTEXTO: MediCar Plus es un software para CENTROS MÉDICOS DE RECONOCIMIENTO DE CONDUCTORES
(donde se renuevan los carnets y se emiten certificados médicos). NO ES PARA AUTOESCUELAS.

Usa la Emergent Universal Key via integration-proxy (modo A del Fal playbook).
"""
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

EMERGENT_LLM_KEY = os.environ["EMERGENT_LLM_KEY"]
INTEGRATION_PROXY_BASE = os.environ.get(
    "INTEGRATION_PROXY_URL",
    "https://integrations.emergentagent.com",
).rstrip("/")
# Fal Universal Key supports queue-based inference through Emergent proxy only, not Platform APIs.
CONTROL_BASE = f"{INTEGRATION_PROXY_BASE}/api/v1/fal"
PUBLIC_QUEUE_BASE = f"{CONTROL_BASE}/queue"
QUEUE_ORIGIN = "https://queue.fal.run"
ENDPOINT_ID = "fal-ai/elevenlabs/tts/eleven-v3"
VOICE = "Liam"           # masculino, multilingüe, tono dinámico/natural
STABILITY = 0.35         # <0.5 → más expresivo/entusiasta
LANGUAGE_CODE = "es"

SEGMENTS = {
    "00_intro": (
        "MediCar Plus es la gestión integral para centros médicos de reconocimiento de conductores. "
        "Importa, cobra, revisa y avisa, todo desde una sola pantalla. Mira cómo funciona."
    ),
    "01_csv": (
        "Al descargar el CSV del día desde la DGT, el programa carga automáticamente todas las "
        "fichas con tipo, grupo, tasa y datos del paciente. No tienes que meter nada a mano: "
        "al abrir el programa ya tienes el día listo para cobrar."
    ),
    "02_dia": (
        "A lo largo del día cobras pagos, añades revisiones privadas, fotos, duplicados o "
        "certificados oficiales. En la columna derecha ves el total cobrado por efectivo, "
        "tarjeta, bizum y transferencia. Al cerrar, la caja cuadra sola."
    ),
    "03_stats": (
        "En Estadísticas tienes el centro entero en una pantalla: facturación mensual y anual, "
        "trámites de Tráfico por grupo, pacientes derivados de cada autoescuela y comparativas "
        "año actual contra el anterior. Listo para el asesor fiscal."
    ),
    "04_sms": (
        "Los avisos SMS se envían solos. Cada paciente recibe el recordatorio de su reconocimiento "
        "antes de que caduque el carnet. Puedes editar la plantilla, elegir a qué grupos avisar "
        "y seguir los envíos, errores y respuestas de cada campaña."
    ),
    "05_audit": (
        "La auditoría encuentra duplicados, reconocimientos interrumpidos y posibles fallos con "
        "importe cero mirando hasta tres meses atrás. En segundos sabes qué revisar antes de "
        "cerrar el mes."
    ),
    "06_outro": (
        "MediCar Plus. Menos tiempo con los números, más tiempo con tus pacientes."
    ),
}


def _headers(extra=None):
    headers = {
        "Authorization": f"Bearer {EMERGENT_LLM_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


def _trusted_proxy_queue_url(value: str) -> str:
    candidate = urlparse(value)
    queue_base = urlparse(PUBLIC_QUEUE_BASE)
    queue_path_prefix = queue_base.path.rstrip("/") + "/"
    if (
        candidate.scheme != queue_base.scheme
        or candidate.netloc != queue_base.netloc
        or not candidate.path.startswith(queue_path_prefix)
    ):
        raise RuntimeError(f"untrusted queue url: {value}")
    return value


def tts(text: str, timeout_s: int = 300) -> bytes:
    """Submit → poll → fetch result → download audio bytes."""
    submit = requests.post(
        f"{CONTROL_BASE}/proxy",
        headers=_headers({"X-Fal-Target-Url": f"{QUEUE_ORIGIN}/{ENDPOINT_ID}"}),
        json={
            "text": text,
            "voice": VOICE,
            "language_code": LANGUAGE_CODE,
            "stability": STABILITY,
            "apply_text_normalization": "auto",
            "timestamps": False,
        },
        timeout=60,
    )
    if submit.status_code == 402:
        raise RuntimeError("Insufficient Universal Key credits")
    submit.raise_for_status()
    sub = submit.json()
    status_url = _trusted_proxy_queue_url(sub["status_url"])
    response_url = _trusted_proxy_queue_url(sub["response_url"])

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        st = requests.get(status_url, headers=_headers(), timeout=30)
        st.raise_for_status()
        body = st.json()
        status = (body.get("status") or "").upper()
        if status in {"COMPLETED", "OK"}:
            if body.get("error"):
                raise RuntimeError(f"TTS failed: {body['error']}")
            res = requests.get(response_url, headers=_headers(), timeout=60)
            res.raise_for_status()
            result = res.json()
            audio_url = result["audio"]["url"]
            dl = requests.get(audio_url, timeout=120)
            dl.raise_for_status()
            return dl.content
        if status in {"FAILED", "CANCELLED", "CANCELED", "ERROR"}:
            raise RuntimeError(f"TTS failed with status {status}: {body}")
        time.sleep(1.5)
    raise RuntimeError("TTS timed out")


def main():
    out = Path("/app/commercial/demo/audio")
    out.mkdir(parents=True, exist_ok=True)
    for name, text in SEGMENTS.items():
        print(f"[tts] {name} · {len(text)} chars · voice={VOICE} stability={STABILITY}...")
        audio = tts(text)
        path = out / f"{name}.mp3"
        path.write_bytes(audio)
        print(f"      → {path.name} ({len(audio)/1024:.1f} KB)")
    print("\nSegmentos listos en:", out)


if __name__ == "__main__":
    main()
