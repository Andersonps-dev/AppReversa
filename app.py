from flask import Flask, render_template, request, redirect, url_for, session, flash, g, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from database import db
from flask_migrate import Migrate
import requests
import json
import os
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime, date, timedelta
from functools import wraps
import logging
from sqlalchemy import func
from models import Estoque
from config import LINK_WMS, LOGINS_WMS, SENHAS_WMS, ID_TOKEN_WMS, TOKENS_SENHAS

# Configuração do Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'admin_anderson_luft'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extrair_dados_estoques_wms(link_wms, user_wms, senha_wms, id_depositante=538607, armazem="alpargatas%"):
    try:
        # Configuração inicial
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        
        session = requests.Session()
        
        # Login
        login_url = link_wms + r'webresources/SessionService/login'
        login_data = {
            "nomeUsuario": user_wms,
            "password": senha_wms,
            "armazem": {
                "id": 7,
                "descricao": "LUFT SOLUTIONS - AG2 - CAJAMAR - 16"
            }
        }
        
        session.get(link_wms, headers=headers)
        response = session.post(login_url, json=login_data, headers=headers)
        if response.status_code != 200:
            logger.error(f"Falha no login WMS! Status: {response.status_code}")
            return False
            
        bearer_token = response.json().get('value', {}).get('bearer')
        headers['Authorization'] = f'Bearer {bearer_token}'
        
        # Consulta de estoque
        consulta_estoque_url = link_wms + r'webresources/ConsultaEstoqueService/getConsultaEstoqueLocalPorProduto'
        consulta_estoque_data = {
            "idDepositante": id_depositante,
            "idArmazem": 7,
            "config": {
                "@class": "SqlQueryResultSlickConfig",
                "sqlQueryLoadMode": "VALUES",
                "queryType": "TABLEID",
                "showAll": False,
                "orderBy": None,
                "customWhere": None,
                "scalarTypes": {
                    "BUFFER": "java.lang.Boolean",
                    "LOCALATIVO": "java.lang.Boolean"
                },
                "showFilter": [],
                "filterConfigs": [],
                "take": 40,
                "skip": 0,
                "advancedSearch": [],
                "parameters": None,
                "onlyGenerateSql": False,
                "dynamicParameters": None
            }
        }
        
        consulta_response = session.post(consulta_estoque_url, json=consulta_estoque_data, headers=headers)
        
        if consulta_response.status_code != 200:
            logger.error(f"Falha na consulta de estoque! Status: {consulta_response.status_code}")
            return False
            
        logger.info("Consulta de estoque realizada com sucesso!")
        consulta_response_json = consulta_response.json()
        
        # Processar dados e salvar no banco
        estoque_data = consulta_response_json.get('value', [])
        
        for item in estoque_data:
            try:
                # Assumindo que Estoque model tem campos como codigo_produto, quantidade, local, etc.
                estoque = Estoque(
                    codigo_produto=item.get('CODIGO', ''),
                    quantidade=item.get('QUANTIDADE', 0),
                    local=item.get('LOCAL', ''),
                    data_atualizacao=datetime.now(),
                    armazem=armazem,
                    depositante_id=id_depositante
                )
                db.session.add(estoque)
            except Exception as e:
                logger.error(f"Erro ao salvar item no banco: {e}")
                continue
                
        db.session.commit()
        logger.info("Dados de estoque salvos no banco com sucesso!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro crítico: {e}")
        db.session.rollback()
        return False

@app.route('/sync_estoque', methods=['POST'])
def sync_estoque():
    try:
        success = extrair_dados_estoques_wms(
            link_wms=LINK_WMS,
            user_wms=LOGINS_WMS[0],
            senha_wms=SENHAS_WMS[0]
        )
        if success:
            flash('Estoque sincronizado com sucesso!', 'success')
        else:
            flash('Falha ao sincronizar estoque.', 'error')
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Erro na rota /sync_estoque: {e}")
        flash('Erro ao sincronizar estoque.', 'error')
        return redirect(url_for('index'))

@app.route('/')
def index():
    estoques = Estoque.query.all()
    return render_template('index.html', estoques=estoques)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)