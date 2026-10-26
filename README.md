# Coletor

Coleta informações de sites e grava no banco de dados
## Como rodar

```
pip install -r requirements.txt
cp .env.example .env
python main.py --dry-run    # testa sem gravar
python main.py              # coleta tudo e grava
python main.py --max 100    # máx. de matérias novas por site (padrão 40)
```


## Acrescentar um novo site

1. Crie `coletor/novo.py` com `FONTE`, `URLS_LISTA`, `extrair_lista(html)` e `autor_alternativo(html)`.
2. Inclua-o no dicionário `SITES` do `main.py`.

## Segurança

O arquivo `.env` (com as chaves) **não** vai para o GitHub: já está no `.gitignore`.
Para o disparo automático, cadastre `SUPABASE_URL` e `SUPABASE_KEY` em
*Settings → Secrets and variables → Actions* do repositório.
