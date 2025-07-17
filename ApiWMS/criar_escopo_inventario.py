import requests
import json
from datetime import datetime
import pandas as pd

def criar_escopo_inventario():
    BASE_URL = 'http://200.143.168.151:8880/siltwms/webresources'
    ENDPOINTS = {
        'login': f'{BASE_URL}/SessionService/login',
        'save': f'{BASE_URL}/InventarioCRUD/save',
        'depositantes': f'{BASE_URL}/InventarioService/addDepositantesInventario',
        'usuarios': f'{BASE_URL}/InventarioService/getUsuarios',
        'add_usuarios': f'{BASE_URL}/InventarioService/addUsuarios',
        'locais': f'{BASE_URL}/InventarioService/getLocais',
        'add_locais': f'{BASE_URL}/InventarioService/addLocais',
        'liberar': f'{BASE_URL}/InventarioService/liberarInventario'
    }
    
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-HTTP-Method-Override': 'POST'
    }

    login_payload = {
        "nomeUsuario": "ANDERSON.SANTOS1",
        "password": "Luft@Solutions2025",
        "armazem": {"id": 7, "descricao": "LUFT SOLUTIONS - AG2 - CAJAMAR - 16"}
    }
    login_response = session.post(ENDPOINTS['login'], json=login_payload, headers=headers)
    if login_response.status_code != 200:
        raise Exception(f"Login failed with status {login_response.status_code}")
    bearer_token = login_response.json().get('value', {}).get('bearer')
    if not bearer_token:
        raise Exception("Authentication token not found")
    headers['Authorization'] = f'Bearer {bearer_token}'

    save_payload = {
        "entity": {
            "id": 0,
            "dataHora": int(datetime.now().timestamp() * 1000),
            "descricao": "Inventario",
            "armazem": {"id": 7, "descricao": "LUFT SOLUTIONS - AG2 - CAJAMAR - 16", "codigo": "7", "ativo": True},
            "idUsuario": {"id": 6501, "nomeUsuario": "ANDERSON.SANTOS1", "ativo": True},
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
        "usuario": {"id": 6501, "nomeUsuario": "ANDERSON.SANTOS1", "ativo": True}
    }
    save_response = session.post(ENDPOINTS['save'], json=save_payload, headers=headers)
    if save_response.status_code != 200:
        raise Exception(f"Failed to save inventory with status {save_response.status_code}")
    inventario_id = save_response.json().get("id")
    if not inventario_id:
        raise Exception("Inventory ID not returned")

    depositantes_payload = {
        "idInventario": inventario_id,
        "idUsuarioLogado": 6501,
        "listaDepositantesAdd": [{"id": 2361178}]
    }
    depositantes_response = session.post(ENDPOINTS['depositantes'], json=depositantes_payload, headers=headers)
    if depositantes_response.status_code != 204:
        raise Exception(f"Failed to add depositantes with status {depositantes_response.status_code}")

    usuarios_payload = {
        "idInventario": inventario_id,
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
    usuarios_response = session.post(ENDPOINTS['usuarios'], json=usuarios_payload, headers=headers)
    if usuarios_response.status_code != 200:
        raise Exception(f"Failed to fetch users with status {usuarios_response.status_code}")
    
    usuarios = []
    for linha in usuarios_response.json().get("value", {}).get("lines", []):
        columns = linha.get("columns", [])
        if len(columns) >= 5 and columns[1].strip().lower() in ["jadson.sales", "anderson.santos1", "amanda.reis"]:
            usuarios.append({
                "id": columns[4],
                "nomeUsuario": columns[1].strip().lower(),
                "ativo": True,
                "enviarSenha": False
            })
    
    if usuarios:
        add_usuarios_payload = {
            "idUsuarioAlteracao": 6501,
            "idInventario": inventario_id,
            "adicionarUsuarios": usuarios
        }
        add_usuarios_response = session.post(ENDPOINTS['add_usuarios'], json=add_usuarios_payload, headers=headers)
        if add_usuarios_response.status_code != 204:
            raise Exception(f"Failed to add users with status {add_usuarios_response.status_code}")

    df = pd.read_excel(r"C:\Users\anderson.santos\Downloads\inventario teste sistema.xlsx")
    if 'Local' not in df.columns:
        raise Exception("Column 'Local' not found in spreadsheet")
    
    locais = []
    for local in df['Local'].dropna().unique():
        locais_payload = {
            "idInventario": inventario_id,
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
        locais_response = session.post(ENDPOINTS['locais'], json=locais_payload, headers=headers)
        if locais_response.status_code != 200:
            continue
        for linha in locais_response.json().get("value", {}).get("lines", []):
            colunas = linha.get("columns", [])
            if len(colunas) >= 2 and colunas[1]:
                locais.append({"id": 0, "ativo": False, "local": colunas[1], "localIntegracao": 0})

    if not locais:
        raise Exception("No valid locations found to add")
    
    add_locais_payload = {
        "idUsuarioAlteracao": 6501,
        "idInventario": inventario_id,
        "idUsuarioLogado": 6501,
        "adicionarLocais": locais
    }
    add_locais_response = session.post(ENDPOINTS['add_locais'], json=add_locais_payload, headers=headers)
    if add_locais_response.status_code != 204:
        raise Exception(f"Failed to add locations with status {add_locais_response.status_code}")

    # Liberar Inventario
    liberar_payload = {"idInventario": inventario_id, "idUsuario": 6501}
    liberar_response = session.post(ENDPOINTS['liberar'], json=liberar_payload, headers=headers)
    if liberar_response.status_code != 204:
        raise Exception(f"Failed to release inventory with status {liberar_response.status_code}")

if __name__ == "__main__":
    criar_escopo_inventario()