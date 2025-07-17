import requests
import orjson
import pandas as pd

def ativar_locais(
    base_url='http://200.143.168.151:8880/siltwms/webresources',
    id_armazem=7,
    usuario_id=6501,
    local_ativo=True,
    excel_path=r"C:\Users\anderson.santos\Downloads\inventario teste sistema.xlsx",
    excel_coluna_local="Local"
):
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-HTTP-Method-Override': 'POST'
    }

    login_data = {
        "nomeUsuario": "ANDERSON.SANTOS1",
        "password": "Luft@Solutions2025",
        "armazem": {"id": id_armazem, "descricao": "LUFT SOLUTIONS - AG2 - CAJAMAR - 16"}
    }

    def make_request(url, payload=None, data=None, content_type='application/json'):
        req_headers = headers.copy()
        req_headers['Content-Type'] = content_type
        response = session.post(url, data=orjson.dumps(payload) if payload else data, headers=req_headers)
        response.raise_for_status()
        return orjson.loads(response.content)

    login_response = make_request(f'{base_url}/SessionService/login', payload=login_data)
    headers['Authorization'] = f'Bearer {login_response["value"]["bearer"]}'

    df = pd.read_excel(excel_path)
    locais_lista = df[excel_coluna_local].dropna().astype(str).tolist()

    for local_code in locais_lista:
        payload = {
            "idArmazem": id_armazem,
            "config": {
                "@class": "SqlQueryResultSlickConfig",
                "sqlQueryLoadMode": "VALUES",
                "queryType": "ROWID",
                "showAll": False,
                "filterConfigs": [{"field": "IDLOCAL", "type": "string", "map": {"value": local_code}}],
                "orderBy": "ID DESC",
                "skip": 0,
                "take": 40
            }
        }
        response = make_request(f'{base_url}/ArmazemService/getLocaisArmazenagem', payload)
        dados = orjson.loads(response['value']['value'])
        result_data = dados.get('resultData', [])
        if not result_data:
            continue

        id_local = result_data[0]['ID']
        detalhes = make_request(
            f'{base_url}/LocalCRUD/findById',
            data=f"id={id_local}",
            content_type='application/x-www-form-urlencoded'
        )

        payload = {
            "entity": {
                "id": detalhes["id"],
                "ativo": local_ativo,
                "altura": str(detalhes["altura"]),
                "largura": str(detalhes["largura"]),
                "comprimento": str(detalhes["comprimento"]),
                "alturaManobra": str(detalhes["alturaManobra"]),
                "pesoMaximo": str(detalhes["pesoMaximo"]),
                "picking": detalhes.get("picking", False),
                "armazem": detalhes["armazem"],
                "local": detalhes["local"],
                "regiaoArmazenagem": detalhes["regiaoArmazenagem"],
                "tipo": detalhes.get("tipo", "PULMAO_PALETIZADO"),
                "buffer": detalhes.get("buffer", False),
                "localIntegracao": detalhes.get("localIntegracao", 0),
                "bloco": detalhes["bloco"],
                "rua": detalhes["rua"],
                "predio": detalhes["predio"],
                "andar": detalhes["andar"],
                "apartamento": detalhes["apartamento"],
                "estanteria": detalhes.get("estanteria", False),
                "origembloqueio": "NAO_BLOQUEADO",
                "bufferEsteira": detalhes.get("bufferEsteira", False),
                "setor": detalhes["setor"]
            },
            "id": None,
            "tela": "Cadastro de Local",
            "usuario": {"id": usuario_id, "nomeUsuario": "ANDERSON.SANTOS1"}
        }
        make_request(f'{base_url}/LocalCRUD/save', payload=payload)

if __name__ == "__main__":
    ativar_locais()