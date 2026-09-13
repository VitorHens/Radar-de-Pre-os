# 📡 Radar de Preços

Sistema web desenvolvido em **Python com FastAPI** para monitorar preços de produtos na internet. A aplicação utiliza web scraping para consultar valores, registra o histórico no **MongoDB Atlas** e envia alertas por e-mail quando a meta de preço é atingida.

## 🚀 Funcionalidades

- 🛒 Cadastro de produtos para monitoramento
- 🔗 Monitoramento através da URL do produto
- 🔍 Web scraping com Requests e BeautifulSoup
- 📊 Histórico de preços armazenado no MongoDB Atlas
- 📉 Consulta do menor preço histórico
- 📈 Cálculo da média dos últimos 30 dias
- 🎯 Definição de uma meta de preço por produto
- 📧 Alerta automático por e-mail quando a meta é atingida
- ⏱️ Verificação automática em intervalos programados
- ✏️ Atualização de informações dos produtos
- 🗑️ Exclusão de produtos

## 🛠️ Tecnologias utilizadas

- Python
- FastAPI
- Uvicorn
- MongoDB Atlas
- PyMongo
- Requests
- BeautifulSoup
- APScheduler
- HTML5
- CSS3
- JavaScript

## 📊 Banco de dados

O projeto armazena o histórico de preços em documentos do MongoDB e utiliza **pipelines de agregação** para gerar estatísticas como:

- menor preço histórico;
- média dos preços dos últimos 30 dias.

Entre os operadores utilizados estão `$unwind`, `$group`, `$min`, `$filter` e `$avg`.

## ▶️ Como executar

### 1. Clone o repositório

```bash
git clone https://github.com/VitorHens/Radar-de-Pre-os.git
cd Radar-de-Pre-os
```

### 2. Instale as dependências

```bash
python -m pip install -r requirements.txt
```

### 3. Configure as variáveis de ambiente

Crie um arquivo `.env` com base no `.env.example`:

```env
MONGO_URI=
EMAIL_REMETENTE=
EMAIL_SENHA_APP=
EMAIL_DESTINO=
INTERVALO_MINUTOS=30
```

> Nunca publique credenciais reais no GitHub. O arquivo `.env` está incluído no `.gitignore`.

### 4. Inicie a API

```bash
python -m uvicorn main:app --reload
```

### 5. Abra a interface

Acesse:

```text
http://127.0.0.1:8000/site/
```

## 🔒 Segurança

O repositório mantém apenas o arquivo `.env.example`. Credenciais, senhas de aplicativo e URIs privadas devem permanecer somente no `.env` local. Consulte também [`SECURITY.md`](./SECURITY.md).

## 🎯 Objetivo do projeto

Praticar desenvolvimento de APIs em Python, banco de dados NoSQL, automação, web scraping e integração com envio de e-mails em uma aplicação completa.

---

Desenvolvido por **Vitor Hens**.
