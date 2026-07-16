"""
Electron source manifest endpoint.
----------------------------------
Serveix un JSON amb SHA-256 + mida de cada fitxer font que sync.js necessita.
Els builds locals validen aquest hash ABANS de sobreescriure els fitxers locals,
eliminant la possibilitat que una resposta HTML 404 (o qualsevol contingut incorrecte)
acabi al disc i corrompi la build.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import hashlib
from datetime import datetime, timezone

ELECTRON_SRC_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "public" / "downloads" / "electron-src"

# Fitxers que sync.js baixa. Han d'existir SEMPRE al servidor.
TRACKED_FILES = ["index.html", "main.js", "preload.js", "sync.js", "package.json"]

# Fitxers auxiliars del sistema bulletproof (scripts locals)
AUX_FILES = ["validate-local.js", "smoke-test.js", "publish-safe.ps1"]

# Signatures de contingut: cada fitxer HA de contenir aquests strings.
# Si en falta algun, considerem el fitxer corrupte i NO l'incloem al manifest.
CONTENT_SIGNATURES = {
    "index.html":   ["MediCar Plus"],
    "main.js":      ["require('electron')", "BrowserWindow"],
    "preload.js":   ["contextBridge"],
    "sync.js":      ["DISCOVERY_SOURCES", "SIGNATURES"],
    "package.json": ['"name"', '"version"'],
}


def _hash_file(path: Path) -> dict:
    data = path.read_bytes()
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
    }


router = APIRouter()


@router.get("/electron/manifest")
async def electron_manifest():
    """Retorna hashes + mides dels fitxers font Electron. Si algun està corrupte,
    l'omet del manifest (sync.js el detectarà i no sobreescriurà el local)."""
    if not ELECTRON_SRC_DIR.exists():
        raise HTTPException(status_code=503, detail="electron source directory missing")

    files_info = {}
    errors = []
    for name in TRACKED_FILES:
        p = ELECTRON_SRC_DIR / name
        if not p.exists():
            errors.append(f"{name}: missing on server")
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            errors.append(f"{name}: read error ({e})")
            continue
        # Signatura de contingut — no serveix un fitxer que no és el que hauria de ser
        for sig in CONTENT_SIGNATURES.get(name, []):
            if sig not in text:
                errors.append(f"{name}: signature missing ({sig!r})")
                break
        else:
            files_info[name] = _hash_file(p)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "server_ok": len(errors) == 0,
        "errors": errors,
        "files": files_info,
    }


# ============================================================================
# DOWNLOAD endpoints — RUTA API que bypassa qualsevol bot-detection de Cloudflare
# sobre fitxers estàtics. Serveix el mateix contingut que /downloads/electron-src/
# però via ruta /api/ que no aplica les mateixes regles.
# ============================================================================

# Fitxers permesos per baixar (whitelist estricta)
ALLOWED_DOWNLOADS = set(TRACKED_FILES) | set(AUX_FILES)


@router.get("/electron/download/{filename}")
async def electron_download(filename: str):
    """Serveix qualsevol fitxer permès des de electron-src/ com attachment."""
    if filename not in ALLOWED_DOWNLOADS:
        raise HTTPException(status_code=404, detail="file not allowed")
    p = ELECTRON_SRC_DIR / filename
    if not p.exists():
        raise HTTPException(status_code=404, detail="file not found")
    # Content-type explícit per evitar sniffing rar
    ctype_map = {
        ".js": "application/javascript",
        ".json": "application/json",
        ".html": "text/html",
        ".ps1": "text/plain",
    }
    ext = p.suffix.lower()
    ctype = ctype_map.get(ext, "application/octet-stream")
    return FileResponse(p, media_type=ctype, filename=filename, headers={
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "X-Content-Type-Options": "nosniff",
    })
