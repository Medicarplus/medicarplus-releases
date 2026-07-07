export default function PrivacyPage() {
  const box = {
    maxWidth: 780,
    margin: "0 auto",
    padding: "40px 24px",
    color: "#e2e8f0",
    fontFamily: "Georgia, serif",
    lineHeight: 1.65,
    fontSize: 15,
  };
  const h2 = { color: "#f5b301", marginTop: 32, marginBottom: 8, fontSize: 20 };
  return (
    <div
      data-testid="privacy-page"
      style={{
        minHeight: "100vh",
        background: "linear-gradient(135deg,#0f172a,#1e293b)",
      }}
    >
      <div style={box}>
        <h1 style={{ color: "#f5b301", fontSize: 32, marginBottom: 6 }}>
          Política de privacitat
        </h1>
        <p style={{ color: "#94a3b8", fontSize: 13 }}>
          Última actualització: 07/02/2026
        </p>

        <h2 style={h2}>1. Responsable del tractament</h2>
        <p>
          <b>Marc Brugulat Lopez</b>
          <br />
          Contacte:{" "}
          <a href="mailto:marc@brugulat.cat" style={{ color: "#f5b301" }}>
            marc@brugulat.cat
          </a>
        </p>

        <h2 style={h2}>2. Quines dades tractem</h2>
        <p>
          Quan sol·licites una llicència a través del formulari
          <code style={{ background: "#0f172a", padding: "2px 6px", borderRadius: 4, margin: "0 4px" }}>
            /request-license
          </code>
          recollim: nom de l'empresa, persona de contacte, correu electrònic,
          telèfon, NIF/CIF, i l'identificador d'instal·lació generat per
          l'aplicació.
        </p>

        <h2 style={h2}>3. Finalitat</h2>
        <p>
          Aquestes dades s'utilitzen exclusivament per:
        </p>
        <ul>
          <li>Gestionar la teva sol·licitud i emetre la llicència.</li>
          <li>Contactar-te per correu quan la llicència estigui aprovada.</li>
          <li>Complir amb obligacions legals i comptables.</li>
        </ul>
        <p>
          <b>Les dades comptables i dels teus clients gestionades dins de
          l'aplicació MediCar Plus es queden 100% al teu ordinador</b> — no
          s'envien mai al nostre servidor.
        </p>

        <h2 style={h2}>4. Base legal</h2>
        <p>
          La base legal és l'<b>execució d'un contracte</b> (facilitar-te la
          llicència del programari) i el teu <b>consentiment exprés</b> marcat
          en enviar el formulari.
        </p>

        <h2 style={h2}>5. Conservació</h2>
        <p>
          Conservem les teves dades mentre siguis client actiu més 5 anys per
          obligacions fiscals i legals espanyoles. Un cop caduquin, es
          suprimeixen o s'anonimitzen.
        </p>

        <h2 style={h2}>6. Els teus drets (RGPD)</h2>
        <ul>
          <li>
            <b>Accés:</b> pots demanar una còpia de totes les dades que tenim
            sobre tu.
          </li>
          <li>
            <b>Rectificació:</b> pots corregir qualsevol dada incorrecta.
          </li>
          <li>
            <b>Supressió (dret a l'oblit):</b> pots demanar que suprimim les
            teves dades.
          </li>
          <li>
            <b>Oposició i limitació:</b> pots oposar-te a certs tractaments.
          </li>
          <li>
            <b>Portabilitat:</b> pots demanar les dades en format estructurat.
          </li>
        </ul>
        <p>
          Per exercir qualsevol dret, escriu a{" "}
          <a href="mailto:marc@brugulat.cat" style={{ color: "#f5b301" }}>
            marc@brugulat.cat
          </a>{" "}
          amb l'assumpte "RGPD".
        </p>

        <h2 style={h2}>7. Destinataris i encarregats</h2>
        <p>
          No cedim les teves dades a tercers, excepte a Resend (proveïdor de
          correu electrònic, EEUU amb clàusules contractuals) per enviar-te
          l'email d'activació de llicència.
        </p>

        <h2 style={h2}>8. Seguretat</h2>
        <p>
          Les teves dades es guarden a un servidor amb MongoDB accessible només
          per autenticació administrativa. Les claus de llicència es signen
          criptogràficament (JWT HS256) i es verifiquen a cada ús.
        </p>

        <h2 style={h2}>9. Autoritat de control</h2>
        <p>
          Pots presentar una reclamació a l'Agència Espanyola de Protecció de
          Dades:{" "}
          <a
            href="https://www.aepd.es"
            target="_blank"
            rel="noreferrer"
            style={{ color: "#f5b301" }}
          >
            www.aepd.es
          </a>
          .
        </p>

        <div
          style={{
            marginTop: 40,
            padding: 16,
            background: "#0f172a",
            borderRadius: 8,
            border: "1px solid #334155",
            fontSize: 13,
            color: "#94a3b8",
          }}
        >
          Aquesta política es podrà actualitzar. Sempre trobaràs la versió
          vigent a aquesta pàgina.
        </div>
        <p style={{ textAlign: "center", marginTop: 32, color: "#64748b" }}>
          <a href="/request-license" style={{ color: "#f5b301" }}>
            ← Tornar al portal
          </a>
        </p>
      </div>
    </div>
  );
}
