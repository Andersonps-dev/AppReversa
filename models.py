from database import db

class Estoque(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Local = db.Column(db.String(255))
    Rua = db.Column(db.String(10))
    F_IDLOCAL = db.Column(db.String(255))
    Tipo_do_Local = db.Column(db.String(255))
    Estado = db.Column(db.String(255))
    Buffer = db.Column(db.Boolean)
    Local_Ativo = db.Column(db.Boolean)
    Setor = db.Column(db.String(255))
    Regiao = db.Column(db.String(255))
    Estoque = db.Column(db.Integer)
    Pendencia = db.Column(db.Integer)
    Adicionar = db.Column(db.Integer)
    Disponivel = db.Column(db.Integer)
    Barra = db.Column(db.String(255))
    Descricao_Reduzida = db.Column(db.String(255))
    idProduto = db.Column(db.String(255), nullable=True)
    Codigo_do_Produto = db.Column(db.String(255))
    Codigo_Produto_Depositante = db.Column(db.String(255))
    Produto = db.Column(db.String(255))
    Depositante = db.Column(db.String(255))
    Tipo = db.Column(db.String(255))
    H_IDARMAZEM = db.Column(db.String(255))
    H_IDDEPOSITANTE = db.Column(db.String(255))
    H_ORDEM = db.Column(db.String(255))
    H_RN = db.Column(db.String(255))
    data_atualizacao = db.Column(db.DateTime)

class BarraEndereco(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    barra = db.Column(db.String(255), nullable=False)
    rua = db.Column(db.String(255), nullable=False)
    endereco = db.Column(db.String(255), nullable=False)
    data_armazenamento = db.Column(db.DateTime, nullable=False)
    bloqueado = db.Column(db.Boolean, default=False, nullable=False)

# Novo modelo para registrar inventários realizados
class InventariosRealizados(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    barra = db.Column(db.String(255), nullable=False)
    rua = db.Column(db.String(255), nullable=False)
    endereco = db.Column(db.String(255), nullable=False)
    data_armazenamento = db.Column(db.DateTime, nullable=False)
    data_inventario = db.Column(db.DateTime, nullable=False)
    
class UserCredential(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user1 = db.Column(db.String(128))
    pass1 = db.Column(db.String(128))
    user2 = db.Column(db.String(128))
    pass2 = db.Column(db.String(128))
    
class Empresa(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_empresa = db.Column(db.String(255), nullable=False)
    nome_empresa = db.Column(db.String(255), nullable=False)

# Modelo de usuário para cadastro
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(128), nullable=False)
    sobrenome = db.Column(db.String(128), nullable=False)
    username = db.Column(db.String(128), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False)
    role = db.Column(db.String(32), nullable=False)

    empresa = db.relationship('Empresa', backref=db.backref('usuarios', lazy=True))