"""SEO validation tests for /app/frontend/public/index.html and served build."""
import json
import os
import re
import subprocess
import pytest
import requests

INDEX_HTML = "/app/frontend/public/index.html"
LANDING_JSX = "/app/frontend/src/pages/LandingPage.jsx"
PUBLIC_URL = "https://project-helper-47.preview.emergentagent.com"


@pytest.fixture(scope="module")
def html():
    with open(INDEX_HTML, encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def jsonld_blocks(html):
    return re.findall(
        r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
        html, re.DOTALL,
    )


# ---- Meta tag checks ----
class TestMeta:
    def test_title_contains_key_phrase(self, html):
        m = re.search(r"<title>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
        assert m, "Missing <title>"
        assert "centros médicos de conductores" in m.group(1).lower()
        assert "certificados médicos" in m.group(1).lower()

    def test_meta_description(self, html):
        m = re.search(r'<meta name="description" content="([^"]+)"', html)
        assert m
        d = m.group(1).lower()
        for kw in ["reconocimientos", "certificados", "facturación",
                   "irpf", "estadísticas", "agenda", "sms"]:
            assert kw in d, f"description missing keyword: {kw}"

    def test_og_title_description(self, html):
        og_t = re.search(r'<meta property="og:title" content="([^"]+)"', html)
        og_d = re.search(r'<meta property="og:description" content="([^"]+)"', html)
        assert og_t and og_d
        assert "centros médicos de conductores" in og_t.group(1).lower()
        assert "centros médicos de conductores" in og_d.group(1).lower()

    def test_twitter_title_description(self, html):
        tw_t = re.search(r'<meta name="twitter:title" content="([^"]+)"', html)
        tw_d = re.search(r'<meta name="twitter:description" content="([^"]+)"', html)
        assert tw_t and tw_d
        assert "centros médicos de conductores" in tw_t.group(1).lower()
        assert "centros médicos de conductores" in tw_d.group(1).lower()


# ---- JSON-LD checks ----
class TestJsonLd:
    def test_four_blocks_present(self, jsonld_blocks):
        assert len(jsonld_blocks) == 4, f"Expected 4 JSON-LD blocks, got {len(jsonld_blocks)}"

    def test_all_blocks_valid_json(self, jsonld_blocks):
        for i, block in enumerate(jsonld_blocks):
            try:
                json.loads(block)
            except json.JSONDecodeError as e:
                pytest.fail(f"JSON-LD block #{i+1} invalid: {e}")

    def test_software_application(self, jsonld_blocks):
        data = json.loads(jsonld_blocks[0])
        assert data["@type"] == "SoftwareApplication"
        assert "centros médicos de conductores" in data["description"].lower()
        assert "60 días" in data["offers"]["description"]
        assert "29,90" in data["offers"]["description"]

    def test_website_search_action(self, jsonld_blocks):
        data = json.loads(jsonld_blocks[1])
        assert data["@type"] == "WebSite"
        assert data["potentialAction"]["@type"] == "SearchAction"

    def test_site_navigation_six_items(self, jsonld_blocks):
        data = json.loads(jsonld_blocks[2])
        graph = data.get("@graph", [])
        assert len(graph) == 6
        names = [n["name"] for n in graph]
        for expected in ["Características", "Planes y precios", "Estadísticas",
                         "Calendario de citas", "Solicitar licencia", "Contacto"]:
            assert expected in names

    def test_organization_contact(self, jsonld_blocks):
        data = json.loads(jsonld_blocks[3])
        assert data["@type"] == "Organization"
        assert data["contactPoint"]["email"] == "info@medicarplus.es"


# ---- Landing page anchors ----
class TestAnchors:
    def test_anchors_present(self):
        with open(LANDING_JSX, encoding="utf-8") as f:
            src = f.read()
        for anchor in ['id="features"', 'id="pricing"', 'id="contact"']:
            assert anchor in src, f"Missing anchor {anchor}"


# ---- Build check ----
class TestBuild:
    def test_yarn_build_succeeds(self):
        result = subprocess.run(
            ["yarn", "build"],
            cwd="/app/frontend",
            capture_output=True, text=True, timeout=240,
            env={**os.environ, "CI": "false"},
        )
        assert result.returncode == 0, f"yarn build failed:\nSTDOUT:{result.stdout[-2000:]}\nSTDERR:{result.stderr[-2000:]}"
        # Verify built index.html contains updated title
        built = "/app/frontend/build/index.html"
        assert os.path.exists(built)
        with open(built, encoding="utf-8") as f:
            content = f.read()
        assert "centros médicos de conductores" in content.lower()
        # Ensure all 4 JSON-LD blocks made it through
        blocks = re.findall(r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
                            content, re.DOTALL)
        assert len(blocks) == 4
        for b in blocks:
            json.loads(b)


# ---- Live preview URL check ----
class TestServed:
    def test_public_url_serves_updated_meta(self):
        try:
            r = requests.get(PUBLIC_URL, timeout=15)
        except Exception as e:
            pytest.skip(f"Preview URL unreachable: {e}")
        assert r.status_code == 200
        assert "centros médicos de conductores" in r.text.lower()
