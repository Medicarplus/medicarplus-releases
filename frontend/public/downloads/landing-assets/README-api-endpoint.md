# Publish api-endpoint.json to medicarplus.es (GitHub Pages)

## Per què cal aquest fitxer?

Emergent (el servidor on corre el backend) rota les seves URLs de preview cada cert temps.
Sense aquest fitxer, cada cop que la URL canvia, TOTS els clients amb l'app instal·lada
tindrien el mòdul SMS / IA / Cites trencat fins que reinstal·lessin manualment.

Amb aquest fitxer publicat a `https://medicarplus.es/api-endpoint.json`:
- L'app Electron el consulta automàticament al iniciar-se (i quan detecta un 404).
- Si la URL del backend canvia, només cal editar el JSON i fer `git push`.
- Tots els clients agafen la nova URL automàticament (immediat o en màxim 24h).

## Com pujar-lo (primera vegada)

1. Ves al repo GitHub Pages de medicarplus.es (el que serveix la landing).
2. Copia el fitxer `api-endpoint.json` d'aquesta carpeta a l'arrel del repo.
3. Commit + push.
4. Verifica que respon: `curl https://medicarplus.es/api-endpoint.json`

## Com actualitzar-lo (si Emergent canvia la URL)

Edita `api-endpoint.json` al repo de medicarplus.es:

```json
{
  "api": "https://NOVA-URL-EMERGENT.preview.emergentagent.com",
  "updated": "2026-XX-XX"
}
```

Commit + push. Els clients es reajusten automàticament.

## Contingut actual

```json
{
  "api": "https://project-helper-47.preview.emergentagent.com",
  "updated": "2026-07-14"
}
```
