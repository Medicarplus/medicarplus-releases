#!/usr/bin/env bash
# ============================================================================
# MediCar Plus — Script de sincronització v1 → v2
# ============================================================================
# Uses:
#   ./sync_v1_to_v2.sh           # sync + obfusca (dev-ready)
#   ./sync_v1_to_v2.sh --release # sync + obfusca + intent de release GitHub
#
# Què fa:
#   1. Copia /app/frontend/public/caja_del_dia.html (v1) → /tmp/v2.working.html
#   2. Aplica les transformacions comercials automàticament:
#      · Rebranding: "Caja del Día" / "Caixa del Dia" → "MediCar Plus"
#      · Tab buttons: injecta <span data-cfg-name> per canvi dinàmic
#      · Buida preus dels chips ("(20€)", "data-preu=X", "data-split=X")
#      · Simplifica formulari cempla (elimina F.Brugulat/Cempla/Dr.Mellado)
#      · Simplifica applyCompanyUI() per usar CFG
#      · Simplifica renderCemplaSplit() (només total, sense repartiment)
#      · Injecta la capa comercial (llicència + wizard + ⚙️) abans de </body>
#   3. Còpia resultat a /app/frontend/public/v2.html
#   4. Sincronitza a /app/commercial/caja_del_dia_v2.html
#   5. Executa l'obfuscador → commercial/electron/index.html
#   6. Regenera el ZIP final
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")"

V1="/app/frontend/public/caja_del_dia.html"
V2="/app/frontend/public/v2.html"
V2_COPY="/app/commercial/caja_del_dia_v2.html"
ELECTRON_INDEX="/app/commercial/electron/index.html"
OVERLAY="/app/commercial/build/overlay.js"
ZIP_OUT="/app/commercial/caja_del_dia_electron.zip"
WORK="/tmp/v2.working.html"

if [ ! -f "$V1" ]; then
  echo "❌ v1 no trobada a $V1"; exit 1
fi
if [ ! -f "$OVERLAY" ]; then
  echo "❌ Overlay no trobada a $OVERLAY"; exit 1
fi

echo "🔄 [1/6] Copiant v1 → working copy"
cp "$V1" "$WORK"

echo "🏷️  [2/6] Aplicant rebranding a MediCar Plus"
sed -i 's/Caja del Día/MediCar Plus/g; s/Caja del Dia/MediCar Plus/g; s/Caixa del Dia/MediCar Plus/g; s/Caixa del Día/MediCar Plus/g' "$WORK"

echo "🎨 [3/6] Aplicant transformacions estructurals per multi-client"
# 3a) Tab buttons: envolta els noms amb <span data-cfg-name> per substitució dinàmica
sed -i 's|🚗 CEMPLA C\.B|🚗 <span data-cfg-name="1">Empresa 1</span>|g' "$WORK"
sed -i 's|🩺 CEMPLA ESPORT|🩺 <span data-cfg-name="2">Esport</span>|g' "$WORK"

# 3b) Chips: buidar preus (elimina data-preu, data-split i el text "(X€)")
python3 << 'PYEOF'
import re
p = '/tmp/v2.working.html'
with open(p) as f: h = f.read()
# Remove data-preu="..." and data-split="..." attributes
h = re.sub(r'\s*data-preu="[^"]*"', '', h)
h = re.sub(r'\s*data-split="[^"]*"', '', h)
# Remove "(20€)", "(40,50€)", etc. from chip labels
h = re.sub(r' \((\d+[.,]?\d*)€\)</span>', '</span>', h)
with open(p,'w') as f: f.write(h)
PYEOF

# 3c) applyCompanyUI: substitueix per la versió CFG-aware
python3 << 'PYEOF'
import re
p = '/tmp/v2.working.html'
with open(p) as f: h = f.read()
old_pattern = r"function applyCompanyUI\(\)\{const isC=currentCompany==='cempla';document\.body\.classList\.toggle\('cempla',isC\);\$\('#cTrafic'\)\.classList\.toggle\('active',!isC\);\$\('#cCempla'\)\.classList\.toggle\('active',isC\);\$\('#appTitle'\)\.firstChild\.nodeValue=isC\?'CEMPLA ESPORT ':'(?:Caja del Día|Caixa del Dia|MediCar Plus) ';\$\('#appSub'\)\.textContent=isC\?'Medicina esportiva · Revisions':'[^']*';"
new_code = "function applyCompanyUI(){const isC=currentCompany==='cempla';const c1=(window.CFG&&CFG.company1&&CFG.company1.name)||'Empresa';const c2=(window.CFG&&CFG.company2&&CFG.company2.name)||'Esport';document.body.classList.toggle('cempla',isC);$('#cTrafic').classList.toggle('active',!isC);$('#cCempla').classList.toggle('active',isC);document.querySelectorAll('[data-cfg-name=\"1\"]').forEach(el=>el.textContent=c1);document.querySelectorAll('[data-cfg-name=\"2\"]').forEach(el=>el.textContent=c2);$('#appTitle').firstChild.nodeValue=isC?c2+' ':'MediCar Plus ';$('#appSub').textContent=isC?'Revisions · '+c2:'Cierre diario · Importación CSV/Excel · Debe / Haber';"
if re.search(old_pattern, h):
    h = re.sub(old_pattern, new_code, h)
    print("  ✓ applyCompanyUI substituïda")
else:
    print("  ⚠ applyCompanyUI no coincideix amb el patró esperat — revisa manualment")
with open(p,'w') as f: f.write(h)
PYEOF

# 3d) compName helpers: substitueix per versió CFG-aware
sed -i "s|const compName=(c)=>c==='cempla'?'CEMPLA ESPORT':'CEMPLA C\.B';|const compName=(c)=>c==='cempla'?((window.CFG\&\&CFG.company2\&\&CFG.company2.name)||'Esport'):((window.CFG\&\&CFG.company1\&\&CFG.company1.name)||'Empresa');|g" "$WORK"

# 3e) Estadístiques h3 header
sed -i 's|📊 Estadístiques Autoescoles CEMPLA C\.B|📊 Estadístiques Autoescoles ${(window.CFG\&\&CFG.company1\&\&CFG.company1.name)||"Empresa"}|g' "$WORK"

# 3f) Empresa activa in audit summary
sed -i "s|currentCompany==='cempla'?'CEMPLA ESPORT':'CEMPLA C\.B'|currentCompany==='cempla'?((window.CFG\&\&CFG.company2\&\&CFG.company2.name)||'Esport'):((window.CFG\&\&CFG.company1\&\&CFG.company1.name)||'Empresa')|g" "$WORK"

# 3g) Ledger comp buttons (2 llocs)
sed -i 's|border-radius:6px">CEMPLA C\.B</button>|border-radius:6px">${compName("trafic")}</button>|g' "$WORK"
sed -i 's|border-radius:6px">CEMPLA ESPORT</button>|border-radius:6px">${compName("cempla")}</button>|g' "$WORK"

echo "💉 [4/6] Injectant la capa comercial (llicència + wizard) abans de </body>"
python3 << PYEOF
p = '/tmp/v2.working.html'
with open(p) as f: h = f.read()
with open('$OVERLAY') as f: overlay = f.read()
if '</body>' not in h:
    print("  ❌ No s'ha trobat </body> a v1")
    exit(1)
# Injecta l'overlay just abans del </body> (dins del script existent? no, com a <script> nou)
new_block = f"\n<script>\n{overlay}\n</script>\n</body>"
h = h.replace('</body>', new_block, 1)
with open(p,'w') as f: f.write(h)
print("  ✓ Overlay injectat")
PYEOF

echo "📤 [5/6] Publicant a v2.html + sync commercial + obfuscant"
cp "$WORK" "$V2"
cp "$V2" "$V2_COPY"
node /app/commercial/build/obfuscate.js 2>&1 | grep -E "(HTML size|JS size|Wrote|WARNING)" || true

echo "📦 [6/6] Regenerant ZIP"
rm -f "$ZIP_OUT"
( cd /app/commercial/electron && zip -qr "$ZIP_OUT" . -x "node_modules/*" -x "yarn.lock" -x "dist/*" -x "*.log" )
ls -la "$ZIP_OUT"

echo ""
echo "✅ Sync completat. Fitxers actualitzats:"
echo "   · $V2 (dev preview)"
echo "   · $V2_COPY (working copy)"
echo "   · $ELECTRON_INDEX (obfuscat)"
echo "   · $ZIP_OUT (paquet distribució)"
echo ""
if [ "${1:-}" = "--release" ]; then
  echo "🚀 Publicant a GitHub Releases (necessita GH_TOKEN i publish real al package.json)..."
  cd /app/commercial/electron && npm run release || {
    echo "⚠️  Release fallit. Comprova que:"
    echo "   · package.json 'publish.owner' ja NO és 'TEU_USUARI_GITHUB'"
    echo "   · GH_TOKEN està definit"
    echo "   · Estàs en un PC Windows/Mac (electron-builder no compila per Windows des de Linux sense config extra)"
  }
else
  echo "💡 Per publicar la nova versió als clients:"
  echo "   1. cd /app/commercial/electron"
  echo "   2. Puja la 'version' del package.json (2.0.0 → 2.0.1)"
  echo "   3. npm run release  (des del PC Windows amb GH_TOKEN definit)"
fi
