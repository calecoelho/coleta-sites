"""Ponto de entrada: dispara a coleta de todos os sites (ou só de alguns).

Exemplos:
    python main.py --dry-run                 # testa tudo, sem gravar nada
    python main.py                           # coleta Valor, Terra e UOL e grava
    python main.py --fonte uol               # só o UOL
    python main.py --fonte valor,terra --max 100
"""
import argparse
import sys

from coletor import comum, terra, uol, valor

SITES = {"valor": valor, "terra": terra, "uol": uol}


def main():
    ap = argparse.ArgumentParser(description="Coleta notícias e grava na public.news (Supabase).")
    ap.add_argument("--fonte", default=",".join(SITES),
                    help="quais sites rodar, separados por vírgula (padrão: todos)")
    ap.add_argument("--dry-run", action="store_true", help="só mostra, não grava")
    ap.add_argument("--max", type=int, default=40, help="máx. de matérias novas por site")
    args = ap.parse_args()

    escolhidos = [s.strip().lower() for s in args.fonte.split(",") if s.strip()]
    desconhecidos = [s for s in escolhidos if s not in SITES]
    if desconhecidos:
        sys.exit(f"Fonte desconhecida: {', '.join(desconhecidos)}. Use: {', '.join(SITES)}")

    base, chave = comum.credenciais()
    if not args.dry_run and not (base and chave):
        sys.exit("Faltam SUPABASE_URL e SUPABASE_KEY (no arquivo .env ou nas variáveis de ambiente).")

    resumo, falhas = [], 0
    for nome in escolhidos:
        print(f"\n=== {nome.upper()} ===")
        # Essa parte tenta isolar cada site: se um falhar, os outros continuam.
        try:
            resumo.append(comum.coletar(SITES[nome], args.max, args.dry_run))
        except Exception as e:  # noqa: BLE001
            falhas += 1
            print(f"  ERRO em {nome}: {e}")

    print("\n=== RESUMO ===")
    for r in resumo:
        print(f"{r['fonte']}: {r['encontradas']} na lista, {r['novas']} novas, {r['gravadas']} gravadas")
    if args.dry_run:
        print("(dry-run: nada foi gravado)")
    sys.exit(1 if falhas else 0)  # código 1 avisa um agendador de que algo falhou


if __name__ == "__main__":
    main()
