import requests
import pandas as pd
from urllib.parse import urljoin
import time
import re
from bs4 import BeautifulSoup   


BASE_URL = 'http://200.143.168.151:8880/mwms/'
LOGIN_WMS = 'amanda.reis'
SENHA_WMS = 'luft@Solutions2025'
BASE_PATH = r"C:\Users\anderson.santos\Downloads\inventario teste sistema.xlsx"

def criar_escopo_inventario():
    df = pd.read_excel(BASE_PATH)
    df['Local'] = df['Local'].str.upper()
    itens = df[['Codigo', 'qtde', 'Local']].to_dict('records')
    if not itens:
        raise Exception("Não foi possível ler os itens da planilha")

    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': urljoin(BASE_URL, '/'),
        'Origin': BASE_URL,
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    # Login
    login_url = urljoin(BASE_URL, 'servlet/LoginServlet')
    login_data = {'op': '1', 'nomeusuario': LOGIN_WMS, 'senha': SENHA_WMS}
    login_response = session.post(login_url, data=login_data, headers=headers, allow_redirects=False)
    if login_response.status_code != 302:
        raise Exception(f"Login falhou com status {login_response.status_code}")

    # Selecionar armazém
    armazem_url = urljoin(BASE_URL, 'servlet/ArmazemServlet')
    armazem_data = {'armazem': '7.0,LUFT SOLUTIONS - AG2 - CAJAMAR - 16,S'}
    session.post(armazem_url, data=armazem_data, headers=headers)

    # Inicializar inventário
    inventario_url = urljoin(BASE_URL, 'servlet/InventarioServlet')
    response = session.get(inventario_url + '?op=1', headers=headers)
    
    # soup = BeautifulSoup(response.text, 'html.parser')
    # select = soup.find('select', {'id': 'inventario'})

    # if select:
    #     options = select.find_all('option')
    #     for option in options:
    #         option_text = option.text.strip()
    #         match = re.match(r'(\d+)', option_text)
    #         if match:
    #             numero_inventario = match.group(1)
    #             print(f"{option_text}")
    #         else:
    #             print(f"Número não encontrado na opção: {option_text}")
    # else:
    #     print("Elemento <select id='inventario'> não encontrado.")
        
    session.post(inventario_url, data={'op': '1', 'inventario': '0'}, headers=headers)

    # Agrupar itens por local
    itens_por_local = {}
    for item in itens:
        local = str(item['Local']).strip()
        if local not in itens_por_local:
            itens_por_local[local] = []
        itens_por_local[local].append(item)

    # Processar inventário por local
    for local, itens_local in itens_por_local.items():
        response_op3 = session.post(inventario_url, data={'op': '2', 'local': local}, headers=headers)
        if response_op3.status_code != 200:
            continue

        time.sleep(0.5)

        # Processar itens do local
        for item in itens_local:
            codigo = str(item['Codigo']).strip()
            qtde = str(item['qtde']).strip()
            if not codigo or not qtde:
                continue

            payload_op4 = {'op': '3', 'finalizar': 'N', 'qtde': qtde, 'barra': codigo, 'tipo': '1'}
            session.post(inventario_url, data=payload_op4, headers=headers)
            time.sleep(0.5)

        # Finalizar local
        payload_op5 = {'op': '3', 'finalizar': 'S', 'qtde': '0', 'barra': '', 'tipo': '1'}
        session.post(inventario_url, data=payload_op5, headers=headers)
        time.sleep(0.5)

if __name__ == "__main__":
    criar_escopo_inventario()