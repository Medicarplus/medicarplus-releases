"""
Genera los 7 segmentos narrados en español (voz Echo, OpenAI TTS) para el vídeo demo.

CONTEXTO: MediCar Plus es un software para CENTROS MÉDICOS DE RECONOCIMIENTO DE CONDUCTORES
(donde se renuevan los carnets y se emiten certificados médicos). NO ES PARA AUTOESCUELAS.
"""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

from emergentintegrations.llm.openai import OpenAITextToSpeech

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

async def main():
    out = Path("/app/commercial/demo/audio")
    out.mkdir(parents=True, exist_ok=True)
    key = os.getenv("EMERGENT_LLM_KEY")
    if not key:
        print("ERROR: EMERGENT_LLM_KEY no encontrada"); sys.exit(1)
    tts = OpenAITextToSpeech(api_key=key)
    for name, text in SEGMENTS.items():
        print(f"[tts] {name} · {len(text)} chars...")
        audio = await tts.generate_speech(text=text, model="tts-1-hd", voice="echo", speed=1.0)
        path = out / f"{name}.mp3"
        path.write_bytes(audio)
        print(f"      → {path.name} ({len(audio)/1024:.1f} KB)")
    print("\nSegmentos listos en:", out)

if __name__ == "__main__":
    asyncio.run(main())
