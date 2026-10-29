# Tramitación Lab · PROTOTIPO AISLADO

**AVISO IMPORTANTE**: esta carpeta es un prototipo visual **completamente separado** de MediCar Plus.
No comparte código, ni base de datos, ni se despliega con la app principal.

## Para qué sirve
Maqueta de un hipotético software propio de tramitación de certificados médicos (equivalente a GIC/ASDE
pero moderno). Pensado como "plan B" en caso de que ASDE bloquee la licencia o se quiera independizar.

## Cómo abrirlo
Doble click en `index.html` — se abre en el navegador. No necesita servidor, ni compilar, ni npm.
Todos los datos se guardan en `localStorage` del navegador (nada se envía a ninguna parte).

## Estado
- v0.1 (Feb 2026) · Primera plantilla con 2 temas (oscuro-dorado / blanco-médico), wizard completo
  Filiación → Trámite → Datos salud → Exploración → Dictamen → Firma y PDF.

## No tocar MediCar
Esta carpeta jamás debe importarse desde `/app/frontend/` ni `/app/backend/`. Si algún día se integra,
será una decisión explícita y planificada. De momento vive en paralelo.
