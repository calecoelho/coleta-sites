"""Peças que todos os sites usam: baixar páginas, ler hora/autor/resumo, falar com o Supabase."""
import html as htmllib
import json
import os
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Essa linha tenta ler as chaves do arquivo .env (se existir).
# Para isso, usa o python-dotenv. Na nuvem (ex.: GitHub Actions) as chaves vêm de variáveis
# de ambiente e o .env simplesmente não existe, o que não é problema.
load_dotenv()

# Cabeçalhos de um Chrome comum. Alguns sites (o UOL, por exemplo) recusam pedidos que
# não parecem vir de um navegador de verdade.
HEADERS_SITE = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Upgrade-Insecure-Requests": "1",
}
# A coluna published_at não guarda fuso, então gravamos sempre em hora de Brasília.
FUSO = ZoneInfo("America/Sao_Paulo")


# ---------------------------------------------------------------- Supabase
# Colunas da tabela public.news que este projeto preenche.
COLUNAS = ["title", "url", "source", "published_at", "author", "resumo"]


def credenciais():
    # Essa função tenta ler o endereço e a chave do Supabase.
    # Para isso, olha as variáveis SUPABASE_URL e SUPABASE_KEY.
    return (os.getenv("SUPABASE_URL") or "").rstrip("/"), os.getenv("SUPABASE_KEY")


def _cabecalho_db():
    _, chave = credenciais()
    return {"apikey": chave or "", "Authorization": f"Bearer {chave}",
            "Content-Type": "application/json"}


def urls_ja_gravadas(urls):
    # Essa função tenta descobrir quais links já estão na tabela.
    # Para isso, pergunta ao Supabase em blocos de 40; cada link vai entre aspas, porque
    # alguns (como os do Terra) têm vírgulas.
    base, _ = credenciais()
    existentes = set()
    for i in range(0, len(urls), 40):
        bloco = urls[i:i + 40]
        filtro = "in.(" + ",".join(f'"{u}"' for u in bloco) + ")"
        r = requests.get(f"{base}/rest/v1/news", headers=_cabecalho_db(),
                         params={"select": "url", "url": filtro}, timeout=30)
        r.raise_for_status()
        existentes |= {x["url"] for x in r.json()}
    return existentes


def enviar_ao_supabase(noticias):
    # Essa função tenta gravar as notícias novas na tabela public.news.
    # Para isso, usa a url como chave e manda ignorar as que já existem (nunca sobrescreve).
    if not noticias:
        return []
    base, _ = credenciais()
    # Essa linha tenta deixar todas as notícias com exatamente as mesmas colunas.
    # Para isso, preenche com vazio (None) o que faltar. O Supabase recusa (erro 400)
    # um pacote em que uma notícia tem colunas diferentes das outras.
    noticias = [{c: n.get(c) for c in COLUNAS} for n in noticias]
    r = requests.post(
        f"{base}/rest/v1/news?on_conflict=url",
        headers={**_cabecalho_db(), "Prefer": "resolution=ignore-duplicates,return=representation"},
        data=json.dumps(noticias), timeout=30)
    if not r.ok:
        # Mostra o motivo que o Supabase deu, em vez de só "400 Bad Request".
        raise RuntimeError(f"Supabase recusou a gravação ({r.status_code}): {r.text[:300]}")
    return r.json()


# ---------------------------------------------------------------- leitura de páginas
def baixar(url):
    # Essa função tenta baixar uma página.
    # Para isso, faz um pedido GET com cara de navegador e avisa se der erro.
    r = requests.get(url, headers=HEADERS_SITE, timeout=20)
    r.raise_for_status()
    return r.text


def hora_local(texto):
    # Essa função tenta converter "2026-10-21T15:30:32-03:00" (ou com Z, que é hora UTC)
    # em hora de Brasília, sem fuso, pronta para a coluna published_at.
    dt = datetime.fromisoformat(texto.strip().replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.isoformat(timespec="seconds")
    return dt.astimezone(FUSO).replace(tzinfo=None).isoformat(timespec="seconds")


def _nomes(a):
    # Aceita autor como texto, objeto {"name": ...} ou lista deles.
    if isinstance(a, str):
        return [a.strip()]
    if isinstance(a, dict):
        return [a["name"].strip()] if a.get("name") else []
    if isinstance(a, list):
        return [n for x in a for n in _nomes(x)]
    return []


def juntar_nomes(nomes):
    # Vários autores ficam numa linha só, separados por vírgula, sem repetir.
    return ", ".join(dict.fromkeys(n for n in nomes if n)) or None


def ler_dados_estruturados(html):
    # Essa função tenta descobrir hora, autor e resumo de UMA matéria.
    # Para isso, procura nos dados estruturados da página (JSON-LD, tipo NewsArticle) e,
    # se faltar algo, nas "meta tags" do cabeçalho.
    soup = BeautifulSoup(html, "html.parser")
    publicado, autores, resumo = None, [], None

    for sc in soup.find_all("script", type="application/ld+json"):
        try:
            dados = json.loads(sc.string or "")
        except ValueError:
            continue
        candidatos = dados if isinstance(dados, list) else dados.get("@graph", [dados])
        for d in candidatos:
            if not isinstance(d, dict):
                continue
            tipo = d.get("@type")
            tipos = tipo if isinstance(tipo, list) else [tipo]
            if not any(t in ("NewsArticle", "Article", "ReportageNewsArticle") for t in tipos):
                continue
            publicado = publicado or d.get("datePublished")
            autores = autores or _nomes(d.get("author"))
            resumo = resumo or d.get("description")

    def meta(*nomes):
        for n in nomes:
            m = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n})
            if m and m.get("content", "").strip():
                return m["content"].strip()
        return None

    publicado = publicado or meta("datePublished", "article:published_time")
    resumo = resumo or meta("og:description", "description")
    try:
        publicado = hora_local(publicado) if publicado else None
    except ValueError:
        publicado = None
    return {
        "published_at": publicado,
        "author": juntar_nomes(autores),
        "resumo": htmllib.unescape(resumo or "").strip() or None,
    }


# ---------------------------------------------------------------- o fluxo de cada site
def coletar(site, max_novas=40, dry_run=False, pausa=1.0):
    """Roda o fluxo completo de um site.

    "site" é um módulo (valor.py, terra.py, uol.py) que precisa ter:
      FONTE, URLS_LISTA, extrair_lista(html) e autor_alternativo(html).
    """
    # 1) Essa parte tenta juntar as matérias de todas as páginas de lista do site.
    lista, vistos = [], set()
    for pagina in site.URLS_LISTA:
        novas = [i for i in site.extrair_lista(baixar(pagina)) if i["url"] not in vistos]
        vistos |= {i["url"] for i in novas}
        lista += novas
    encontradas = len(lista)

    # 2) Essa parte tenta descartar o que já está no banco (se houver chaves).
    base, chave = credenciais()
    if base and chave:
        ja = urls_ja_gravadas([i["url"] for i in lista])
        lista = [i for i in lista if i["url"] not in ja]
    lista = lista[:max_novas]

    # 3) Essa parte abre cada matéria nova e completa autor, hora e resumo.
    prontas, descartadas = [], 0
    for item in lista:
        try:
            html = baixar(item["url"])
        except requests.RequestException as e:
            print(f"  - erro ao abrir {item['url']} ({e})")
            continue
        dados = ler_dados_estruturados(html)
        dados["author"] = dados["author"] or site.autor_alternativo(html)
        # Só sobrescreve o que a matéria realmente trouxe (não apaga o que veio da lista),
        # e mantém o resumo da lista quando ele já existe.
        item.update({k: v for k, v in dados.items()
                     if v and not (k == "resumo" and item.get("resumo"))})
        # Regra do projeto: só grava matéria com título, url e data de publicação.
        faltando = [nome for nome, chave in (("título", "title"), ("url", "url"),
                                              ("data", "published_at")) if not item.get(chave)]
        if faltando:
            descartadas += 1
            print(f"  x descartada (sem {', '.join(faltando)}): {item.get('title') or item['url']}")
        else:
            print(f"  - {item['published_at']} | {item.get('author') or '(sem autor)'} | {item['title']}")
            prontas.append(item)
        time.sleep(pausa)  # pausa entre páginas, para não sobrecarregar o site

    # 4) Essa parte grava (a não ser no modo de teste).
    gravadas = 0 if dry_run else len(enviar_ao_supabase(prontas))
    return {"fonte": site.FONTE, "encontradas": encontradas, "novas": len(prontas),
            "descartadas": descartadas, "gravadas": gravadas}
