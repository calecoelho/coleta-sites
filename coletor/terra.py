"""Terra: página de últimas notícias. Regra: entra tudo que leva a um endereço dentro de terra.com.br."""
from urllib.parse import urlparse

from bs4 import BeautifulSoup

FONTE = "Terra"
URLS_LISTA = ["https://www.terra.com.br/ultimas/"]
DOMINIO = "terra.com.br"


def extrair_lista(html):
    # Essa função tenta achar as matérias da lista.
    # Para isso, percorre cada "div.card-news", pega título e link e descarta o que leva
    # a outro domínio e os links repetidos.
    soup = BeautifulSoup(html, "html.parser")
    itens, vistos = [], set()
    for card in soup.select("div.card-news"):
        a = card.select_one("a.card-news__text--title")
        if not a or not a.get("href") or a["href"] in vistos:
            continue
        host = (urlparse(a["href"]).hostname or "").lower()
        if host != DOMINIO and not host.endswith("." + DOMINIO):
            continue
        vistos.add(a["href"])
        itens.append({"title": a.get_text(strip=True), "url": a["href"], "source": FONTE})
    return itens


def autor_alternativo(html):
    # Plano B para o autor: o nome que aparece no topo da matéria ("Por: Redação Terra").
    soup = BeautifulSoup(html, "html.parser")
    from .comum import juntar_nomes
    return juntar_nomes(e.get_text(strip=True)
                        for e in soup.select("span.article__header__author__item__name"))
