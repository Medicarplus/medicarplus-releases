"""
Genera 3 muestras de voz en español para que el usuario elija la voz final
antes de montar el vídeo completo.

Uso: python3 /app/commercial/demo/test_voice.py
Salida: /app/commercial/demo/samples/*.mp3
"""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

from emergentintegrations.llm.openai import OpenAITextToSpeech

SAMPLE_TEXT = (
    "Bienvenido a MediCar Plus, la gestión integral para centros médicos de reconocimiento "
    "y autoescuelas. En menos de un minuto importas el CSV de la DGT, cuadras caja, "
    "revisas estadísticas y envías los avisos SMS a tus clientes."
)

VOICES = ["nova", "shimmer", "echo", "alloy"]

async def main():
    out_dir = Path("/app/commercial/demo/samples")
    out_dir.mkdir(parents=True, exist_ok=True)
    key = os.getenv("EMERGENT_LLM_KEY")
    if not key:
        print("ERROR: EMERGENT_LLM_KEY no está cargada")
        sys.exit(1)
    tts = OpenAITextToSpeech(api_key=key)
    for v in VOICES:
        print(f"[tts] generando voz '{v}'...")
        try:
            audio = await tts.generate_speech(
                text=SAMPLE_TEXT,
                model="tts-1-hd",
                voice=v,
                speed=1.0,
            )
            path = out_dir / f"sample_{v}.mp3"
            path.write_bytes(audio)
            print(f"  → {path} ({len(audio)/1024:.1f} KB)")
        except Exception as e:
            print(f"  ✗ FALLO con '{v}': {e}")
    print("\nMuestras en:", out_dir)

if __name__ == "__main__":
    asyncio.run(main())
