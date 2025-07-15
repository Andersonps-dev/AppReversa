from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from database import db
from flask_migrate import Migrate
import requests
import json
import os
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime, date, timedelta
import sqlite3
from functools import wraps
import logging
from sqlalchemy import func
from models import Estoque
from config import LINK_WMS, LOGINS_WMS, SENHAS_WMS, ID_TOKEN_WMS, TOKENS_SENHAS

app = Flask(__name__)

app.config['SECRET_KEY'] = 'admin_anderson_luft'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extrair_dados_estoques_wms(link_wms, user_wms, senha_wms, id_depositante=2361178, armazem="insider%", save_path=app.instance_path):
    try:
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
        bearer_token = response.json().get('value', {}).get('bearer')
        headers['Authorization'] = f'Bearer {bearer_token}'
        
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
            flash(f"Falha na consulta de estoque! Status: {consulta_response.status_code}", 'error')
            return False
        
        logger.info("Consulta de estoque realizada com sucesso!")
        
        gerar_csv_data = {
            "idDepositante": id_depositante,
            "idArmazem": 7,
            "config": {
                "@class": "SqlQueryResultCsvConfig",
                "sqlQueryLoadMode": "VALUES",
                "queryType": "TABLEID",
                "showAll": True,
                "orderBy": None,
                "customWhere": None,
                "scalarTypes": {
                    "BUFFER": "java.lang.Boolean",
                    "LOCALATIVO": "java.lang.Boolean"
                },
                "separator": 1,
                "showFilter": [],
                "filterConfigs": [],
                "take": 40,
                "skip": 0,
                "advancedSearch": [],
                "parameters": None,
                "onlyGenerateSql": False,
                "dynamicParameters": None,
                "visibleColumnIndex": ""
            }
        }
        
        logger.info("Gerando CSV...")
        gerar_csv_response = session.post(consulta_estoque_url, json=gerar_csv_data, headers=headers)
        
        if gerar_csv_response.status_code != 200:
            flash(f"Falha ao gerar o CSV! Status: {gerar_csv_response.status_code}", 'error')
            return False
            
        logger.info("CSV gerado com sucesso!")
        gerar_csv_response_json = gerar_csv_response.json()

        file_name = gerar_csv_response_json['value']['fileName']
        download_csv_url = f'http://200.143.168.151:8880/siltwms/tsunami/ExportServlet?ExportedFilename={file_name}'
        
        logger.info(f"Baixando o arquivo CSV: {file_name}...")
        download_response = session.get(download_csv_url, headers=headers)
        
        if download_response.status_code != 200:
            flash(f"Falha ao baixar o arquivo CSV! Status: {download_response.status_code}", 'error')
            return False
            
        logger.info("Arquivo baixado com sucesso!")
        
        novo_nome = "Estoque Local Por Produto"
        full_path = os.path.join(save_path, novo_nome + ".csv")
        
        save_dir = os.path.dirname(full_path)
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
            
        with open(full_path, 'wb') as file:
            file.write(download_response.content)
        logger.info(f"Arquivo salvo em: {full_path}")

        db_path = os.path.join(save_path, "database.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('DROP TABLE IF EXISTS estoque')
        except:
            pass
            
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS estoque (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                Local TEXT,
                F_IDLOCAL TEXT,
                Tipo_do_Local TEXT,
                Estado TEXT,
                Buffer BOOLEAN,
                Local_Ativo BOOLEAN,
                Setor TEXT,
                Regiao TEXT,
                Estoque INTEGER,
                Pendencia INTEGER,
                Adicionar INTEGER,
                Disponivel INTEGER,
                Barra TEXT,
                Descricao_Reduzida TEXT,
                idProduto TEXT,
                Codigo_do_Produto TEXT,
                Codigo_Produto_Depositante TEXT,
                Produto TEXT,
                Depositante TEXT,
                Tipo TEXT,
                H_IDARMAZEM TEXT,
                H_IDDEPOSITANTE TEXT,
                H_ORDEM TEXT,
                H_RN TEXT,
                data_atualizacao DATETIME
            )
        ''')

        df = pd.read_csv(full_path) 
        for _, row in df.iterrows():
            cursor.execute('''
                INSERT INTO estoque (
                    Local, F_IDLOCAL, Tipo_do_Local, Estado, Buffer, Local_Ativo, Setor, Regiao,
                    Estoque, Pendencia, Adicionar, Disponivel, Barra, Descricao_Reduzida,
                    idProduto, Codigo_do_Produto, Codigo_Produto_Depositante, Produto,
                    Depositante, Tipo, H_IDARMAZEM, H_IDDEPOSITANTE, H_ORDEM, H_RN, data_atualizacao
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                row.get('Local', ''),
                row.get('F$IDLOCAL', ''),
                row.get('Tipo do Local', ''),
                row.get('Estado', ''),
                row.get('Buffer', False),
                row.get('Local Ativo', False),
                row.get('Setor', ''),
                row.get('Região', ''),
                row.get('Estoque', 0),
                row.get('Pendência', 0),
                row.get('Adicionar', 0),
                row.get('Disponível', 0),
                row.get('Barra', ''),
                row.get('Descrição Reduzida', ''),
                row.get('idProduto', ''),
                row.get('Código do Produto', ''),
                row.get('Código Produto Depositante', ''),
                row.get('Produto', ''),
                row.get('Depositante', ''),
                row.get('Tipo', ''),
                row.get('H$IDARMAZEM', ''),
                row.get('H$IDDEPOSITANTE', ''),
                row.get('H$ORDEM', ''),
                row.get('H$RN', ''),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))

        conn.commit()
        conn.close()
        logger.info(f"Dados salvos com sucesso no banco de dados: {db_path}, tabela: estoque")
        flash("Dados de estoque atualizados com sucesso!", "success")
        return True

    except Exception as e:
        logger.error(f"❌ Erro crítico: {e}")
        flash(f"Erro ao atualizar dados de estoque: {e}", "error")
        return False

@app.route('/')
def index():
    estoques = Estoque.query.limit(20).all()
    return render_template('index.html', estoques=estoques)

@app.route('/atualizar_estoque', methods=['POST'])
def atualizar_estoque():
    success = extrair_dados_estoques_wms(
        link_wms=LINK_WMS,
        user_wms=LOGINS_WMS[0],
        senha_wms=SENHAS_WMS[0],
        save_path=app.instance_path
    )
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)