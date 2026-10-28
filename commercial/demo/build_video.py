"""
Pipeline completo del vídeo demo MediCar Plus.

Fases:
  1. Monta la pista de audio final (concat de 7 segmentos + silencios de transición).
  2. Mide duraciones y arma el script de timings para el screencast.
  3. Lanza Playwright → graba WEBM del flujo guiado del software.
  4. Mezcla vídeo + audio con ffmpeg → MP4 final.
  5. Copia el MP4 a /app/frontend/public/demo/medicar_demo.mp4.
"""
import asyncio
import subprocess
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path("/app/commercial/demo")
AUDIO_DIR = ROOT / "audio"
BUILD_DIR = ROOT / "build"
OUT_DIR = Path("/app/frontend/public/demo")
BUILD_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Duración (segundos) de cada segmento MP3 (medidas con ffprobe)
SEG_DUR = {
    "00_intro": 12.7,
    "01_csv":   18.8,
    "02_dia":   20.0,
    "03_stats": 15.8,
    "04_sms":   15.9,
    "05_audit": 13.9,
    "06_outro": 5.4,
}
SILENCE_SEC = 1.6  # silencio entre segmentos
PREVIEW_URL = "https://project-helper-47.preview.emergentagent.com/v2.html?demo=1"
VIEWPORT = {"width": 1600, "height": 900}

def build_timeline():
    """Retorna lista [(label, start_sec, end_sec)] alineada al audio final."""
    t = 0.0
    timeline = []
    for seg, dur in SEG_DUR.items():
        timeline.append((seg, t, t + dur))
        t += dur + SILENCE_SEC
    total = t - SILENCE_SEC  # el último no lleva silencio después
    return timeline, total

def concat_audio():
    """Concatena los 7 MP3 con 1.6s de silencio entre cada uno → audio_final.mp3."""
    print("[audio] generando pista final...")
    # 1. silencio base
    silence_path = BUILD_DIR / "silence.mp3"
    subprocess.run([
        "ffmpeg","-y","-f","lavfi","-i",f"anullsrc=r=24000:cl=mono",
        "-t",str(SILENCE_SEC),"-q:a","9","-acodec","libmp3lame",str(silence_path)
    ], check=True, capture_output=True)
    # 2. file list
    list_path = BUILD_DIR / "concat.txt"
    lines = []
    segments = list(SEG_DUR.keys())
    for i, seg in enumerate(segments):
        lines.append(f"file '{AUDIO_DIR / (seg + '.mp3')}'")
        if i < len(segments) - 1:
            lines.append(f"file '{silence_path}'")
    list_path.write_text("\n".join(lines))
    # 3. concat
    final = BUILD_DIR / "audio_final.mp3"
    subprocess.run([
        "ffmpeg","-y","-f","concat","-safe","0","-i",str(list_path),
        "-c","copy",str(final)
    ], check=True, capture_output=True)
    dur = float(subprocess.check_output([
        "ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=noprint_wrappers=1:nokey=1",str(final)
    ]).decode().strip())
    print(f"[audio] final: {dur:.1f}s en {final}")
    return final, dur


async def record_screencast(duration_target: float, timeline):
    """Graba un WEBM con Playwright navegando por la app en los tiempos indicados."""
    print(f"[rec] arrancando screencast (~{duration_target:.0f}s)...")
    out_webm_dir = BUILD_DIR / "rec"
    out_webm_dir.mkdir(exist_ok=True)
    # Timeline → marcas de inicio de cada sección
    marks = {label: start for label, start, _ in timeline}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=[
            "--disable-blink-features=AutomationControlled",
            "--autoplay-policy=no-user-gesture-required",
        ])
        context = await browser.new_context(
            viewport=VIEWPORT,
            record_video_dir=str(out_webm_dir),
            record_video_size=VIEWPORT,
        )
        page = await context.new_page()
        # 0) Reset storage antes del demo mode
        await page.goto(PREVIEW_URL.replace("?demo=1", ""), wait_until="domcontentloaded", timeout=30000)
        await page.evaluate("localStorage.clear()")
        # 1) Modo demo
        t0 = asyncio.get_event_loop().time()
        async def until(label: str):
            target = marks[label]
            while asyncio.get_event_loop().time() - t0 < target:
                await asyncio.sleep(0.05)

        await page.goto(PREVIEW_URL, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3500)

        # 00_intro (0-12.7s): pantalla principal, scroll suave
        await until("00_intro")
        try:
            await page.mouse.wheel(0, 100); await page.wait_for_timeout(2500)
            await page.mouse.wheel(0, -80); await page.wait_for_timeout(2500)
        except Exception: pass

        # 01_csv (14.3-33.1s): abrir Importar CSV
        await until("01_csv")
        try:
            btn = page.locator('#btnImport').first
            if await btn.count():
                await btn.scroll_into_view_if_needed()
                await btn.hover(); await page.wait_for_timeout(900)
                await btn.click(force=True); await page.wait_for_timeout(2000)
                # cerrar modal si abrió
                await page.keyboard.press("Escape"); await page.wait_for_timeout(1500)
        except Exception as e: print(f"  csv step err: {e}")
        # recorrido por entradas del día
        try:
            await page.mouse.wheel(0, 300); await page.wait_for_timeout(1800)
            await page.mouse.wheel(0, -200); await page.wait_for_timeout(1500)
        except Exception: pass

        # 02_dia (34.7-54.7s): mover por entradas, hover en concepto
        await until("02_dia")
        try:
            name_inp = page.locator('#t-nombre').first
            if await name_inp.count():
                await name_inp.scroll_into_view_if_needed()
                await name_inp.click(); await page.wait_for_timeout(400)
                await name_inp.type("PACIENTE DEMO", delay=85)
                await page.wait_for_timeout(600)
                dni = page.locator('#t-dni').first
                if await dni.count(): await dni.click(); await dni.type("12345678A", delay=70)
                imp = page.locator('#t-importe').first
                if await imp.count(): await imp.click(); await imp.type("43", delay=90)
                await page.wait_for_timeout(1200)
                # NO guardamos realmente
                await page.locator('#t-nombre').fill("")
                await page.locator('#t-dni').fill("")
                await page.locator('#t-importe').fill("")
        except Exception as e: print(f"  dia step err: {e}")
        # mostrar cierre del día (lateral derecho)
        try:
            await page.mouse.move(1300, 450); await page.wait_for_timeout(1500)
            await page.mouse.wheel(0, 300); await page.wait_for_timeout(1500)
            await page.mouse.wheel(0, -300); await page.wait_for_timeout(1200)
        except Exception: pass

        # 03_stats (56.3-72.1s): abrir Estadísticas → Facturación
        await until("03_stats")
        try:
            # Buscar el botón de Estadísticas en el header
            await page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('button, a, span'));
                const sb = btns.find(b => /Estad.stic/.test(b.textContent||''));
                if(sb) sb.click();
            }""")
            await page.wait_for_timeout(1200)
            # abrir facturación anual
            await page.evaluate("""() => {
                const el = Array.from(document.querySelectorAll('button,a,li,span')).find(x => /Facturaci.n|Factura/.test(x.textContent||''));
                if(el) el.click();
            }""")
            await page.wait_for_timeout(2500)
            await page.mouse.wheel(0, 400); await page.wait_for_timeout(2500)
            await page.mouse.wheel(0, -400); await page.wait_for_timeout(1500)
            await page.keyboard.press("Escape"); await page.wait_for_timeout(1000)
        except Exception as e: print(f"  stats step err: {e}")

        # 04_sms (73.7-89.6s): abrir utilidades → SMS
        await until("04_sms")
        try:
            await page.evaluate("""() => {
                const el = Array.from(document.querySelectorAll('button,a,span')).find(x => /Utilidades|Utilitats/.test(x.textContent||''));
                if(el) el.click();
            }""")
            await page.wait_for_timeout(1200)
            await page.evaluate("""() => {
                const el = Array.from(document.querySelectorAll('button,a,li,span')).find(x => /SMS|Avisos/.test(x.textContent||''));
                if(el) el.click();
            }""")
            await page.wait_for_timeout(2500)
            await page.mouse.wheel(0, 300); await page.wait_for_timeout(2000)
            await page.mouse.wheel(0, -300); await page.wait_for_timeout(1500)
            await page.keyboard.press("Escape"); await page.wait_for_timeout(1000)
        except Exception as e: print(f"  sms step err: {e}")

        # 05_audit (91.2-105.1s): abrir Auditoría
        await until("05_audit")
        try:
            await page.evaluate("""() => {
                const el = Array.from(document.querySelectorAll('button,a,span')).find(x => /Auditor.a|Auditoria/.test(x.textContent||''));
                if(el) el.click();
            }""")
            await page.wait_for_timeout(2500)
            await page.mouse.wheel(0, 300); await page.wait_for_timeout(2000)
            await page.mouse.wheel(0, -200); await page.wait_for_timeout(1500)
            await page.keyboard.press("Escape"); await page.wait_for_timeout(1000)
        except Exception as e: print(f"  audit step err: {e}")

        # 06_outro (106.7-112.1s): zoom al logo
        await until("06_outro")
        try:
            await page.mouse.wheel(0, -2000); await page.wait_for_timeout(1500)
        except Exception: pass

        # Esperar al final
        while asyncio.get_event_loop().time() - t0 < duration_target + 0.5:
            await asyncio.sleep(0.1)

        await context.close()
        await browser.close()

    # Localizar el webm generado
    webm = sorted(out_webm_dir.glob("*.webm"), key=lambda p: p.stat().st_mtime)[-1]
    print(f"[rec] webm: {webm}")
    return webm


def merge(webm: Path, audio: Path, audio_dur: float):
    out_mp4 = OUT_DIR / "medicar_demo.mp4"
    print(f"[merge] combinando → {out_mp4}")
    subprocess.run([
        "ffmpeg","-y",
        "-i",str(webm),
        "-i",str(audio),
        "-c:v","libx264","-crf","23","-preset","medium","-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","128k",
        "-map","0:v:0","-map","1:a:0",
        "-shortest",
        "-movflags","+faststart",
        str(out_mp4)
    ], check=True, capture_output=True)
    size_mb = out_mp4.stat().st_size / 1024 / 1024
    print(f"[merge] MP4 listo: {out_mp4} ({size_mb:.1f} MB)")
    # Generar también un poster para el reproductor
    poster = OUT_DIR / "medicar_demo_poster.jpg"
    subprocess.run([
        "ffmpeg","-y","-ss","2","-i",str(out_mp4),
        "-frames:v","1","-q:v","3",str(poster)
    ], check=True, capture_output=True)
    print(f"[merge] poster: {poster}")

async def main():
    timeline, total = build_timeline()
    print(f"[plan] timeline:")
    for s, a, b in timeline:
        print(f"       {s}: {a:5.1f} → {b:5.1f}s")
    print(f"[plan] duración objetivo: {total:.1f}s")
    audio_path, audio_dur = concat_audio()
    webm = await record_screencast(audio_dur, timeline)
    merge(webm, audio_path, audio_dur)
    print("\n✅ Vídeo demo listo. Entra con ?demo=1 en la landing y pulsa 'VER VÍDEO DEMO'.")

if __name__ == "__main__":
    asyncio.run(main())
