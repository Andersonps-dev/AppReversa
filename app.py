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
import io
from sqlalchemy import func
from config import LINK_WMS, LOGINS_WMS, SENHAS_WMS, ID_TOKEN_WMS, TOKENS_SENHAS

# app = Flask(__name__)

# app.config['SECRET_KEY'] = 'admin_anderson_luft'
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# db.init_app(app)
# migrate = Migrate(app, db)

id_depositante = 2361178
user_wms = LOGINS_WMS[0]
senha_wms = SENHAS_WMS[0]
id_token_wms = ID_TOKEN_WMS[0]
token_senha_wms = TOKENS_SENHAS[0]

def extrair_dados_estoques():
    from models import Estoque
    login_url = LINK_WMS + r'webresources/SessionService/login'
    login_data = {
        "nomeUsuario": user_wms,
        "password": senha_wms,
        "armazem": {
            "id": 7,
            "descricao": "LUFT SOLUTIONS - AG2 - CAJAMAR - 16"
        }
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    session = requests.Session()
    try:
        response = session.get(LINK_WMS, headers=headers)
        response = session.post(login_url, json=login_data, headers=headers)
        response.raise_for_status()
        response_json = response.json()
        bearer_token = response_json.get('value', {}).get('bearer')
        if not bearer_token:
            raise Exception('Token de autenticação não encontrado!')
        headers['Authorization'] = f'Bearer {bearer_token}'
        consulta_estoque_url = LINK_WMS + r'webresources/ConsultaEstoqueService/getConsultaEstoqueLocalPorProduto'
        consulta_estoque_data = {
            "idDepositante": id_depositante,
            "idArmazem": 7,
            "config": {
                "@class": "SqlQueryResultSlickConfig",
                "sqlQueryLoadMode": "VALUES",
                "queryType": "TABLEID",
                "showAll": True,
                "orderBy": None,
                "customWhere": None,
                "scalarTypes": {
                    "BUFFER": "java.lang.Boolean",
                    "LOCALATIVO": "java.lang.Boolean"
                },
                "showFilter": [],
                "filterConfigs": [],
                "take": 1000,
                "skip": 0,
                "advancedSearch": [],
                "parameters": None,
                "onlyGenerateSql": False,
                "dynamicParameters": None
            }
        }
        consulta_response = session.post(consulta_estoque_url, json=consulta_estoque_data, headers=headers)
        consulta_response.raise_for_status()
        consulta_response_json = consulta_response.json()
        dados = consulta_response_json.get('value', {}).get('data', [])
        
        if not dados:
            print('Nenhum dado de estoque retornado!')
            return
        Estoque.query.delete()
        for item in dados:
            estoque = Estoque(
                local=item.get('Local', ''),
                f_idlocal=item.get('F$IDLOCAL', ''),
                tipo_local=item.get('Tipo do Local', ''),
                estado=item.get('Estado', ''),
                buffer=item.get('Buffer', ''),
                local_ativo=item.get('Local Ativo', ''),
                setor=item.get('Setor', ''),
                regiao=item.get('RegiÃ£o', ''),
                estoque=item.get('Estoque', ''),
                pendencia=item.get('PendÃªncia', ''),
                adicionar=item.get('Adicionar', ''),
                disponivel=item.get('DisponÃ­vel', ''),
                barra=item.get('Barra', ''),
                descricao_reduzida=item.get('DescriÃ§Ã£o Reduzida', ''),
                id_produto=item.get('idProduto', ''),
                codigo_produto=item.get('CÃ³digo do Produto', ''),
                codigo_produto_depositante=item.get('CÃ³digo Produto Depositante', ''),
                produto=item.get('Produto', ''),
                depositante=item.get('Depositante', ''),
                tipo=item.get('Tipo', ''),
                h_idarmazem=item.get('H$IDARMAZEM', ''),
                h_iddepositante=item.get('H$IDDEPOSITANTE', ''),
                h_ordem=item.get('H$ORDEM', ''),
                h_rn=item.get('H$RN', '')
            )
            db.session.add(estoque)
        db.session.commit()
        print('Dados de estoque gravados no banco de dados com sucesso!')
    except requests.RequestException as req_err:
        print(f'Erro de requisição: {req_err}')
    except Exception as e:
        print(f'Erro inesperado: {e}')

if __name__ == '__main__':
    # app.run(debug=True)
    extrair_dados_estoques()