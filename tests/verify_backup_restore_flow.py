import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright, expect


APP_URL = "https://project-helper-47.preview.emergentagent.com/v2.html"
OUT_DIR = Path("/app/test_reports/artifacts/backup_restore")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MASTER_LICENSE = {
    "key": "MB-MASTER-BRUGULAT-2026-OWNER",
    "install_id": "CD-MASTER-TEST",
    "type": "MASTER",
    "plan": "MASTER",
    "centre": "MediCar Plus (owner)",
    "expires": "PERMANENT",
    "activated": "2026-07-01T00:00:00.000Z",
    "installId": "CD-MASTER-TEST",
}

CONFIG = {
    "configured": True,
    "company1": {"name": "Empresa Test"},
    "company2": {"name": "Empresa 2 Test"},
    "partners": [],
}

DATA_KEYS = [
    "caja.v1",
    "caja.cempla.v1",
    "caja.stats.v1",
    "caja.irpf.v1",
    "caja.datafono",
    "caja.cempla.datafono",
]


def original_dataset():
    return {
        "caja.v1": {
            "byDate": {
                "2026-07-15": [
                    {
                        "id": "traf-001",
                        "kind": "TRAF",
                        "tipo": "B",
                        "grupo": "AUTO TEST",
                        "nombre": "Cliente Tráfico Original",
                        "importe": 42.5,
                        "descuento": 0,
                        "tasa": 24.58,
                        "fp": "E",
                        "fpTasa": "T",
                        "retorno": False,
                    },
                    {
                        "id": "traf-002",
                        "kind": "PRIV",
                        "tipo": "Psicotécnico",
                        "grupo": "-",
                        "nombre": "Cliente Privado Original",
                        "importe": 55,
                        "descuento": 5,
                        "tasa": 0,
                        "fp": "B",
                        "fpTasa": "B",
                        "retorno": False,
                    },
                ]
            }
        },
        "caja.cempla.v1": {
            "byDate": {
                "2026-07-16": [
                    {
                        "id": "cem-001",
                        "kind": "PRIV",
                        "tipo": "Revisión deportiva",
                        "grupo": "-",
                        "nombre": "Deportista Original",
                        "importe": 35,
                        "descuento": 0,
                        "tasa": 0,
                        "fp": "T",
                        "fpTasa": "T",
                        "split": "45-45-10",
                        "retorno": False,
                    }
                ]
            }
        },
        "caja.datafono": {"2026-07-15": 91.08},
        "caja.cempla.datafono": {"2026-07-16": 35},
        "caja.stats.v1": {
            "autoescoles": ["Autoescuela Norte", "Autoescuela Sur"],
            "data": {
                "2026-07": {
                    "Autoescuela Norte": {"certificados": 11, "importe": 330},
                    "Autoescuela Sur": {"certificados": 7, "importe": 210},
                }
            },
        },
        "caja.irpf.v1": {
            "months": {
                "2026-07": {
                    "personas": 3,
                    "bruto": 3000,
                    "retencion": 450,
                    "empresa": "Empresa Test",
                }
            },
            "quarters": {"2026-Q3": {"amount": 450, "paid": False}},
        },
    }


def different_dataset():
    return {
        "caja.v1": {"byDate": {"2026-01-01": [{"id": "old-traf", "nombre": "NO DEBE QUEDAR", "importe": 1, "tasa": 0, "kind": "TRAF", "fp": "E"}]}},
        "caja.cempla.v1": {"byDate": {"2026-01-02": [{"id": "old-cem", "nombre": "NO DEBE QUEDAR 2", "importe": 2, "kind": "PRIV", "fp": "E"}]}},
        "caja.stats.v1": {"autoescoles": ["Vieja"], "data": {"2025-01": {"Vieja": {"certificados": 1}}}},
        "caja.irpf.v1": {"months": {"2025-01": {"personas": 1}}, "quarters": {}},
        "caja.datafono": {"2026-01-01": 1},
        "caja.cempla.datafono": {"2026-01-02": 2},
    }


def signed_backup_from_dataset(dataset):
    return {
        "_signature": "MEDICAR-PLUS-BACKUP-V4",
        "_createdAt": "2026-07-28T10:00:00.000Z",
        "_appVersion": "qa-test",
        "cbTrafic": dataset["caja.v1"],
        "cempla": dataset["caja.cempla.v1"],
        "datafono": dataset["caja.datafono"],
        "datafonoCempla": dataset["caja.cempla.datafono"],
        "stats": dataset["caja.stats.v1"],
        "irpf": dataset["caja.irpf.v1"],
        "_v": 4,
    }


async def setup_page(page):
    await page.set_viewport_size({"width": 1920, "height": 1080})
    await page.add_init_script(
        """
        (() => {
          try { Object.defineProperty(window, 'showSaveFilePicker', { value: undefined, configurable: true }); } catch(e) { window.showSaveFilePicker = undefined; }
          localStorage.clear();
          localStorage.setItem('caja.lang', 'es');
          localStorage.setItem('caja.install.id.v1', 'CD-MASTER-TEST');
          localStorage.setItem('caja.license.v1', JSON.stringify(%s));
          localStorage.setItem('caja.license.v3', JSON.stringify(%s));
          localStorage.setItem('caja.license.lastcheck.v1', String(Date.now()));
          localStorage.setItem('caja.config.v1', JSON.stringify(%s));
          localStorage.setItem('caja.company', 'trafic');
        })();
        """
        % (json.dumps(MASTER_LICENSE), json.dumps(MASTER_LICENSE), json.dumps(CONFIG))
    )
    await page.goto(APP_URL, wait_until="domcontentloaded")
    await expect(page.locator('[data-testid="app-title"]')).to_be_visible(timeout=15000)
    await expect(page.locator('[data-testid="btn-backup"]')).to_be_visible(timeout=15000)
    # If activation or setup overlays unexpectedly appear, fail early with visible text.
    visible_text = await page.locator("body").inner_text(timeout=5000)
    assert "Activación de licencia" not in visible_text, "License modal was not bypassed"
    assert "Configuración" not in visible_text or "Copias de seguridad" in visible_text, "Configuration wizard may not be bypassed"


async def seed_dataset(page, dataset):
    await page.evaluate(
        """({dataset, keys}) => {
          for (const k of keys) localStorage.removeItem(k);
          for (const [k, v] of Object.entries(dataset)) localStorage.setItem(k, JSON.stringify(v));
          localStorage.setItem('caja.company', 'trafic');
        }""",
        {"dataset": dataset, "keys": DATA_KEYS},
    )


async def get_data_snapshot(page, include_all=False):
    if include_all:
        return await page.evaluate("""() => Object.fromEntries(Object.keys(localStorage).sort().map(k => [k, localStorage.getItem(k)]))""")
    return await page.evaluate(
        """keys => Object.fromEntries(keys.map(k => [k, localStorage.getItem(k)]))""",
        DATA_KEYS,
    )


async def get_parsed_data(page):
    return await page.evaluate(
        """keys => Object.fromEntries(keys.map(k => [k, JSON.parse(localStorage.getItem(k) || 'null')]))""",
        DATA_KEYS,
    )


async def click_backup_menu_item(page, testid):
    await page.locator('[data-testid="btn-backup"]').click()
    await page.wait_for_timeout(200)
    await page.locator(f'[data-testid="{testid}"]').click()


async def upload_json(page, path: Path):
    await page.locator("#jsonInput").set_input_files(str(path))
    await page.wait_for_timeout(700)


async def toast_text(page):
    return await page.evaluate(
        """() => Array.from(document.querySelectorAll('.toast')).map(t => t.textContent).join('\\n')"""
    )


async def dismiss_all_modals(page):
    await page.evaluate("""() => document.querySelectorAll('.modal-back').forEach(e => e.remove())""")


async def main():
    results = []
    async with async_playwright() as p:
        executable = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE") or "/root/bin/chromium"
        browser = await p.chromium.launch(headless=True, executable_path=executable if Path(executable).exists() else None)
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()
        page.on("console", lambda msg: print(f"BROWSER CONSOLE {msg.type}: {msg.text}"))
        await setup_page(page)

        original = original_dataset()
        await seed_dataset(page, original)

        # 1) Save backup through the real UI, verify filename, JSON signature, and Windows red-X explanation modal.
        async with page.expect_download(timeout=15000) as download_info:
            await click_backup_menu_item(page, "btn-save-backup")
        download = await download_info.value
        suggested = download.suggested_filename
        download_path = OUT_DIR / suggested
        await download.save_as(str(download_path))
        assert re.fullmatch(r"medicar_copia_\d{4}-\d{2}-\d{2}\.json", suggested), f"Unexpected backup filename: {suggested}"
        exported = json.loads(download_path.read_text(encoding="utf-8"))
        assert exported.get("_signature") == "MEDICAR-PLUS-BACKUP-V4", "Exported JSON missing backup signature"
        assert exported.get("_createdAt"), "Exported JSON missing _createdAt"
        datetime.fromisoformat(exported["_createdAt"].replace("Z", "+00:00"))
        await expect(page.locator('[data-testid="backup-info-ok"]')).to_be_visible(timeout=5000)
        modal_text = await page.locator(".modal-back .modal").last.inner_text()
        assert "crucecita roja" in modal_text, "Post-save modal does not mention Windows red X/crucecita roja"
        assert "NORMAL" in modal_text, "Post-save modal does not clearly say the Windows icon issue is normal"
        assert "firmado internamente" in modal_text, "Post-save modal does not mention internal signature"
        assert "Restaurar copia" in modal_text, "Post-save modal does not instruct how to restore"
        await page.locator('[data-testid="backup-info-ok"]').click()
        results.append("save_backup_export_and_red_x_modal_ok")

        # 2) Security-critical unknown JSON must be rejected and must not touch localStorage.
        await seed_dataset(page, original)
        before_unknown_all = await get_data_snapshot(page, include_all=True)
        before_unknown_data = await get_data_snapshot(page, include_all=False)
        unknown_path = OUT_DIR / "unknown.json"
        unknown_path.write_text(json.dumps({"randomKey": "value"}), encoding="utf-8")
        await upload_json(page, unknown_path)
        unknown_toast = await toast_text(page)
        after_unknown_all = await get_data_snapshot(page, include_all=True)
        after_unknown_data = await get_data_snapshot(page, include_all=False)
        if before_unknown_all != after_unknown_all:
            changed = sorted(set(before_unknown_all) | set(after_unknown_all))
            diff_keys = [k for k in changed if before_unknown_all.get(k) != after_unknown_all.get(k)]
            print("Unknown JSON localStorage diff keys:", diff_keys)
        assert "❌ Archivo no reconocido como copia de MediCar Plus. No se tocará ningún dato." in unknown_toast, unknown_toast
        assert before_unknown_data == after_unknown_data, "Unknown JSON modified protected data localStorage keys"
        results.append("unknown_json_rejected_without_localstorage_changes_ok")

        # 3) Malformed JSON must be rejected without modifying data.
        await seed_dataset(page, original)
        before_bad = await get_data_snapshot(page, include_all=False)
        bad_path = OUT_DIR / "malformed.json"
        bad_path.write_text("not-json-content", encoding="utf-8")
        await upload_json(page, bad_path)
        bad_toast = await toast_text(page)
        after_bad = await get_data_snapshot(page, include_all=False)
        assert "❌ El archivo no es un JSON válido" in bad_toast, bad_toast
        assert before_bad == after_bad, "Malformed JSON modified protected data localStorage keys"
        results.append("malformed_json_rejected_without_localstorage_changes_ok")

        # 4) Valid signed restore: confirmation modal in Spanish, contents listed, Reemplazar todo restores all keys.
        await seed_dataset(page, different_dataset())
        signed_path = OUT_DIR / "valid_signed_backup.json"
        signed_path.write_text(json.dumps(signed_backup_from_dataset(original), ensure_ascii=False, indent=2), encoding="utf-8")
        await upload_json(page, signed_path)
        modal = page.locator(".modal-back .modal").last
        await expect(modal).to_be_visible(timeout=5000)
        signed_modal_text = await modal.inner_text()
        assert "Restaurar copia completa" in signed_modal_text, signed_modal_text
        assert "2 fichas Tráfico" in signed_modal_text, signed_modal_text
        assert "1 fichas Empresa 2 Test" in signed_modal_text, signed_modal_text
        assert "1 meses de estadísticas" in signed_modal_text, signed_modal_text
        assert "Reemplazar todo" in signed_modal_text and "Fusionar" in signed_modal_text, signed_modal_text
        await modal.locator("button", has_text="Reemplazar todo").click()
        await page.wait_for_timeout(700)
        restored = await get_parsed_data(page)
        for key, value in original.items():
            assert restored[key] == value, f"Signed restore mismatch for {key}: {restored[key]} != {value}"
        history = await page.evaluate("""() => JSON.parse(localStorage.getItem('caja.snapshots') || '[]')""")
        assert any(s.get("reason") == "preRestore" for s in history), "No preRestore snapshot created before restore"
        results.append("valid_signed_restore_replace_and_prerestore_snapshot_ok")

        # 5) Legacy old-format backup (only byDate, no signature) is still accepted and restorable.
        await seed_dataset(page, different_dataset())
        legacy_obj = {
            "byDate": {
                "2026-07-20": [
                    {"id": "legacy-001", "kind": "TRAF", "tipo": "A", "nombre": "Cliente Legacy", "importe": 12, "tasa": 3, "fp": "E", "fpTasa": "E", "retorno": False}
                ]
            }
        }
        legacy_path = OUT_DIR / "legacy_bydate_backup.json"
        legacy_path.write_text(json.dumps(legacy_obj, ensure_ascii=False), encoding="utf-8")
        await upload_json(page, legacy_path)
        legacy_modal = page.locator(".modal-back .modal").last
        await expect(legacy_modal).to_be_visible(timeout=5000)
        legacy_text = await legacy_modal.inner_text()
        assert "Restaurar copia completa" in legacy_text, legacy_text
        assert "1 fichas (individual)" in legacy_text, legacy_text
        await legacy_modal.locator("button", has_text="Reemplazar todo").click()
        await page.wait_for_timeout(700)
        legacy_restored = await get_parsed_data(page)
        assert legacy_restored["caja.v1"] == legacy_obj, f"Legacy restore did not replace current company data: {legacy_restored['caja.v1']}"
        results.append("legacy_bydate_restore_backwards_compatible_ok")

        # 6) Round trip: exported file restores into an empty/different session and all exported data keys match original.
        await seed_dataset(page, {k: {"byDate": {}} if k.endswith("v1") and k in ("caja.v1", "caja.cempla.v1") else ({} if "datafono" in k else ({"autoescoles": [], "data": {}} if k == "caja.stats.v1" else {"months": {}, "quarters": {}})) for k in DATA_KEYS})
        await upload_json(page, download_path)
        rt_modal = page.locator(".modal-back .modal").last
        await expect(rt_modal).to_be_visible(timeout=5000)
        await rt_modal.locator("button", has_text="Reemplazar todo").click()
        await page.wait_for_timeout(700)
        roundtrip_restored = await get_parsed_data(page)
        expected_from_download = {
            "caja.v1": exported["cbTrafic"],
            "caja.cempla.v1": exported["cempla"],
            "caja.stats.v1": exported["stats"],
            "caja.irpf.v1": exported["irpf"],
            "caja.datafono": exported["datafono"],
            "caja.cempla.datafono": exported["datafonoCempla"],
        }
        assert roundtrip_restored == expected_from_download, "Round-trip restored data differs from exported backup"
        results.append("export_restore_roundtrip_data_integrity_ok")

        await context.close()
        await browser.close()

    print(json.dumps({"status": "passed", "results": results, "download": str(download_path)}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())