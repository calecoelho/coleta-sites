# Coletor de notícias

Coleta as últimas notícias de **Valor Econômico**, **Terra** e **UOL** e grava na tabela
`public.news` do Supabase. Para cada matéria nova, abre a página e pega autor, hora de
publicação e resumo. Nunca sobrescreve o que já existe (a `url` é a chave).

## Como rodar

```
pip install -r requirements.txt
cp .env.example .env        # e preencha SUPABASE_URL e SUPABASE_KEY
python main.py --dry-run    # testa sem gravar
python main.py              # coleta tudo e grava
python main.py --fonte uol  # só um site (valor, terra, uol; separe por vírgula)
python main.py --max 100    # máx. de matérias novas por site (padrão 40)
```

## Estrutura

```
main.py              dispara os fluxos (o "botão" do projeto)
coletor/comum.py     partes compartilhadas: baixar páginas, ler hora/autor, Supabase
coletor/valor.py     o que é específico do Valor
coletor/terra.py     o que é específico do Terra
coletor/uol.py       o que é específico do UOL
scripts/             utilitários avulsos (ex.: preencher autor de linhas antigas do Valor)
.github/workflows/   disparo automático no GitHub (desligado por padrão)
```

## Acrescentar um novo site

1. Crie `coletor/novo.py` com `FONTE`, `URLS_LISTA`, `extrair_lista(html)` e `autor_alternativo(html)`.
2. Inclua-o no dicionário `SITES` do `main.py`.

## Segurança

O arquivo `.env` (com as chaves) **não** vai para o GitHub: já está no `.gitignore`.
Para o disparo automático, cadastre `SUPABASE_URL` e `SUPABASE_KEY` em
*Settings → Secrets and variables → Actions* do repositório.
