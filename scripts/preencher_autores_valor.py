"""Preenche a coluna author da public.news para matérias do Valor Econômico que estão sem autor.

Uso:
    python valor_autores.py --dry-run          # mostra o que encontraria, sem gravar
    python valor_autores.py                    # grava (só onde author está vazio)
    python valor_autores.py --limite 100 --dias 3
"""
import argparse
import json
import os
import re
import time

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Essa linha tenta ler as chaves do arquivo .env (as mesmas do outro script).
load_dotenv()
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

FONTE = "Valor Econômico"
HEADERS_SITE = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
HEADERS_DB = {
    "apikey": SUPABASE_KEY or "",
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}
# Filtro "author vazio": cobre tanto NULL quanto texto em branco.
AUTOR_VAZIO = "or=(author.is.null,author.eq.)"


def extrair_autor(html):
    # Essa função tenta descobrir quem assinou a matéria.
    # Para isso, tenta três caminhos, do mais confiável ao menos:
    #  1) os links de autor dentro da assinatura ("Por Maria Fernanda Salinet, Valor");
    #  2) a lista "authors" embutida no código da página;
    #  3) o texto solto depois de "Por", para casos sem link (ex.: agência).
    soup = BeautifulSoup(html, "html.parser")

    nomes = [a.get_text(strip=True) for a in soup.select("div.content__signature address a")]
    if nomes:
        return ", ".join(dict.fromkeys(nomes))

    achado = re.search(r'"authors"\s*:\s*(\[[^\]]*\])', html)
    if achado:
        try:
            lista = [n.strip() for n in json.loads(achado.group(1)) if n.strip()]
            if lista:
                return ", ".join(dict.fromkeys(lista))
        except ValueError:
            pass

    de = soup.select_one("div.content-publication-data__from")
    if de:
        texto = de.get_text(" ", strip=True)
        m = re.match(r"Por\s+(.+?)\s*(?:,|—|$)", texto)
        if m:
            return m.group(1).strip()
    return None


def buscar_pendentes(limite, dias):
    # Essa função tenta listar as matérias do Valor que ainda estão sem autor.
    # Para isso, pergunta ao Supabase por linhas da fonte certa, com author vazio,
    # criadas nos últimos "dias" dias (para não insistir para sempre nas antigas).
    url = (f"{SUPABASE_URL}/rest/v1/news?select=id,url"
           f"&source=eq.{FONTE}&{AUTOR_VAZIO}&url=not.is.null"
           f"&created_at=gte.{time.strftime('%Y-%m-%d', time.gmtime(time.time() - dias * 86400))}"
           f"&order=created_at.desc&limit={limite}")
    r = requests.get(url, headers=HEADERS_DB, timeout=30)
    r.raise_for_status()
    return r.json()


def gravar_autor(id_, autor):
    # Essa função tenta gravar o autor numa linha só.
    # Para isso, faz um PATCH pelo id e repete o filtro "author vazio": assim,
    # nunca sobrescreve um autor que já esteja preenchido.
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/news?id=eq.{id_}&{AUTOR_VAZIO}",
                       headers={**HEADERS_DB, "Prefer": "return=minimal"},
                       data=json.dumps({"author": autor}), timeout=30)
    r.raise_for_status()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limite", type=int, default=50, help="máx. de matérias por rodada")
    ap.add_argument("--dias", type=int, default=3, help="só olha linhas criadas nos últimos N dias")
    args = ap.parse_args()

    if not (SUPABASE_URL and SUPABASE_KEY):
        raise SystemExit("Faltam SUPABASE_URL e SUPABASE_KEY no arquivo .env")

    pendentes = buscar_pendentes(args.limite, args.dias)
    print(f"{len(pendentes)} matérias sem autor")

    achados = 0
    for p in pendentes:
        try:
            r = requests.get(p["url"], headers=HEADERS_SITE, timeout=20)
            r.raise_for_status()
            autor = extrair_autor(r.text)
        except requests.RequestException as e:
            print(f"- id {p['id']}: erro ao abrir a página ({e})")
            continue

        print(f"- id {p['id']}: {autor or '(sem autor na página)'}")
        if autor and not args.dry_run:
            gravar_autor(p["id"], autor)
            achados += 1
        time.sleep(1)  # pausa de 1 s entre páginas, para não sobrecarregar o site

    print("(dry-run: nada foi gravado)" if args.dry_run else f"{achados} autores gravados")
