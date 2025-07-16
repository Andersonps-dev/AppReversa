import requests
import orjson
import pandas as pd

class SiltWMSClient:
    def __init__(self):
        self.BASE_URL = 'http://200.143.168.151:8880/siltwms/webresources'
        self.session = requests.Session()
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-HTTP-Method-Override': 'POST'
        }
        
        self.ID_ARMAZEM = 7
        self.USUARIO_ID = 6501
        self.LOCAL_ATIVO = True
        self.EXCEL_PATH = r"C:\Users\jadson.sales\Downloads\itensinventario.xlsx"
        self.EXCEL_COLUNA_LOCAL = "Local"
        
        self.LOGIN_URL = f'{self.BASE_URL}/SessionService/login'
        self.LOCAL_SERVICE_URLS = {
            'get_locais': f'{self.BASE_URL}/ArmazemService/getLocaisArmazenagem',
            'get_detalhes': f'{self.BASE_URL}/LocalCRUD/findById',
            'save_local': f'{self.BASE_URL}/LocalCRUD/save'
        }
        
        self.INVENTARIO_SERVICE_URLS = {
            'get_inventarios': f'{self.BASE_URL}/InventarioService/getInventarios',
            'save_inventario': f'{self.BASE_URL}/InventarioCRUD/save',
            'add_depositantes': f'{self.BASE_URL}/InventarioService/addDepositantesInventario',
            'get_usuarios': f'{self.BASE_URL}/InventarioService/getUsuarios',
            'add_usuarios': f'{self.BASE_URL}/InventarioService/addUsuarios',
            'get_locais': f'{self.BASE_URL}/InventarioService/getLocais',
            'add_locais': f'{self.BASE_URL}/InventarioService/addLocais',
            'liberar_inventario': f'{self.BASE_URL}/InventarioService/liberarInventario'
        }
        
    def make_request(self, url, payload=None, data=None, content_type='application/json'):
        req_headers = self.headers.copy()
        req_headers['Content-Type'] = content_type
        
        try:
            if payload:
                response = self.session.post(url, data=orjson.dumps(payload), headers=req_headers)
            elif data:
                response = self.session.post(url, data=data, headers=req_headers)
            else:
                response = self.session.post(url, headers=req_headers)

            response.raise_for_status()
            
            if response.status_code == 204 or not response.content:
                return None
                
            return orjson.loads(response.content)
        except Exception as e:
            print(f"❌ Erro em {url}: {e}")
            return None
