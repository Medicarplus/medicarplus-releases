// 🧪 Oct 2026 · Comprueba que TODOS los PDF/print del app incluyen reglas CSS
//   anti-corte robustas (sin falsos positivos de secciones a mitad de página).
//
// Uso: node tests/pdf_anticorte.js

const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'v2.html'), 'utf8');

let okCount = 0, failCount = 0;
function check(cond, label, extra){
  if(cond){ okCount++; console.log('  ✅', label); }
  else    { failCount++; console.error('  ❌', label, extra||''); }
}

// Localizar todos los bloques @page (son los PDFs embebidos)
const pageBlocks = [];
const atPageRegex = /@page\s*\{[^}]*\}/g;
let m;
while ((m = atPageRegex.exec(html)) !== null){
  // Capturar ~800 chars tras el @page (donde está el CSS asociado)
  const chunk = html.slice(m.index, m.index + 7000);
  pageBlocks.push({ idx: m.index, chunk });
}

console.log(`\n📊 Encontrados ${pageBlocks.length} bloques de PDF/@page en v2.html`);
console.log('='.repeat(70));

// Reglas que todos los PDFs deben contener (al menos una de cada tipo)
const rules = [
  { label: 'tr: page-break-inside avoid',       pattern: /tr\s*\{[^}]*page-break-inside\s*:\s*avoid/ },
  { label: 'thead: display table-header-group', pattern: /thead\s*\{[^}]*display\s*:\s*table-header-group/ },
  { label: 'tfoot: no partir',                   pattern: /tfoot[^{]*\{[^}]*(page-break-inside|break-inside)\s*:\s*avoid/ },
  { label: 'h*+*: no cortar título de contenido',pattern: /h[1-5]\s*\+\s*\*[^{]*\{[^}]*(page-break-before|break-before)\s*:\s*avoid/ },
];

pageBlocks.forEach((pb, i) => {
  console.log(`\n🖨️ PDF #${i+1} · offset ${pb.idx}`);
  // Snippet corto para identificar
  const titleMatch = pb.chunk.match(/<title>([^<]+)<\/title>/) ||
                     pb.chunk.match(/title\s*:\s*['"`]([^'"`]+)/) ||
                     [null, 'anónimo'];
  console.log(`   contexto: "${(titleMatch[1]||'').slice(0,60)}"`);
  rules.forEach(r => {
    check(r.pattern.test(pb.chunk), `${r.label}`);
  });
});

console.log('\n' + '='.repeat(70));
console.log(`📊 RESULTADO · ${okCount} OK · ${failCount} FAIL · ${pageBlocks.length} PDFs analizados`);
console.log('='.repeat(70));
if (failCount){
  console.error('⚠️ Algunos PDFs no tienen todas las reglas anti-corte');
  process.exit(1);
}
console.log('🛡  Todos los PDFs del app tienen reglas anti-corte robustas');
process.exit(0);
