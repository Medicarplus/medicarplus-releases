"""
Pipeline completo del vídeo demo MediCar Plus (feb 2026, revisión bonita).

Mejoras clave vs versión anterior:
- Menos tiempo en Home (apenas 3s de intro).
- Cada capítulo cierra el modal previo antes de abrir el siguiente.
- Capítulo CSV: hace scroll por la lista de fichas del día para mostrar que
  están "ya importadas automáticamente" (no manuales).
- Capítulo Stats: abre Facturación anual + Tráfico + Autoescuelas.
- Capítulo SMS: abre avisos, muestra listado de campañas y estadísticas.
- Capítulo Auditoría: 3 meses atrás, pestaña Dup/Int y Posible fallo.
- Outro: zoom al logo.

Audio total ~84s + silencios → ~94s de vídeo.
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

SEG_DUR = {
    "00_intro": 11.0,
    "01_csv":   14.0,
    "02_dia":   16.0,
    "03_stats": 14.5,
    "04_sms":   15.6,
    "05_audit": 11.9,
    "06_outro": 7.2,
}
SILENCE_SEC = 1.4
PREVIEW_URL = "https://project-helper-47.preview.emergentagent.com/v2.html?demo=1"
VIEWPORT = {"width": 1600, "height": 900}
# Tiempo (s) que la pestaña necesita para cargar antes de que t0 arranque.
# Debe coincidir con el `page.wait_for_timeout(PREROLL_MS)` del grabado,
# así podemos cortarlo del webm al mergear y el audio queda sincronizado.
PREROLL_SEC = 3.5

def build_timeline():
    t = 0.0
    timeline = []
    for seg, dur in SEG_DUR.items():
        timeline.append((seg, t, t + dur))
        t += dur + SILENCE_SEC
    total = t - SILENCE_SEC
    return timeline, total

def concat_audio():
    print("[audio] generando pista final...")
    silence_path = BUILD_DIR / "silence.mp3"
    subprocess.run([
        "ffmpeg","-y","-f","lavfi","-i","anullsrc=r=44100:cl=mono",
        "-t",str(SILENCE_SEC),"-b:a","128k","-ar","44100","-ac","1",
        "-acodec","libmp3lame",str(silence_path)
    ], check=True, capture_output=True)
    list_path = BUILD_DIR / "concat.txt"
    lines = []
    segments = list(SEG_DUR.keys())
    for i, seg in enumerate(segments):
        lines.append(f"file '{AUDIO_DIR / (seg + '.mp3')}'")
        if i < len(segments) - 1:
            lines.append(f"file '{silence_path}'")
    list_path.write_text("\n".join(lines))
    final = BUILD_DIR / "audio_final.mp3"
    subprocess.run([
        "ffmpeg","-y","-f","concat","-safe","0","-i",str(list_path),
        "-c","copy",str(final)
    ], check=True, capture_output=True)
    dur = float(subprocess.check_output([
        "ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=noprint_wrappers=1:nokey=1",str(final)
    ]).decode().strip())
    print(f"[audio] final: {dur:.1f}s")
    return final, dur


async def record_screencast(duration_target: float, timeline):
    print(f"[rec] arrancando screencast (~{duration_target:.0f}s)...")
    out_webm_dir = BUILD_DIR / "rec"
    out_webm_dir.mkdir(exist_ok=True)
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
        await page.goto(PREVIEW_URL.replace("?demo=1", ""), wait_until="domcontentloaded", timeout=30000)
        await page.evaluate("localStorage.clear()")
        await page.goto(PREVIEW_URL, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(int(PREROLL_SEC * 1000))

        t0 = asyncio.get_event_loop().time()

        async def close_any_modal():
            try:
                # Cerrar cualquier .modal-back visible y esperar a que el DOM se
                # repinte antes de abrir el siguiente. Añadimos un hard flush
                # (requestAnimationFrame) para que el frame siguiente no muestre
                # dos modales superpuestos.
                await page.evaluate("""() => new Promise(res => {
                    document.querySelectorAll('.modal-back').forEach(m => m.remove());
                    requestAnimationFrame(() => requestAnimationFrame(res));
                })""")
                await page.wait_for_timeout(400)
            except Exception: pass

        async def until(label: str):
            target = marks[label]
            while asyncio.get_event_loop().time() - t0 < target:
                await asyncio.sleep(0.05)

        async def click_id(sel: str, label: str = ""):
            """Click robusto por selector CSS."""
            try:
                el = page.locator(sel).first
                if await el.count():
                    await el.scroll_into_view_if_needed()
                    await el.click(force=True)
                    return True
                else:
                    print(f"  ⚠️ sel {sel} ({label}) no encontrado")
            except Exception as e:
                print(f"  click_id({sel}) err: {e}")
            return False

        async def open_submenu(toggle_sel: str):
            """Abre un dropdown (si no está abierto ya)."""
            try:
                await page.locator(toggle_sel).first.click(force=True)
                await page.wait_for_timeout(600)
            except Exception: pass

        # ─── 00_intro (0-10.8s): home con datos cargados, pequeño pan ───
        await until("00_intro")
        await page.wait_for_timeout(1200)
        try:
            await page.mouse.wheel(0, 200); await page.wait_for_timeout(1800)
            await page.mouse.wheel(0, -200); await page.wait_for_timeout(1500)
        except Exception: pass

        # ─── 01_csv (12.2-26.3s): hover importar + scroll por fichas ───
        await close_any_modal()
        await until("01_csv")
        try:
            btn = page.locator('#btnImport').first
            if await btn.count():
                await btn.scroll_into_view_if_needed()
                await btn.hover(); await page.wait_for_timeout(1800)
            for dy in [220, 220, 220, -660]:
                await page.mouse.wheel(0, dy); await page.wait_for_timeout(1600)
        except Exception as e: print(f"  csv err: {e}")

        # ─── 02_dia (27.7-41.6s): columna derecha totales / FPs ───
        await close_any_modal()
        await until("02_dia")
        try:
            await page.evaluate("document.querySelector('#sumBox')?.scrollIntoView({block:'center'})")
            await page.wait_for_timeout(1500)
            await page.mouse.move(1300, 420); await page.wait_for_timeout(1200)
            await page.mouse.move(1300, 500); await page.wait_for_timeout(1200)
            await page.mouse.move(1300, 300); await page.wait_for_timeout(1200)
            await page.mouse.wheel(0, 350); await page.wait_for_timeout(1500)
            await page.mouse.wheel(0, -350); await page.wait_for_timeout(1500)
        except Exception as e: print(f"  dia err: {e}")

        # ─── 03_stats (43.0-57.6s): Facturación → Autoescuelas → Tráfico ───
        # Narración: "facturación mensual y anual, trámites de Tráfico por grupo,
        # pacientes derivados de cada autoescuela y comparativas año actual..."
        await close_any_modal()
        await until("03_stats")
        try:
            # 1) Facturación mensual/anual al principio (narración empieza por aquí)
            await page.evaluate("document.querySelector('#btnStatFacMensual')?.click()")
            await page.wait_for_timeout(3200)
            # Pequeño scroll para enseñar los KPIs y la tabla mensual
            await page.evaluate("document.querySelector('.modal-back .modal')?.scrollBy(0, 220)")
            await page.wait_for_timeout(2000)
            await page.evaluate("document.querySelector('.modal-back .modal')?.scrollBy(0, 200)")
            await page.wait_for_timeout(1800)
            # 2) Cerrar y abrir Autoescuelas (con comparativas)
            await close_any_modal()
            await page.evaluate("document.querySelector('#btnStatAutoescolas')?.click()")
            await page.wait_for_timeout(2600)
            await page.evaluate("document.querySelector('#stBody')?.scrollBy(0, 120)")
            await page.wait_for_timeout(1500)
            # 3) Cambiar a Tráfico usando el switcher interno
            await page.evaluate("document.querySelector('#stSectionSwitch [data-section=\"traffic\"]')?.click()")
            await page.wait_for_timeout(2000)
            await page.evaluate("document.querySelector('#stBody')?.scrollBy(0, 150)")
            await page.wait_for_timeout(1200)
        except Exception as e: print(f"  stats err: {e}")

        # ─── 04_sms (59.0-73.7s): cambiar a sección SMS en el mismo modal ───
        await until("04_sms")
        try:
            visible = await page.evaluate("!!document.querySelector('.stats-modal')")
            if not visible:
                await close_any_modal()
                await page.evaluate("document.querySelector('#btnStatSms')?.click()")
            else:
                await page.evaluate("document.querySelector('#stSectionSwitch [data-section=\"sms\"]')?.click()")
            await page.wait_for_timeout(2800)
            await page.evaluate("document.querySelector('#stBody')?.scrollBy(0, 180)")
            await page.wait_for_timeout(2600)
            await page.evaluate("document.querySelector('#stBody')?.scrollBy(0, 220)")
            await page.wait_for_timeout(2500)
            await page.evaluate("document.querySelector('#stBody')?.scrollBy(0, -400)")
            await page.wait_for_timeout(1800)
        except Exception as e: print(f"  sms err: {e}")

        # ─── 05_audit (75.1-86.9s): cerrar stats y abrir Auditoría con datos ───
        await close_any_modal()
        await until("05_audit")
        try:
            await page.evaluate("document.querySelector('#btnAudit')?.click()")
            await page.wait_for_timeout(1200)
            # Rango por defecto es "hoy" → poner "3 meses" para que entren los
            # casos sembrados (ANNA, LAURA, JORDI, CARMEN, XAVIER). Narración dice
            # "mirando hasta tres meses atrás" → aquí visualmente coincide.
            await page.evaluate("document.querySelector('[data-preset=\"3m\"]')?.click()")
            await page.wait_for_timeout(1500)
            # Pestaña "Duplicado / Interrumpido" (2 casos: ANNA, CARMEN) — se
            # corresponde con la palabra "interrumpidos" de la narración.
            await page.evaluate("document.querySelector('[data-tab=\"dup_interrumpido\"]')?.click()")
            await page.wait_for_timeout(2000)
            await page.evaluate("document.querySelector('#auBody')?.scrollBy(0, 160)")
            await page.wait_for_timeout(1300)
            # Pestaña "Duplicado seguro" (2 casos: LAURA, JORDI) — palabra "duplicados".
            await page.evaluate("document.querySelector('[data-tab=\"dup_seguro\"]')?.click()")
            await page.wait_for_timeout(2200)
            await page.evaluate("document.querySelector('#auBody')?.scrollBy(0, 160)")
            await page.wait_for_timeout(1200)
            # Pestaña "Posible fallo (0€)" — palabra "posibles fallos con importe cero".
            await page.evaluate("document.querySelector('[data-tab=\"posible_fallo\"]')?.click()")
            await page.wait_for_timeout(1800)
        except Exception as e: print(f"  audit err: {e}")

        # ─── 06_outro (88.3-92.9s): zoom al logo ───
        await close_any_modal()
        await until("06_outro")
        try:
            await page.evaluate("window.scrollTo({top:0, behavior:'smooth'})")
            await page.wait_for_timeout(1500)
            await page.mouse.wheel(0, -2000); await page.wait_for_timeout(1500)
        except Exception: pass

        while asyncio.get_event_loop().time() - t0 < duration_target + 0.5:
            await asyncio.sleep(0.1)

        await context.close()
        await browser.close()

    webm = sorted(out_webm_dir.glob("*.webm"), key=lambda p: p.stat().st_mtime)[-1]
    print(f"[rec] webm: {webm}")
    return webm


def merge(webm: Path, audio: Path):
    out_mp4 = OUT_DIR / "medicar_demo.mp4"
    print(f"[merge] → {out_mp4} (trim preroll {PREROLL_SEC}s)")
    # El webm empieza a grabar antes de que arranque el reloj t0 (el browser
    # tarda ~3.5s en pintar la UI). Recortamos ese preroll para que coincida
    # con el audio, que empieza en 0.
    subprocess.run([
        "ffmpeg","-y",
        "-ss",str(PREROLL_SEC),"-i",str(webm),
        "-i",str(audio),
        "-c:v","libx264","-crf","23","-preset","fast","-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","128k",
        "-map","0:v:0","-map","1:a:0","-shortest","-movflags","+faststart",
        str(out_mp4)
    ], check=True, capture_output=True)
    size_mb = out_mp4.stat().st_size / 1024 / 1024
    print(f"[merge] MP4 listo: {out_mp4} ({size_mb:.1f} MB)")
    poster = OUT_DIR / "medicar_demo_poster.jpg"
    subprocess.run([
        "ffmpeg","-y","-ss","3","-i",str(out_mp4),
        "-frames:v","1","-q:v","3",str(poster)
    ], check=True, capture_output=True)
    print(f"[merge] poster: {poster}")

async def main():
    timeline, total = build_timeline()
    print(f"[plan] timeline:")
    for s, a, b in timeline: print(f"       {s}: {a:5.1f} → {b:5.1f}s")
    print(f"[plan] total: {total:.1f}s")
    audio_path, _ = concat_audio()
    webm = await record_screencast(total, timeline)
    merge(webm, audio_path)
    print("\n✅ Vídeo demo listo.")

if __name__ == "__main__":
    asyncio.run(main())
