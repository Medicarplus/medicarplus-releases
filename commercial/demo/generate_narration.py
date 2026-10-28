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
        "Renovar carnets, emitir certificados médicos, cobrar y avisar, todo desde una sola pantalla. "
        "Mira cómo funciona."
    ),
    "01_csv": (
        "El día empieza aquí. Importas el fichero CSV que descargas de la DGT en un solo clic. "
        "El programa clasifica cada reconocimiento médico automáticamente por tipo, grupo y tasa oficial. "
        "Renovaciones, expediciones, canjes, armas, animales peligrosos... "
        "todo ordenado y listo para cobrar sin tocar nada más."
    ),
    "02_dia": (
        "Durante el día añades los reconocimientos médicos, fotos, duplicados, certificados oficiales "
        "y pagos manuales en segundos. Elige concepto, paciente, importe y forma de pago. "
        "En la columna de la derecha ves en tiempo real cuánto has cobrado: por efectivo, tarjeta, "
        "bizum, transferencia... La caja cuadra sola al cerrar el día."
    ),
    "03_stats": (
        "En Estadísticas tienes todo tu centro médico en una pantalla: "
        "facturación mensual y anual por categoría, reconocimientos por grupo, "
        "pacientes que llegan de cada autoescuela, ingresos de los socios. "
        "Los datos están listos para enseñar al asesor fiscal."
    ),
    "04_sms": (
        "Los avisos SMS se mandan solos. Cada paciente recibe el recordatorio de su reconocimiento "
        "médico antes de que caduque el carnet. Puedes editar la plantilla, elegir a qué grupos "
        "avisar y seguir las estadísticas de envíos y de respuestas en tiempo real."
    ),
    "05_audit": (
        "La auditoría detecta duplicados, reconocimientos interrumpidos y posibles fallos con importe cero. "
        "Marcas el rango, el programa mira tres meses atrás automáticamente, "
        "y en segundos ves qué revisar antes de cerrar el mes."
    ),
    "06_outro": (
        "MediCar Plus. Menos tiempo con los números, más tiempo con tus pacientes. "
        "Pruébalo hoy."
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
