"""Valor Econômico: página de últimas notícias.

A lista traz título, link, resumo e a hora exata (num JSON dentro da página). O autor só
aparece na matéria, então o fluxo abre cada matéria nova para pegá-lo.
"""
import json
import re

from bs4 import BeautifulSoup

FONTE = "Valor Econômico"
URLS_LISTA = ["https://valor.globo.com/ultimas-noticias/"]


def _json_da_lista(html):
    # Essa função tenta ler a lista "escondida" no código da página (cerca de 30 itens).
    # Para isso, acha o bloco bstn-launcher-bundle e, a cada '{"age":', lê um objeto
    # JSON completo (cada um é uma notícia).
    from .comum import hora_local
    bloco = re.search(r'<script id="bstn-launcher-bundle"[^>]*>(.*?)</script>', html, re.S)
    if not bloco:
        return []
    texto, decoder, itens = bloco.group(1), json.JSONDecoder(), []
    for achado in re.finditer(r'\{"age":', texto):
        try:
            item, _ = decoder.raw_decode(texto, achado.start())
        except ValueError:
            continue
        c = item.get("content", {})
        if not c.get("url") or not c.get("title"):
            continue
        itens.append({
            "title": c["title"].strip(), "url": c["url"], "source": FONTE,
            "published_at": hora_local(item["publication"]) if item.get("publication") else None,
            "resumo": (c.get("summary") or "").strip() or None,
        })
    return itens


def _cartoes_da_lista(html):
    # Plano B: se o JSON sumir, lê os 10 cartões visíveis (sem hora exata).
    soup = BeautifulSoup(html, "html.parser")
    itens = []
    for card in soup.select("div.bastian-feed-item"):
        a = card.select_one("h2.feed-post-link a")
        if not a:
            continue
        resumo = card.select_one("p.feed-post-body-resumo")
        itens.append({"title": a.get_text(strip=True), "url": a.get("href"), "source": FONTE,
                      "resumo": resumo.get_text(strip=True) if resumo else None})
    return itens


def extrair_lista(html):
    itens = _json_da_lista(html) or _cartoes_da_lista(html)
    # Um item por url (o banco só aceita uma linha por url).
    return list({i["url"]: i for i in itens}.values())


def autor_alternativo(html):
    # Essa função tenta descobrir quem assinou a matéria. Para isso, tenta:
    #  1) os links de autor na assinatura ("Por Maria Fernanda Salinet, Valor");
    #  2) a lista "authors" embutida na página;
    #  3) o texto solto depois de "Por", para casos sem link (ex.: agência).
    from .comum import juntar_nomes
    soup = BeautifulSoup(html, "html.parser")
    nomes = juntar_nomes(a.get_text(strip=True)
                         for a in soup.select("div.content__signature address a"))
    if nomes:
        return nomes
    achado = re.search(r'"authors"\s*:\s*(\[[^\]]*\])', html)
    if achado:
        try:
            nomes = juntar_nomes(n.strip() for n in json.loads(achado.group(1)))
            if nomes:
                return nomes
        except ValueError:
            pass
    de = soup.select_one("div.content-publication-data__from")
    if de:
        m = re.match(r"Por\s+(.+?)\s*(?:,|—|$)", de.get_text(" ", strip=True))
        if m:
            return m.group(1).strip()
    return None
