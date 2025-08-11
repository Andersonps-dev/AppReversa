import requests
import pandas as pd
from datetime import datetime
import logging
from flask import flash
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker
import sys
import os
import tempfile

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import db
from models import Estoque

logger = logging.getLogger(__name__)

def extrair_dados_estoques_wms(link_wms, user_wms, senha_wms, id_depositante, armazem="insider%"):
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
        
        gerar_csv_response_json = gerar_csv_response.json()

        file_name = gerar_csv_response_json['value']['fileName']
        download_csv_url = f'http://200.143.168.151:8880/siltwms/tsunami/ExportServlet?ExportedFilename={file_name}'
        
        logger.info(f"Baixando o arquivo CSV: {file_name}...")
        download_response = session.get(download_csv_url, headers=headers)
        
        if download_response.status_code != 200:
            flash(f"Falha ao baixar o arquivo CSV! Status: {download_response.status_code}", 'error')
            return False
        
        # Use temporary file instead of instance folder
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as temp_file:
            temp_file.write(download_response.content)
            temp_file_path = temp_file.name

        logger.info(f"Arquivo salvo temporariamente em: {temp_file_path}")

        # Clear existing data in Estoque table
        db.session.query(Estoque).filter(Estoque.H_IDDEPOSITANTE == id_depositante).delete(synchronize_session=False)
        db.session.commit()


        df = pd.read_csv(temp_file_path, dtype={'Barra': str, 'Código do Produto': str, 'Código Produto Depositante': str})
        df = df[(df['Estado'] == 'NORMAL') & (df['Setor'].str.contains('BOM')) & (df['Tipo do Local'].str.contains('PICKING'))]
        # df = df[df['Local'].str[6:8].astype(int) < 23]
        
        # Function to convert 'S'/'N' to boolean
        def to_boolean(value):
            if isinstance(value, str):
                return value.upper() == 'S'
            return bool(value)

        for _, row in df.iterrows():
            local = row.get('Local', '')
            estoque = Estoque(
                Local=row.get('Local', ''),
                Rua=local[2:5],
                F_IDLOCAL=row.get('F$IDLOCAL', ''),
                Tipo_do_Local=row.get('Tipo do Local', ''),
                Estado=row.get('Estado', ''),
                Buffer=to_boolean(row.get('Buffer', False)),
                Local_Ativo=to_boolean(row.get('Local Ativo', False)),
                Setor=row.get('Setor', ''),
                Regiao=row.get('Região', ''),
                Estoque=row.get('Estoque', 0),
                Pendencia=row.get('Pendência', 0),
                Adicionar=row.get('Adicionar', 0),
                Disponivel=row.get('Disponível', 0),
                Barra=row.get('Barra', ''),
                Descricao_Reduzida=row.get('Descrição Reduzida', ''),
                idProduto=row.get('idProduto', ''),
                Codigo_do_Produto=row.get('Código do Produto', ''),
                Codigo_Produto_Depositante=row.get('Código Produto Depositante', ''),
                Produto=row.get('Produto', ''),
                Depositante=row.get('Depositante', ''),
                Tipo=row.get('Tipo', ''),
                H_IDARMAZEM=row.get('H$IDARMAZEM', ''),
                H_IDDEPOSITANTE=row.get('H$IDDEPOSITANTE', ''),
                H_ORDEM=row.get('H$ORDEM', ''),
                H_RN=row.get('H$RN', ''),
                data_atualizacao=datetime.now()
            )
            db.session.add(estoque)
        
        db.session.commit()
        logger.info("Dados salvos com sucesso no banco de dados PostgreSQL, tabela: estoque")
        
        # Clean up temporary file
        os.unlink(temp_file_path)
        return True

    except Exception as e:
        logger.error(f"❌ Erro crítico: {e}")
        flash(f"Erro ao atualizar dados de estoque: {e}", "error")
        db.session.rollback()
        return False