// ============================================================================
// GUIA AI WIDGET · Google Gemini (GRATIS 1500 consultes/dia amb clau pròpia)
// ----------------------------------------------------------------------------
// Injecta un botó flotant a totes les guies. Al clicar obre un xat amb IA que
// coneix el context de MediCar Plus i respon dubtes de l'usuari.
//
// La clau Google Gemini es demana un cop i es guarda a localStorage. Google
// regala 1500 consultes/dia gratis: https://aistudio.google.com/apikey
// ============================================================================
(function(){
  'use strict';
  const KEY_STORAGE='medicarplus.gemini.key';
  const HISTORY_STORAGE='medicarplus.guide.chat.v1';
  const MAX_HISTORY=20; // pairs of user/assistant messages

  // Context del sistema: MediCar Plus, què és, què fa, on trobar cada cosa
  const SYSTEM_PROMPT=`Ets un assistent expert del programa MediCar Plus, una aplicació d'escriptori (Electron + Windows) per a centres mèdics de reconeixement de conductors i gestories de tràfic. L'usuari és Marc Brugulat Lopez, propietari del programa.

FUNCIONALITATS DEL PROGRAMA:
- Cierre diario de caja amb ingressos per Efectivo/Tarjeta/Bizum/Transferencia, tasas DGT, descomptes
- Múltiples empreses aïllades (Tráfico + Revisiones) amb dades independents
- Módulo IRPF trimestral: nòmina de treballadors amb càlcul automàtic BRUT/S.S./TOTAL/IRPF/NET, sobre IRPF, control de pagaments a Hisenda
- Estadísticas: gràfics per empresa, mes, forma de pagament, tipus de servei
- Libro de Registro (històric complet de moviments)
- Audit / Asesor IA amb Google Gemini per detectar descuadres
- Cites del día · sincronització amb Google Calendar, Doctoralia, Calendly, Doctolib via URLs .ics
- Avisos SMS: campanyes de recordatoris a clients (mock/Twilio)
- Sistema llicències HWID-locked amb JWT
- Auto-updates via GitHub Releases (electron-updater)
- Landing pública a medicarplus.es (GitHub Pages)

ESTRUCTURA TÈCNICA:
- Frontend: Vanilla JS · un únic fitxer v2.html/index.html (~5.400 línies)
- Backend: FastAPI + MongoDB (a preview.emergentagent.com)
- Publicació: publish-safe.ps1 (sync + build + smoke + publish)
- Distribució: NSIS installer + Portable exe des de GitHub Releases

COSES QUE HA DE SABER L'USUARI:
- Master key (mai compartir): MB-MASTER-BRUGULAT-2026-OWNER
- Admin panel: /admin.html · token MB-ADMIN-BRUGULAT-2026-4F8E2A1C
- Preus: 39€/mes o 349€/any per empresa
- Solució 404 SMS/Cites: editar https://medicarplus.es/api-endpoint.json amb la nova URL del backend
- Configuración → Diagnóstico permet override manual d'URL

Respons sempre en Català o Castellà segons l'idioma de la pregunta. Sigues concís i pràctic. Si l'usuari pregunta com fer alguna cosa, dona-li els passos concrets. Si pregunta sobre un error, primer diagnostica i després proposa fix. Si no saps la resposta, digue-ho i suggereix on mirar (guia general, guia deploy, guia stripe, etc.).`;

  const gemini={
    async ask(apiKey, question, history){
      // Construeix contingut: system + history + nova pregunta
      const contents=[];
      // Gemini no té "system" role dedicat, així que injectem com a primer message del user amb rol assistant després
      contents.push({role:'user', parts:[{text:'INSTRUCCIONS DEL SISTEMA:\n'+SYSTEM_PROMPT+'\n\nAra respon la següent pregunta de l\'usuari.'}]});
      contents.push({role:'model', parts:[{text:'Entesos. Estic llest per ajudar-te amb MediCar Plus.'}]});
      // History (pairs)
      for(const h of history){
        contents.push({role:'user', parts:[{text:h.q}]});
        contents.push({role:'model', parts:[{text:h.a}]});
      }
      contents.push({role:'user', parts:[{text:question}]});

      const model='gemini-2.0-flash-exp';
      const url=`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${encodeURIComponent(apiKey)}`;
      const r=await fetch(url,{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({contents, generationConfig:{temperature:0.5, maxOutputTokens:2048}})
      });
      if(!r.ok){
        const err=await r.text();
        throw new Error('HTTP '+r.status+' · '+err.slice(0,200));
      }
      const j=await r.json();
      const txt=(((j.candidates||[])[0]||{}).content||{}).parts;
      if(!txt||!txt[0]||!txt[0].text) throw new Error('Resposta buida');
      return txt[0].text;
    }
  };

  function getKey(){ try{return localStorage.getItem(KEY_STORAGE)||''}catch(e){return ''} }
  function setKey(k){ try{localStorage.setItem(KEY_STORAGE, k||'')}catch(e){} }
  function loadHistory(){ try{return JSON.parse(localStorage.getItem(HISTORY_STORAGE)||'[]')}catch(e){return []} }
  function saveHistory(h){ try{localStorage.setItem(HISTORY_STORAGE, JSON.stringify(h.slice(-MAX_HISTORY)))}catch(e){} }

  const style=document.createElement('style');
  style.textContent=`
    #ai-fab{position:fixed;bottom:24px;right:24px;width:60px;height:60px;border-radius:50%;background:linear-gradient(135deg,#7c3aed,#a855f7);color:#fff;border:none;box-shadow:0 8px 24px rgba(124,58,237,.4);cursor:pointer;z-index:99998;font-size:28px;display:flex;align-items:center;justify-content:center;transition:transform .2s}
    #ai-fab:hover{transform:scale(1.08)}
    #ai-fab .ai-badge{position:absolute;top:-4px;right:-4px;background:#22c55e;color:#0f172a;border-radius:12px;padding:2px 6px;font-size:9px;font-weight:800;letter-spacing:.5px}
    #ai-overlay{position:fixed;inset:0;background:rgba(0,0,0,.55);backdrop-filter:blur(6px);z-index:99999;display:none;align-items:flex-end;justify-content:flex-end;padding:20px}
    #ai-overlay.open{display:flex}
    #ai-panel{background:linear-gradient(160deg,#0f172a,#020617);color:#e2e8f0;width:100%;max-width:440px;height:640px;max-height:88vh;border-radius:18px;box-shadow:0 25px 60px rgba(0,0,0,.6);border:1px solid #334155;display:flex;flex-direction:column;overflow:hidden;font-family:'Segoe UI',system-ui,sans-serif}
    #ai-head{padding:14px 18px;background:linear-gradient(135deg,#7c3aed,#a855f7);color:#fff;display:flex;align-items:center;gap:10px;font-weight:700}
    #ai-head .ai-t{flex:1;font-size:15px;line-height:1.2}
    #ai-head .ai-s{font-size:11px;opacity:.85;font-weight:400}
    #ai-head button{background:transparent;border:1px solid rgba(255,255,255,.3);color:#fff;padding:4px 10px;border-radius:6px;cursor:pointer;font-size:12px}
    #ai-body{flex:1;overflow:auto;padding:14px;display:flex;flex-direction:column;gap:10px;font-size:13.5px;line-height:1.5}
    #ai-body .msg{padding:10px 12px;border-radius:12px;max-width:88%;white-space:pre-wrap;word-break:break-word}
    #ai-body .msg-u{background:#1e293b;color:#e2e8f0;align-self:flex-end;border:1px solid #334155}
    #ai-body .msg-a{background:#3b0764;color:#f3e8ff;align-self:flex-start;border:1px solid #7c3aed}
    #ai-body .msg-e{background:#7f1d1d;color:#fecaca;align-self:flex-start;border:1px solid #b91c1c}
    #ai-body .msg-sys{background:#0c4a6e;color:#bae6fd;align-self:stretch;border:1px solid #0284c7;font-size:12px}
    #ai-key-box{background:#1e293b;border-top:1px solid #334155;padding:12px 14px;font-size:12px}
    #ai-key-box.hidden{display:none}
    #ai-key-box label{display:block;margin-bottom:6px;color:#cbd5e1;font-weight:600}
    #ai-key-box input{width:100%;background:#0f172a;color:#f3e8ff;border:1px solid #475569;border-radius:6px;padding:8px;font-family:monospace;font-size:12px;box-sizing:border-box;margin-bottom:8px}
    #ai-key-box .k-actions{display:flex;gap:6px}
    #ai-key-box button{flex:1;background:#7c3aed;color:#fff;border:none;padding:8px;border-radius:6px;cursor:pointer;font-weight:700;font-size:12px}
    #ai-key-box .k-info{color:#94a3b8;font-size:11px;line-height:1.5;margin-bottom:8px}
    #ai-key-box a{color:#a5b4fc}
    #ai-input-box{padding:12px;border-top:1px solid #334155;background:#0b1220;display:flex;gap:8px}
    #ai-input-box textarea{flex:1;background:#1e293b;color:#e2e8f0;border:1px solid #475569;border-radius:8px;padding:8px 10px;font-family:inherit;font-size:13px;resize:none;height:44px;box-sizing:border-box}
    #ai-input-box button{background:linear-gradient(135deg,#7c3aed,#a855f7);color:#fff;border:none;padding:8px 16px;border-radius:8px;cursor:pointer;font-weight:700}
    #ai-input-box button:disabled{opacity:.5;cursor:not-allowed}
    #ai-clear{background:transparent;color:#94a3b8;border:none;font-size:11px;padding:6px;cursor:pointer;text-decoration:underline}
    @media(max-width:600px){
      #ai-overlay{padding:0}
      #ai-panel{max-width:100%;height:100vh;max-height:100vh;border-radius:0}
    }
  `;
  document.head.appendChild(style);

  const fab=document.createElement('button');
  fab.id='ai-fab';
  fab.title='Preguntar a la IA';
  fab.innerHTML='🤖<span class="ai-badge">IA</span>';
  document.body.appendChild(fab);

  const overlay=document.createElement('div');
  overlay.id='ai-overlay';
  overlay.innerHTML=`
    <div id="ai-panel">
      <div id="ai-head">
        <div class="ai-t">🤖 Assistent MediCar Plus<div class="ai-s">Google Gemini · GRATIS amb la teva clau</div></div>
        <button id="ai-close">✕</button>
      </div>
      <div id="ai-body"></div>
      <div id="ai-key-box" class="hidden">
        <label>🔑 Clau Google Gemini (GRATIS · 1.500 consultes/dia)</label>
        <div class="k-info">Aconsegueix la teva clau a <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener">aistudio.google.com/apikey</a>. Inicia sessió amb Google, clica "Create API Key", copia-la (comença per AIza...) i enganxa-la aquí. Es guarda al teu navegador; mai s'envia enlloc més.</div>
        <input id="ai-key-input" type="text" placeholder="AIzaSy..." />
        <div class="k-actions">
          <button id="ai-key-save">💾 Desar clau</button>
        </div>
      </div>
      <div id="ai-input-box">
        <textarea id="ai-input" placeholder="Fes-me una pregunta sobre MediCar Plus..." rows="2"></textarea>
        <button id="ai-send">Enviar</button>
      </div>
      <div style="text-align:center;padding:4px 0;background:#0b1220"><button id="ai-clear">Netejar conversa</button></div>
    </div>
  `;
  document.body.appendChild(overlay);

  const body=overlay.querySelector('#ai-body');
  const inp=overlay.querySelector('#ai-input');
  const sendBtn=overlay.querySelector('#ai-send');
  const keyBox=overlay.querySelector('#ai-key-box');
  const keyInput=overlay.querySelector('#ai-key-input');
  const clearBtn=overlay.querySelector('#ai-clear');

  function scrollBottom(){ body.scrollTop=body.scrollHeight; }

  function renderHistory(){
    body.innerHTML='';
    const hist=loadHistory();
    if(hist.length===0){
      body.innerHTML='<div class="msg msg-sys">👋 Hola! Sóc l\'assistent de MediCar Plus. Puc ajudar-te amb dubtes sobre el programa, errors, com fer coses o on trobar informació a les guies. Pregunta el que vulguis!</div>';
      return;
    }
    for(const h of hist){
      const u=document.createElement('div'); u.className='msg msg-u'; u.textContent=h.q; body.appendChild(u);
      const a=document.createElement('div'); a.className='msg msg-a'; a.textContent=h.a; body.appendChild(a);
    }
    scrollBottom();
  }

  function openPanel(){
    overlay.classList.add('open');
    const k=getKey();
    if(!k){
      keyBox.classList.remove('hidden');
    } else {
      keyBox.classList.add('hidden');
    }
    renderHistory();
    setTimeout(()=>inp.focus(),100);
  }
  function closePanel(){ overlay.classList.remove('open'); }

  fab.addEventListener('click', openPanel);
  overlay.querySelector('#ai-close').addEventListener('click', closePanel);
  overlay.addEventListener('click', ev => { if(ev.target===overlay) closePanel(); });

  overlay.querySelector('#ai-key-save').addEventListener('click', () => {
    const v=(keyInput.value||'').trim();
    if(!v){ alert('Enganxa la teva clau abans de desar.'); return; }
    if(!v.startsWith('AIza')){ if(!confirm('La clau no comença per AIza. Segur que és correcta?')) return; }
    setKey(v);
    keyBox.classList.add('hidden');
    inp.focus();
  });

  clearBtn.addEventListener('click', () => {
    if(!confirm('Segur que vols esborrar tot l\'historial de la conversa?')) return;
    saveHistory([]);
    renderHistory();
  });

  async function send(){
    const q=(inp.value||'').trim();
    if(!q) return;
    const key=getKey();
    if(!key){ keyBox.classList.remove('hidden'); keyInput.focus(); return; }
    inp.value='';
    sendBtn.disabled=true;
    const hist=loadHistory();
    // Show user msg
    const uEl=document.createElement('div'); uEl.className='msg msg-u'; uEl.textContent=q; body.appendChild(uEl);
    const aEl=document.createElement('div'); aEl.className='msg msg-a'; aEl.textContent='⏳ Pensant...'; body.appendChild(aEl);
    scrollBottom();
    try{
      const answer=await gemini.ask(key, q, hist);
      aEl.textContent=answer;
      hist.push({q, a:answer});
      saveHistory(hist);
    }catch(e){
      aEl.className='msg msg-e';
      aEl.textContent='❌ '+e.message+'\n\nComprova que la teva clau sigui vàlida.';
      // If key error, show key box
      if(/api.?key|permission|forbidden|401|403/i.test(e.message)){
        keyBox.classList.remove('hidden');
      }
    }
    sendBtn.disabled=false;
    scrollBottom();
  }

  sendBtn.addEventListener('click', send);
  inp.addEventListener('keydown', ev => {
    if(ev.key==='Enter' && !ev.shiftKey){ ev.preventDefault(); send(); }
  });
})();
