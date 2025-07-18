from urllib.parse import urljoin
import time
import re
from bs4 import BeautifulSoup
import requests
import pandas as pd
from datetime import datetime
import logging

from flask import flash

logger = logging.getLogger(__name__)

class InventoryExecutor:
    BASE_API_URL = 'http://200.143.168.151:8880/siltwms/webresources'
    BASE_WMS_URL = 'http://200.143.168.151:8880/mwms/'
    API_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-HTTP-Method-Override': 'POST'
    }
    WMS_HEADERS = {
        'User-Agent': 'Mozilla/5.0',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    WMS_WAREHOUSE = '7.0,LUFT SOLUTIONS - AG2 - CAJAMAR - 16,S'

    def __init__(self, user1=None, pass1=None, user2=None, pass2=None, locais_banco=[], items_by_location=[]):
        
        self.wms_credentials = [
            {'username': user1, 'password': pass1},
            {'username': user2, 'password': pass2}
        ]
        
        self.user1 = user1
        self.pass1 = pass1
        self.user2 = user2
        self.pass2 = pass2
        
        self.locais_banco = locais_banco
        self.items_by_location = items_by_location
        self.inventory_id = self.create_inventory_scope()

    def _get_api_endpoints(self):
        return {
            'login': f'{self.BASE_API_URL}/SessionService/login',
            'save': f'{self.BASE_API_URL}/InventarioCRUD/save',
            'depositantes': f'{self.BASE_API_URL}/InventarioService/addDepositantesInventario',
            'usuarios': f'{self.BASE_API_URL}/InventarioService/getUsuarios',
            'add_usuarios': f'{self.BASE_API_URL}/InventarioService/addUsuarios',
            'locais': f'{self.BASE_API_URL}/InventarioService/getLocais',
            'add_locais': f'{self.BASE_API_URL}/InventarioService/addLocais',
            'liberar': f'{self.BASE_API_URL}/InventarioService/liberarInventario',
            'atualizar_critica': f'{self.BASE_API_URL}/InventarioService/atualizarCriticas'
        }

    def create_inventory_scope(self):
        api_session = requests.Session()
        endpoints = self._get_api_endpoints()

        # Authenticate
        login_payload = {
            "nomeUsuario": self.user1,
            "password": self.pass1,
            "armazem": {"id": 7, "descricao": "LUFT SOLUTIONS - AG2 - CAJAMAR - 16"}
        }
        
        login_response = api_session.post(endpoints['login'], json=login_payload, headers=self.API_HEADERS)
        
        id_usuario_logado = login_response.json()['value']['usuario']['id']
        
        if login_response.status_code != 200:
            raise Exception(f"Login failed with status {login_response.status_code}")

        bearer_token = login_response.json().get('value', {}).get('bearer')
        if not bearer_token:
            raise Exception("Authentication token not found")
        auth_headers = {**self.API_HEADERS, 'Authorization': f'Bearer {bearer_token}'}

        # Save inventory
        save_payload = {
            "entity": {
                "id": 0,
                "dataHora": int(datetime.now().timestamp() * 1000),
                "descricao": "Inventario",
                "armazem": {"id": 7, "descricao": "LUFT SOLUTIONS - AG2 - CAJAMAR - 16", "codigo": "7", "ativo": True},
                "idUsuario": {"id": id_usuario_logado, "nomeUsuario": self.user1, "ativo": True},
                "tipoInventario": "ROTATIVO",
                "tipoContagem": "PICKING_PULMAO",
                "sequenciaEscopoInventario": "BLOCORUAANDARPRODUTOLOTE",
                "finalizado": False,
                "geradoNf": False,
                "estoqueAtz": False,
                "estoqueEntrada": False,
                "estoqueSaida": False,
                "conferirLoteIndustria": False,
                "conferirDataVencimento": False,
                "conferirEstado": False,
                "conferenciaPorProduto": False,
                "inventarioTercerizado": False,
                "qtdeJuntoComBarra": True,
                "solicitaQtdeCaixa": False,
                "agruparContagemDoProduto": True,
                "permitirContDuplicadoProd": False,
                "permitirContagemDupPorEndereco": False,
                "liberarContagemMinPorEndereco": False,
                "ignorarContagemAutomaticamento": True,
                "liberarOndaPendente": True,
                "atualizaPickingInventario": False,
                "atualizaDadosLote": False,
                "valoralotesgravaestoque": False,
                "tipoPadraoIdentificacao": "EMBALAGEM"
            },
            "tela": "Cadastro de Inventário",
            "usuario": {"id": id_usuario_logado, "nomeUsuario": self.user1, "ativo": True}
        }
        save_response = api_session.post(endpoints['save'], json=save_payload, headers=auth_headers)
        if save_response.status_code != 200:
            raise Exception(f"Failed to save inventory with status {save_response.status_code}")

        inventory_id = save_response.json().get("id")
        if not inventory_id:
            raise Exception("Inventory ID not returned")

        # Add depositantes
        depositantes_payload = {
            "idInventario": inventory_id,
            "idUsuarioLogado": id_usuario_logado,
            "listaDepositantesAdd": [{"id": 2361178}]
        }
        depositantes_response = api_session.post(endpoints['depositantes'], json=depositantes_payload, headers=auth_headers)
        if depositantes_response.status_code != 204:
            raise Exception(f"Failed to add depositantes with status {depositantes_response.status_code}")

        # Fetch and add users
        usuarios_payload = {
            "idInventario": inventory_id,
            "config": {
                "@class": "SqlQueryResultTableConfig",
                "sqlQueryLoadMode": "DEFAULT",
                "queryType": "ROWID",
                "showAll": False,
                "onlyGenerateSql": False,
                "showQueryCount": False,
                "skip": 0,
                "take": 10000
            }
        }
        usuarios_response = api_session.post(endpoints['usuarios'], json=usuarios_payload, headers=auth_headers)
        if usuarios_response.status_code != 200:
            raise Exception(f"Failed to fetch users with status {usuarios_response.status_code}")

        allowed_users = [self.user1, self.user2]
        usuarios = [
            {
                "id": linha["columns"][4],
                "nomeUsuario": linha["columns"][1].strip().lower(),
                "ativo": True,
                "enviarSenha": False
            }
            for linha in usuarios_response.json().get("value", {}).get("lines", [])
            if len(linha.get("columns", [])) >= 5 and linha["columns"][1].strip().lower() in allowed_users
        ]

        if usuarios:
            add_usuarios_payload = {
                "idUsuarioAlteracao": id_usuario_logado,
                "idInventario": inventory_id,
                "adicionarUsuarios": usuarios
            }
            add_usuarios_response = api_session.post(endpoints['add_usuarios'], json=add_usuarios_payload, headers=auth_headers)
            if add_usuarios_response.status_code != 204:
                raise Exception(f"Failed to add users with status {add_usuarios_response.status_code}")

        locais = []
        for local in self.locais_banco:
            locais_payload = {
                "idInventario": inventory_id,
                "config": {
                    "@class": "SqlQueryResultTableConfig",
                    "sqlQueryLoadMode": "DEFAULT",
                    "queryType": "ROWID",
                    "showAll": False,
                    "onlyGenerateSql": False,
                    "showQueryCount": False,
                    "skip": 0,
                    "take": 10000,
                    "filterConfigs": [{"field": "IDLOCAL", "type": "string", "map": {"value": local}}]
                }
            }
            locais_response = api_session.post(endpoints['locais'], json=locais_payload, headers=auth_headers)
            if locais_response.status_code != 200:
                continue
            for linha in locais_response.json().get("value", {}).get("lines", []):
                colunas = linha.get("columns", [])
                if len(colunas) >= 2 and colunas[1]:
                    locais.append({"id": 0, "ativo": False, "local": colunas[1], "localIntegracao": 0})

        if not locais:
            raise Exception("No valid locations found to add")

        add_locais_payload = {
            "idUsuarioAlteracao": id_usuario_logado,
            "idInventario": inventory_id,
            "idUsuarioLogado": id_usuario_logado,
            "adicionarLocais": locais
        }
        add_locais_response = api_session.post(endpoints['add_locais'], json=add_locais_payload, headers=auth_headers)
        if add_locais_response.status_code != 204:
            raise Exception(f"Failed to add locations with status {add_locais_response.status_code}")

        # Release inventory
        liberar_payload = {"idInventario": inventory_id, "idUsuario": id_usuario_logado}
        liberar_response = api_session.post(endpoints['liberar'], json=liberar_payload, headers=auth_headers)
        if liberar_response.status_code != 204:
            raise Exception(f"Failed to release inventory with status {liberar_response.status_code}")

        return inventory_id

    def execute_inventory(self):
        for cred in self.wms_credentials:
            wms_session = requests.Session()
            wms_headers = {
                **self.WMS_HEADERS,
                'Referer': urljoin(self.BASE_WMS_URL, '/'),
                'Origin': self.BASE_WMS_URL
            }

            # Login
            login_url = urljoin(self.BASE_WMS_URL, 'servlet/LoginServlet')
            login_data = {'op': '1', 'nomeusuario': cred['username'], 'senha': cred['password']}
            login_response = wms_session.post(login_url, data=login_data, headers=wms_headers, allow_redirects=False)
            if login_response.status_code != 302:
                raise Exception(f"Login failed for user {cred['username']} with status {login_response.status_code}")

            # Select warehouse
            armazem_url = urljoin(self.BASE_WMS_URL, 'servlet/ArmazemServlet')
            wms_session.post(armazem_url, data={'armazem': self.WMS_WAREHOUSE}, headers=wms_headers)

            # Initialize inventory
            inventario_url = urljoin(self.BASE_WMS_URL, 'servlet/InventarioServlet')
            response = wms_session.get(f'{inventario_url}?op=1', headers=wms_headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            select = soup.find('select', {'id': 'inventario'})

            scope_ids = [re.sub(r'\D', '', option.text.strip()) for option in select.find_all('option')]
            scope_index = scope_ids.index(str(self.inventory_id))
            
            wms_session.post(inventario_url, data={'op': '1', 'inventario': scope_index}, headers=wms_headers)
                        
            location_groups = {}
            
            for item in self.items_by_location:
                local = str(item['Local']).strip()
                location_groups.setdefault(local, []).append(item)

            # Process inventory by location
            for local, items in location_groups.items():
                response_op3 = wms_session.post(inventario_url, data={'op': '2', 'local': local}, headers=wms_headers)
                if response_op3.status_code != 200:
                    continue
                time.sleep(0.5)

                # Process items in location
                for item in items:
                    code, qty = str(item['Codigo']).strip(), str(item['qtde']).strip()
                    if not code or not qty:
                        continue
                    wms_session.post(
                        inventario_url,
                        data={'op': '3', 'finalizar': 'N', 'qtde': qty, 'barra': code, 'tipo': '1'},
                        headers=wms_headers
                    )
                    time.sleep(0.5)

                # Finalize location
                wms_session.post(
                    inventario_url,
                    data={'op': '3', 'finalizar': 'S', 'qtde': '0', 'barra': '', 'tipo': '1'},
                    headers=wms_headers
                )
                time.sleep(0.5)

    def atualizar_critica(self):
        api_session = requests.Session()
        endpoints = self._get_api_endpoints()

        # Authenticate
        login_payload = {
            "nomeUsuario": self.user1,
            "password": self.pass1,
            "armazem": {"id": 7, "descricao": "LUFT SOLUTIONS - AG2 - CAJAMAR - 16"}
        }
        
        login_response = api_session.post(endpoints['login'], json=login_payload, headers=self.API_HEADERS)
        
        id_usuario_logado = login_response.json()['value']['usuario']['id']
        
        if login_response.status_code != 200:
            raise Exception(f"Login failed with status {login_response.status_code}")
    
        bearer_token = login_response.json().get('value', {}).get('bearer')
        
        if not bearer_token:
            raise Exception("Authentication token not found")
        
        auth_headers = {**self.API_HEADERS, 'Authorization': f'Bearer {bearer_token}'}
        
if __name__ == "__main__":
    InventoryExecutor(
                    user1='anderson.santos1', pass1='Luft@Solutions2025', user2='amanda.reis', pass2='luft@Solutions2025', 
                      locais_banco=['II111012101'], 
                      items_by_location=[{'Codigo': '7898677401786', 'qtde': 1, 'Local': 'II111012101'},
                                         {'Codigo': '7908556003168', 'qtde': 1, 'Local': 'II111012101'}]
                      ).execute_inventory()