# 🚀 MediCar Plus · Guía de Migración TEST → LIVE (Stripe + Producción)

> **Creado**: 30-Jul-2026 · **Autor**: E1 (agente) · Solicitado por Marc Brugulat
> **Objetivo**: cuando la cuenta Stripe LIVE esté activa (previsión ~Oct 2026), tener un checklist blindado para pasar de TEST a LIVE sin perder ningún detalle.

---

## 📸 Estado ACTUAL (test · Julio 2026) — congelado para referencia

### Stripe (cuenta test)
- **Cuenta**: `Entorno de prueba de MediCarPlus` (ES)
- **API key**: `sk_test_51Tq...` (en `/app/backend/.env` como `STRIPE_API_KEY`)
- **Webhook secret**: `whsec_s46odS...` (`STRIPE_WEBHOOK_SECRET`)
- **Endpoint webhook Stripe → nuestro backend**: `https://project-helper-47.emergent.host/api/webhook/stripe`
- **Prices activos (TEST)**:
  | Variable | Price ID | Plan | Recurrencia | Importe |
  |----------|----------|------|-------------|---------|
  | `STRIPE_PRICE_STD_MES` | `price_1Tqx9iDICdnmKtZ3j0kwOfIH` | Standard | mensual | 29,90 € |
  | `STRIPE_PRICE_STD_ANY` | `price_1TqxAZDICdnmKtZ3qmcp1Mf0` | Standard | anual | 299,90 € |
  | `STRIPE_PRICE_PREMIUM_MES` | `price_1TqxC3DICdnmKtZ3HvDPBovI` | Premium | mensual | 39,90 € |
  | `STRIPE_PRICE_PREMIUM_ANY` | `price_1TqxCTDICdnmKtZ30Tahx798` | Premium | anual | 399,90 € |

### Configuración Stripe Dashboard (test) — activada por Marc el 30-Jul-2026
En **https://dashboard.stripe.com/test/settings/emails** (sección Empresa → Correos electrónicos de clientes):
- ✅ **Pagos que se han efectuado correctamente** (envía factura + PDF al cliente tras cada cobro)
- ✅ **Reembolsos** (email de confirmación)
- ⚠️ **Pendiente por Marc**: revisar en **Billing → Automations** los toggles de:
  - ✅ Email al cliente cuando falle un pago
  - ✅ Smart Retries (reintentar ~3 semanas)
  - ✅ Recordatorio pre-renovación (opcional, 3-7 días antes)
  - ✅ Cancelación automática tras N reintentos fallidos

### Backend (nuestro código · ya funciona en TEST)
- ✅ Webhook `invoice.paid` → renueva `expires_at` de la licencia + suma a `total_paid_cents`
- ✅ Webhook `invoice.payment_failed` → marca `payment_health=red` + email admin (`info@medicarplus.es`) + notificación crítica en el feed
- ✅ Webhook `customer.subscription.updated` → detecta upgrade/downgrade y crea notificación en feed
- ✅ Webhook `customer.subscription.deleted` → notificación cancelación
- ✅ Idempotencia por `dedupe_key` en `notifications` y `admin_notified_*` en `payments`
- ✅ Emails al admin vía SMTP IONOS (`SMTP_*` en `.env`)
- ✅ Panel admin con badge pulsante rojo cuando hay críticas sin leer
- ✅ Auto-renovación validada E2E: mensual (+30d) y anual (+365d) en `tests/test_stripe_autorenewal_e2e.py`

### 🎯 Lo que ya funciona bien y NO hay que tocar
- Backend en producción: `https://project-helper-47.emergent.host` (deployed vía Emergent)
- Frontend `.exe` Electron apunta a producción vía `API_BASE_HARDCODED` en `v2.html`
- Panel admin en `/admin.html` con login `ADMINISTRADOR` / password + token JWT
- Base de datos MongoDB: colecciones `licenses`, `subscriptions`, `payments`, `installations`, `notifications`, `admin_users`, `audit_logs`

---

## 🚦 Cuándo hacer el switch a LIVE

**Precondiciones (a comprobar por Marc)**:
- [ ] Datos fiscales listos: NIF, CIF (si sociedad), dirección fiscal ES, IBAN cuenta bancaria
- [ ] Al menos 1 cliente beta real dispuesto a hacer el primer cobro real (mejor 3-5)
- [ ] Cuenta Stripe LIVE **verificada** (Stripe tarda 24-72h en aprobar)
- [ ] Backup completo de MongoDB del día D (por si algo va mal, poder volver atrás)

**Momento estimado**: ~Oct-Nov 2026 (a confirmar por Marc).

---

## 📋 Checklist Migración TEST → LIVE (paso a paso)

### Fase 1 · Preparación (5-7 días antes)
1. [ ] **Marc activa cuenta LIVE en Stripe** desde el botón "Cambiar a la cuenta activa"
   - Sube documentación fiscal
   - Configura IBAN de cobro
   - Espera aprobación (24-72h)
2. [ ] Backup DB producción: `mongodump --uri="$MONGO_URL" --db="$DB_NAME" --out=/backup/pre-live-$(date +%Y%m%d)`
3. [ ] Confirmar que todos los emails admin llegan bien (info@medicarplus.es no está lleno, filtros OK)

### Fase 2 · Configuración Stripe LIVE (día del switch)
4. [ ] **Crear los 4 productos en Stripe LIVE** (Dashboard → Product catalog):
   - `MediCar Plus Standard Mensual` — 29,90 € / mes recurring
   - `MediCar Plus Standard Anual` — 299,90 € / año recurring
   - `MediCar Plus Premium Mensual` — 39,90 € / mes recurring
   - `MediCar Plus Premium Anual` — 399,90 € / año recurring
   - Copiar los 4 nuevos `price_id` (empiezan por `price_1...` sin `Tqx` que era test)
5. [ ] **Activar los mismos emails en LIVE** (https://dashboard.stripe.com/settings/emails):
   - ✅ Pagos correctos · ✅ Reembolsos · ✅ Pagos fallidos · ✅ Smart Retries
   - Cambiar **Idioma predeterminado** a `Spanish (Spain)`
6. [ ] **Crear webhook endpoint LIVE** (Dashboard → Developers → Webhooks):
   - URL: `https://project-helper-47.emergent.host/api/webhook/stripe`
   - Eventos a suscribir (mismos que test):
     - `checkout.session.completed`
     - `customer.subscription.created`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
     - `invoice.paid`
     - `invoice.payment_failed`
   - Copiar el nuevo `whsec_...` (será distinto al de test)
7. [ ] **API keys LIVE**: Developers → API keys
   - Copiar `pk_live_...` y `sk_live_...`

### Fase 3 · Deploy backend con claves LIVE
8. [ ] Actualizar `/app/backend/.env` **SOLO EN PRODUCCIÓN** (mantener test en preview):
   ```env
   STRIPE_API_KEY=sk_live_51...
   STRIPE_WEBHOOK_SECRET=whsec_LIVE...
   STRIPE_PRICE_STD_MES=price_LIVE_std_mes
   STRIPE_PRICE_STD_ANY=price_LIVE_std_any
   STRIPE_PRICE_PREMIUM_MES=price_LIVE_premium_mes
   STRIPE_PRICE_PREMIUM_ANY=price_LIVE_premium_any
   ```
9. [ ] **Deploy en Emergent** (pulsar "Deploy" en la UI)
10. [ ] Verificar reinicio del backend: `curl https://project-helper-47.emergent.host/api/` → 200 OK

### Fase 4 · Verificación E2E con dinero real
11. [ ] **Primer cobro real** con Marc como cliente beta:
    - Ir a landing → elegir plan Standard Mensual (29,90 €)
    - Pagar con tarjeta real
    - Verificar:
      - [ ] Email de factura llega al cliente (Stripe automático)
      - [ ] Email admin de "nuevo cliente" llega a `info@medicarplus.es`
      - [ ] Panel admin muestra la licencia en verde
      - [ ] Notificación en el feed (`💰 Pago recibido`)
      - [ ] Dinero visible en Stripe Dashboard → Balance
12. [ ] **Test tarjeta rechazada** (usar tarjeta `4000 0000 0000 9995` NO — esa es de test):
    - En LIVE se prueba forzando un fallo con una tarjeta con saldo insuficiente
    - Verificar que:
      - [ ] Email al cliente pidiendo actualizar tarjeta
      - [ ] Email admin crítico + badge rojo pulsante en panel
      - [ ] Feed muestra `🚨 Pago fallido URGENTE`
13. [ ] **Verificar Smart Retries**: dejar que Stripe reintente automáticamente. Confirmar que si el cliente actualiza tarjeta, la suscripción vuelve a verde y el feed muestra `✅ Pago recuperado`.

### Fase 5 · Post-migración
14. [ ] **Migrar clientes de test a live**: si hubo clientes reales en test (no debería haberlos, pero por si acaso), reactivarles la suscripción en LIVE manualmente.
15. [ ] Actualizar la landing page → botones apuntan a los precios LIVE
16. [ ] Comunicar a clientes beta que ya está en modo real
17. [ ] Mantener durante 1 mes ambos modos operativos (preview con test, prod con live) para poder testear cambios sin afectar producción

---

## 🇪🇸 Verifactu (aplicación posterior · 2027)

Cuando llegue el momento de cumplir con Verifactu (obligatorio en España a partir de 2026-2027):

1. [ ] En Stripe Dashboard → **Tax → Registrations** → añadir registro fiscal español
2. [ ] Activar "Automatic tax collection" en la cuenta
3. [ ] Stripe registrará automáticamente cada factura en la AEAT
4. [ ] Verificar que el email al cliente incluye el **código Verifactu** en el PDF de factura
5. [ ] Nuestro backend NO necesita cambios (Stripe lo gestiona todo)

**Referencias oficiales**:
- Stripe España Verifactu: https://stripe.com/es/legal/verifactu
- AEAT Verifactu: https://sede.agenciatributaria.gob.es/Sede/verifactu.html

---

## ⚠️ Cosas que NO hay que olvidar

### 🔴 No confundir preview y producción
- **Preview** (dev de agente): `https://project-helper-47.preview.emergentagent.com` → sigue en TEST siempre
- **Producción** (cliente `.exe`): `https://project-helper-47.emergent.host` → aquí es donde pasará a LIVE
- El `.exe` apunta 100% a producción (hardcoded en `v2.html::API_BASE_HARDCODED`)

### 🔴 Los install_id y clientes en TEST NO se copian a LIVE
Cuando migres, todos los clientes que empezaron en test seguirán ahí (sus suscripciones son de test). Los clientes reales empezarán su suscripción desde cero en LIVE. Si Marc quiere migrar 1-2 clientes específicos, hay que:
1. Cancelar su sub de test manualmente
2. Recrearla en LIVE con el mismo email
3. Nuestro webhook `invoice.paid` en LIVE creará una license nueva ligada al install_id existente (si es el mismo PC)

### 🔴 Prices IDs distintos entre TEST y LIVE
Cada `price_id` de test **NO existe** en LIVE. Hay que crear productos nuevos en Stripe LIVE. Los importes pueden ser los mismos.

### 🔴 Webhook secret DIFERENTE
El `whsec_...` de test **no valida** eventos live. Hay que generar uno nuevo en el endpoint LIVE de webhooks.

### 🔴 Emails admin no se duplican
Nuestro sistema envía a `info@medicarplus.es` independientemente de test/live. Cuando estés en LIVE, los emails serán de cobros reales — no ignorar ningún fallo.

---

## 📞 Contactos y recursos

- **Stripe Support ES**: https://support.stripe.com/contact/email (respuesta 24h)
- **Stripe status**: https://status.stripe.com (comprobar antes de reportar bugs)
- **Nuestro webhook logs**: en Emergent Dashboard → Logs, filtrar por `[stripe]`
- **Backup DB command**: `mongodump --uri="$MONGO_URL" --db="$DB_NAME" --out=/backup/YYYYMMDD`

---

## ✅ Firma de aceptación

Cuando completes esta migración, actualiza este archivo con:
- Fecha del switch
- Hora del primer cobro real
- Cliente beta que hizo el primer cobro (nombre + email)
- Cualquier fricción encontrada

---

*Fin de la guía · Última actualización: 30-Jul-2026*
