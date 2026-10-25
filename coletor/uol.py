"""UOL: página de últimas notícias. Regra: entra tudo que leva a um endereço dentro de uol.com.br."""
import re
from urllib.parse import urldefrag, urlparse

from bs4 import BeautifulSoup

FONTE = "UOL"
URLS_LISTA = ["https://noticias.uol.com.br/ultimas/"]
DOMINIO = "uol.com.br"


def _hora_lista(texto):
    # Converte "23/10/2026 17h24" (hora de Brasília) em "2026-10-23T17:24:00".
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})\s+(\d{1,2})h(\d{2})", texto or "")
    if not m:
        return None
    d, mes, a, h, mi = m.groups()
    return f"{a}-{mes}-{d}T{int(h):02d}:{mi}:00"


def extrair_lista(html):
    # Essa função tenta achar as matérias da lista.
    # Para isso, percorre cada "div.thumbnails-item" e pega link, título e hora.
    soup = BeautifulSoup(html, "html.parser")
    itens, vistos = [], set()
    for card in soup.select("div.thumbnails-item"):
        a = card.select_one("a[href]")
        titulo = card.select_one(".thumb-title")
        if not a or not titulo:
            continue
        url = urldefrag(a["href"].strip())[0]  # tira o "#post123" do fim do link
        host = (urlparse(url).hostname or "").lower()
        if (host != DOMINIO and not host.endswith("." + DOMINIO)) or url in vistos:
            continue
        vistos.add(url)
        hora = card.select_one("time.thumb-date")
        itens.append({"title": titulo.get_text(strip=True), "url": url, "source": FONTE,
                      "published_at": _hora_lista(hora.get_text(strip=True) if hora else "")})
    return itens


def autor_alternativo(html):
    # Plano B: o nome no topo da matéria. Plano C: matéria de agência (AFP, Reuters...) não
    # tem autor; o nome da agência vem no campo "credits" quando "showAuthors" é falso.
    from .comum import juntar_nomes
    soup = BeautifulSoup(html, "html.parser")
    nomes = juntar_nomes(e.get_text(strip=True) for e in soup.select("a.solar-author-name"))
    if nomes:
        return nomes
    m = re.search(r'"showAuthors":false,"hideData":(?:true|false),"credits":"([^"]+)"', html)
    return m.group(1).strip() if m else None
