# Configuració SMTP/IMAP — MediCar Plus (IONOS)

## Domini
- `medicarplus.es` (comprat a IONOS, actiu)

## Correu principal
- `info@medicarplus.es` (Correo Profesional 50GB, 1 llicència)
- Contrasenya: **GUARDADA PER L'USUARI (no compartida)**

## SMTP (enviament sortint) — per backend `.env`
```
SMTP_HOST=smtp.ionos.es
SMTP_PORT=587
SMTP_TLS=true
SMTP_USER=info@medicarplus.es
SMTP_PASS=[pendent - a demanar quan implementem]
SMTP_FROM=info@medicarplus.es
```

## IMAP (lectura entrant) — opcional per lectura automàtica
```
IMAP_HOST=imap.ionos.es
IMAP_PORT=993
IMAP_SSL=true
IMAP_USER=info@medicarplus.es
```

## Ús previst
1. Enviament automàtic de la clau de llicència quan un client paga (via Stripe webhook)
2. Emails de benvinguda, renovació, avisos d'expiració
3. Notificacions internes al admin
4. Formulari de contacte de la landing page → arriba a `info@medicarplus.es`

## Integració necessària
Backend Python: usar `aiosmtplib` o `emails` library. La contrasenya s'entra al `.env` només al deploy final (no al preview).
