import requests

api_session = requests.Session()

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}


login_payload = {
    "nomeUsuario": 'anderson.santos1',
    "password": 'Luft@Solutions2025',
    "armazem": {"id": 7, "descricao": "LUFT SOLUTIONS - AG2 - CAJAMAR - 16"}
}

login_response = api_session.post('http://200.143.168.151:8880/siltwms/webresources/SessionService/login', json=login_payload, headers=headers)

bearer_token = login_response.json().get('value', {}).get('bearer', '')

headers.update({
    'Authorization': f'Bearer {bearer_token}',
    'X-HTTP-Method-Override': 'POST'
})

print(login_response.status_code)
#---------------------------------------------------------------------------------------------
json_data_getInventario = {
    'idArmazem': 7,
    'config': {
        '@class': 'SqlQueryResultSlickConfig',
        'sqlQueryLoadMode': 'VALUES',
        'queryType': 'ROWID',
        'showAll': False,
        'orderBy': None,
        'customWhere': None,
        'scalarTypes': {},
        'showFilter': [
            0,
        ],
        'filterConfigs': [],
        'take': 40,
        'skip': 0,
        'advancedSearch': [],
        'parameters': None,
        'onlyGenerateSql': False,
        'dynamicParameters': None,
    },
}

response_inventario = api_session.post(
    'http://200.143.168.151:8880/siltwms/webresources/InventarioService/getInventarios',
    headers=headers,
    json=json_data_getInventario,
)

print(response_inventario.status_code)

#---------------------------------------------------------------------------------------------
json_data_monitorar = {
    'idInventario': 415149,
    'config': {
        '@class': 'SqlQueryResultTableConfig',
        'sqlQueryLoadMode': 'METADATA',
        'queryType': 'ROWID',
        'showAll': False,
        'orderBy': 'H$IDINVDET1 ASC',
        'customWhere': None,
        'scalarTypes': {},
        'showFilter': [
            0,
        ],
        'filterConfigs': [],
        'take': 50,
        'skip': 0,
        'advancedSearch': [],
        'parameters': None,
        'onlyGenerateSql': False,
        'dynamicParameters': None,
        'showQueryCount': True,
    },
}

response_critica = api_session.post(
    'http://200.143.168.151:8880/siltwms/webresources/InventarioService/getMonitorarInventarios',
    headers=headers,
    json=json_data_monitorar,
)

print(response_critica.status_code)

#---------------------------------------------------------------------------------------------
json_data_atualizar_critica = {
    'idInventario': 415149,
    'idUsuarioLogado': 6501,
}

response_critica = api_session.post(
    'http://200.143.168.151:8880/siltwms/webresources/InventarioService/atualizarCriticas',
    headers=headers,
    json=json_data_atualizar_critica,
)

print(response_critica.status_code)

#---------------------------------------------------------------------------------------------
json_data_bloqueio_contagem ={
    'idInventario': 415149,
    'idUsuario': 6501,
}

response_bloqueio = requests.post(
    'http://200.143.168.151:8880/siltwms/webresources/InventarioService/bloquearInventario',
    headers=headers,
    json=json_data_bloqueio_contagem,
)

print(response_bloqueio.status_code)
#---------------------------------------------------------------------------------------------