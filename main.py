import json
import os
import re
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pymongo import MongoClient
from pymongo.server_api import ServerApi

load_dotenv()

app = FastAPI(title="Radar de Preços")
app.mount("/site", StaticFiles(directory="frontend", html=True), name="site")

MONGO_URI = os.getenv("MONGO_URI")
INTERVALO_MINUTOS = int(os.getenv("INTERVALO_MINUTOS", "30"))

client = MongoClient(MONGO_URI, server_api=ServerApi("1"))
db = client["projeto_precos"]
colecao = db["produtos"]

EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE")
EMAIL_SENHA_APP = os.getenv("EMAIL_SENHA_APP")
EMAIL_DESTINO = os.getenv("EMAIL_DESTINO")

HEADERS_SCRAPING = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}

scheduler = BackgroundScheduler()


class ProdutoCreate(BaseModel):
    nome: str
    url: str
    preco: float = Field(gt=0)
    preco_meta: float | None = Field(default=None, gt=0)


class PrecoUpdate(BaseModel):
    novo_preco: float = Field(gt=0)


def enviar_alerta_email(assunto: str, mensagem: str):
    if not EMAIL_REMETENTE or not EMAIL_SENHA_APP or not EMAIL_DESTINO:
        print("E-mail não configurado. Alerta não enviado.")
        return

    msg = MIMEText(mensagem)
    msg["Subject"] = assunto
    msg["From"] = EMAIL_REMETENTE
    msg["To"] = EMAIL_DESTINO

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as servidor:
            servidor.login(EMAIL_REMETENTE, EMAIL_SENHA_APP)
            servidor.send_message(msg)
        print("Alerta enviado por e-mail.")
    except Exception as erro:
        print(f"Erro ao enviar e-mail: {erro}")


def limpar_preco(valor):
    try:
        texto = str(valor).replace("R$", "").strip()
        if "," in texto and "." in texto:
            texto = texto.replace(".", "").replace(",", ".")
        elif "," in texto:
            texto = texto.replace(",", ".")
        return float(texto)
    except (ValueError, TypeError):
        return None


def procurar_preco_json(dados):
    if isinstance(dados, dict):
        if "offers" in dados:
            ofertas = dados["offers"]
            if isinstance(ofertas, list):
                ofertas = ofertas[0] if ofertas else {}
            if isinstance(ofertas, dict) and ofertas.get("price"):
                preco = limpar_preco(ofertas["price"])
                if preco is not None:
                    return preco
        for valor in dados.values():
            resultado = procurar_preco_json(valor)
            if resultado is not None:
                return resultado
    elif isinstance(dados, list):
        for item in dados:
            resultado = procurar_preco_json(item)
            if resultado is not None:
                return resultado
    return None


def buscar_preco(url: str):
    try:
        resposta = requests.get(url, headers=HEADERS_SCRAPING, timeout=15)
        resposta.raise_for_status()
    except Exception as erro:
        print(f"Erro ao acessar {url}: {erro}")
        return None

    soup = BeautifulSoup(resposta.text, "html.parser")

    for propriedade in ["product:price:amount", "og:price:amount"]:
        tag = soup.find("meta", attrs={"property": propriedade})
        if tag and tag.get("content"):
            preco = limpar_preco(tag["content"])
            if preco is not None:
                return preco

    tag = soup.find("meta", attrs={"itemprop": "price"})
    if tag and tag.get("content"):
        preco = limpar_preco(tag["content"])
        if preco is not None:
            return preco

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            dados = json.loads(script.string)
            preco = procurar_preco_json(dados)
            if preco is not None:
                return preco
        except (TypeError, json.JSONDecodeError):
            continue

    encontrado = re.search(r"R\$\s?(\d{1,3}(?:\.\d{3})*,\d{2})", soup.get_text())
    if encontrado:
        return limpar_preco(encontrado.group(1))
    return None


def verificar_meta(produto, novo_preco: float):
    """Envia somente um aviso enquanto o preço permanecer abaixo da mesma meta."""
    meta = produto.get("preco_meta")
    if meta is None:
        return False

    if novo_preco <= meta and not produto.get("meta_atingida", False):
        colecao.update_one(
            {"_id": produto["_id"]},
            {"$set": {"meta_atingida": True, "ultimo_alerta": datetime.now()}},
        )
        enviar_alerta_email(
            f"Meta atingida: {produto['nome']}",
            f"O produto {produto['nome']} atingiu sua meta.\n\n"
            f"Meta: R$ {meta:.2f}\nPreço atual: R$ {novo_preco:.2f}",
        )
        return True

    if novo_preco > meta and produto.get("meta_atingida", False):
        colecao.update_one({"_id": produto["_id"]}, {"$set": {"meta_atingida": False}})
    return False


def registrar_preco(produto, novo_preco: float):
    alerta_enviado = verificar_meta(produto, novo_preco)
    colecao.update_one(
        {"_id": produto["_id"]},
        {
            "$set": {"preco": novo_preco},
            "$push": {"historico_precos": {"data": datetime.now(), "preco": novo_preco}},
        },
    )
    return alerta_enviado


def atualizar_todos_os_precos():
    """Função chamada pelo agendador a cada intervalo definido no .env."""
    atualizados = 0
    falhas = 0
    alertas = 0

    for produto in colecao.find({}):
        preco_novo = buscar_preco(produto.get("url", ""))
        if preco_novo is None:
            falhas += 1
            continue
        if registrar_preco(produto, preco_novo):
            alertas += 1
        atualizados += 1

    print(f"Monitoramento concluído: {atualizados} atualizados, {falhas} falhas.")
    return {"atualizados": atualizados, "falhas": falhas, "alertas": alertas}


@app.on_event("startup")
def iniciar_monitoramento():
    scheduler.add_job(
        atualizar_todos_os_precos,
        "interval",
        minutes=INTERVALO_MINUTOS,
        id="monitorar_precos",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    print(f"Monitoramento automático iniciado: a cada {INTERVALO_MINUTOS} minutos.")


@app.on_event("shutdown")
def parar_monitoramento():
    if scheduler.running:
        scheduler.shutdown()


@app.get("/")
def inicio():
    return {"mensagem": "Radar de preços funcionando!"}


@app.post("/produto")
def cadastrar_produto(dados: ProdutoCreate):
    if colecao.find_one({"nome": dados.nome}):
        return {"erro": "Já existe um produto cadastrado com esse nome."}

    produto = {
        "nome": dados.nome,
        "url": dados.url,
        "preco": dados.preco,
        "preco_meta": dados.preco_meta,
        "meta_atingida": False,
        "historico_precos": [{"data": datetime.now(), "preco": dados.preco}],
    }
    resultado = colecao.insert_one(produto)
    produto["_id"] = resultado.inserted_id
    alerta_enviado = verificar_meta(produto, dados.preco)
    return {"mensagem": "Produto cadastrado com sucesso!", "alerta_enviado": alerta_enviado}


@app.get("/produtos")
def listar_produtos():
    return list(colecao.find({}, {"_id": 0, "nome": 1, "preco": 1, "url": 1, "preco_meta": 1, "meta_atingida": 1}))


@app.delete("/produto/{nome}")
def excluir_produto(nome: str):
    resultado = colecao.delete_one({"nome": nome})
    if resultado.deleted_count == 0:
        return {"erro": "Produto não encontrado."}
    return {"mensagem": "Produto excluído com sucesso!"}


@app.put("/produto/{nome}")
def atualizar_preco(nome: str, dados: PrecoUpdate):
    produto = colecao.find_one({"nome": nome})
    if produto is None:
        return {"erro": "Produto não encontrado."}
    alerta_enviado = registrar_preco(produto, dados.novo_preco)
    return {"mensagem": "Novo preço registrado!", "preco": dados.novo_preco, "alerta_enviado": alerta_enviado}


@app.put("/produto/{nome}/atualizar-automatico")
def atualizar_preco_automatico(nome: str):
    produto = colecao.find_one({"nome": nome})
    if produto is None:
        return {"erro": "Produto não encontrado."}

    preco_novo = buscar_preco(produto.get("url", ""))
    if preco_novo is None:
        return {"erro": "Não foi possível encontrar o preço nessa página."}

    alerta_enviado = registrar_preco(produto, preco_novo)
    return {"mensagem": "Preço atualizado via scraping!", "preco": preco_novo, "alerta_enviado": alerta_enviado}


@app.post("/monitoramento/agora")
def monitorar_agora():
    return atualizar_todos_os_precos()


@app.get("/produto")
def consultar_metricas():
    data_limite = datetime.now() - timedelta(days=30)
    resultado = colecao.aggregate([
        {"$unwind": "$historico_precos"},
        {"$group": {
            "_id": "$nome",
            "menor_preco": {"$min": "$historico_precos.preco"},
            "historico": {"$push": "$historico_precos"},
        }},
        {"$project": {
            "menor_preco": 1,
            "ultimos_30_dias": {
                "$filter": {
                    "input": "$historico",
                    "as": "item",
                    "cond": {"$gte": ["$$item.data", data_limite]},
                }
            }
        }},
        {"$project": {
            "menor_preco": 1,
            "media_30_dias": {"$avg": "$ultimos_30_dias.preco"},
        }},
    ])
    return list(resultado)


@app.get("/historico/{nome}")
def consultar_historico(nome: str):
    produto = colecao.find_one({"nome": nome})
    if produto is None:
        return {"erro": "Produto não encontrado."}
    return {"nome": produto["nome"], "historico_precos": produto["historico_precos"]}


@app.get("/meta/{nome}")
def consultar_meta(nome: str):
    produto = colecao.find_one({"nome": nome})
    if produto is None:
        return {"erro": "Produto não encontrado."}
    meta = produto.get("preco_meta")
    if meta is None:
        return {"mensagem": "Este produto ainda não possui uma meta de preço.", "atingida": False}
    atingida = produto["preco"] <= meta
    return {
        "mensagem": "Meta atingida!" if atingida else "Meta ainda não foi atingida.",
        "atingida": atingida,
        "meta": meta,
        "preco_atual": produto["preco"],
    }


try:
    client.admin.command("ping")
    print("Conexão estabelecida com sucesso com o MongoDB Atlas!")
except Exception as erro:
    print(f"Erro ao conectar: {erro}")
