# Radar de Preços

Projeto 1: monitora preços de produtos, registra o histórico no MongoDB Atlas e envia e-mail quando a meta de preço é atingida.

## Como rodar

1. Instale as bibliotecas: `python -m pip install -r requirements.txt`
2. Crie um arquivo chamado `.env` na pasta do projeto. Copie os nomes das variáveis de `.env.example` e coloque seus próprios dados.
3. Inicie a API: `python -m uvicorn main:app --reload`
4. Abra `http://127.0.0.1:8000/site/` no navegador.

## Requisitos atendidos

- Histórico de preços em subdocumentos (`historico_precos`).
- Pipeline com `$unwind`, `$group`, `$min`, `$filter` e `$avg`.
- Menor preço histórico e média dos últimos 30 dias.
- Scraping com `requests` e `BeautifulSoup`.
- Verificação automática a cada 30 minutos (altere `INTERVALO_MINUTOS` no `.env` para testar mais rápido).
- Alerta por e-mail quando o preço for menor ou igual ao preço-meta.
