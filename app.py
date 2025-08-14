from flask import Flask, render_template, request, redirect, url_for, flash, get_flashed_messages, g, session
from werkzeug.security import generate_password_hash, check_password_hash
from database import db
from flask_migrate import Migrate
import os
from dotenv import load_dotenv
import logging
from sqlalchemy import func
from models import Estoque, BarraEndereco, InventariosRealizados, UserCredential, Empresa, Usuario, RuasSelecionadas, Permissao
from sqlalchemy import cast, Integer
from config import LINK_WMS, QTDE_CABE_PICKING
from ApiWMS.extrair_dados_estoque import extrair_dados_estoques_wms
from ApiWMS.executar_inventario import InventoryExecutor
from datetime import datetime
import pytz
from functools import wraps
import secrets, string

app = Flask(__name__)

load_dotenv()

POSTGRES_USER = os.getenv('POSTGRES_USER')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
POSTGRES_DB = os.getenv('POSTGRES_DB')
POSTGRES_HOST = os.getenv('POSTGRES_HOST')
POSTGRES_PORT = os.getenv('POSTGRES_PORT')

app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}'

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        rota = request.path
        # Normalizar rotas dinâmicas para checagem de permissão
        rota_normalizada = rota
        if rota.startswith('/enderecos/'):
            partes = rota.split('/')
            if len(partes) == 3:
                rota_normalizada = '/enderecos/<endereco>'
            elif len(partes) == 4 and partes[-1] == 'excluir':
                rota_normalizada = '/enderecos/<endereco>/excluir'
            elif len(partes) == 4 and partes[-1] == 'excluir_item':
                rota_normalizada = '/enderecos/<endereco>/excluir_item'
        # Permitir acesso livre ao login e logout
        if rota in ['/login', '/logout']:
            return f(*args, **kwargs)
        if not session.get('usuario_id'):
            flash('Faça login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        usuario = Usuario.query.get(session['usuario_id'])
        if usuario and usuario.role == 'master':
            return f(*args, **kwargs)
        perm = Permissao.query.filter_by(cargo=usuario.role, rota=rota_normalizada).first()
        if not perm or not perm.pode_acessar:
            return render_template('acesso_negado.html'), 403
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def inject_data_atualizacao_estoque():
    empresa_id = session.get('empresa_id')
    empresa = Empresa.query.filter_by(id=empresa_id).first() if empresa_id else None
    if empresa:
        g.data_atualizacao_estoque = db.session.query(func.max(Estoque.data_atualizacao)).filter(Estoque.H_IDDEPOSITANTE == empresa.id_empresa).scalar()
    else:
        g.data_atualizacao_estoque = None
    
@app.context_processor
def inject_usuario_empresa():
    usuario_nome = session.get('usuario_nome')
    usuario_username = session.get('usuario_username')
    empresa_id = session.get('empresa_id')
    empresa_nome = None
    if empresa_id:
        empresa = Empresa.query.filter_by(id=empresa_id).first()
        if empresa:
            empresa_nome = empresa.nome_empresa
    # Adiciona classes para uso nos templates
    from models import Usuario, Permissao
    return dict(
        usuario_nome=usuario_nome,
        usuario_username=usuario_username,
        empresa_nome=empresa_nome,
        Usuario=Usuario,
        Permissao=Permissao
    )
@app.route('/login', methods=['GET', 'POST'])
def login():
    empresas = Empresa.query.all()
    erro = None
    if request.method == 'POST':
        username = request.form.get('usuario')
        password = request.form.get('senha')
        empresa_id = request.form.get('empresa')

        usuario = Usuario.query.filter_by(username=username, empresa_id=empresa_id).first()
        if usuario and check_password_hash(usuario.password, password):
            session['usuario_id'] = usuario.id
            session['usuario_nome'] = usuario.nome
            session['usuario_username'] = usuario.username
            session['usuario_role'] = usuario.role
            session['empresa_id'] = usuario.empresa_id
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('index'))
        else:
            erro = 'Usuário, senha ou empresa inválidos.'
    return render_template('login.html', empresas=empresas, erro=erro)

@app.route('/permissoes', methods=['GET', 'POST'])
@login_required
def permissoes():
    cargos = [r[0] for r in db.session.query(Usuario.role).distinct().all()]
    if 'master' not in cargos:
        cargos.append('master')
    cargo_selecionado = request.form.get('cargo') or request.args.get('cargo')
    grupos_rotas = [
        ("Página Inicial", [('/', 'Início')]),
        ("Endereços", [
            ('/enderecos', 'Listar'),
            ('/enderecos/<endereco>', 'Detalhes'),
            ('/enderecos/<endereco>/excluir', 'Excluir'),
            ('/enderecos/<endereco>/excluir_item', 'Excluir Item'),
            ('/salvar_endereco', 'Salvar'),
            ('/consultar_rua', 'Consultar Rua'),
        ]),
        ("Estoque", [
            ('/atualizar_estoque', 'Atualizar'),
            ('/salvar_ruas_selecionadas', 'Salvar Ruas Selecionadas'),
        ]),
        ("Usuários e Empresas", [
            ('/cadastro_usuario', 'Usuários - Cadastro/Listagem'),
            ('/empresa_cadastro', 'Empresas - Cadastro/Listagem'),
        ]),
        ("Credenciais", [
            ('/credenciais', 'Credenciais'),
        ]),
        ("Permissões", [
            ('/permissoes', 'Permissões'),
        ]),
    ]
    permissoes_grupo = []
    if cargo_selecionado:
        # Atualiza permissões se o botão de salvar foi pressionado (POST e não é master e tem o botão)
        if request.method == 'POST' and cargo_selecionado != 'master' and (
            request.form.get('action') == 'salvar_permissoes' or 'Salvar Permissões' in request.form.values()):
            for grupo, rotas in grupos_rotas:
                for rota, _ in rotas:
                    checkbox_name = f'acesso_{rota}'
                    checked = request.form.get(checkbox_name) == '1'
                    perm = Permissao.query.filter_by(cargo=cargo_selecionado, rota=rota).first()
                    if perm:
                        perm.pode_acessar = checked
                    else:
                        perm = Permissao(cargo=cargo_selecionado, rota=rota, pode_acessar=checked)
                        db.session.add(perm)
            db.session.commit()
            flash('Permissões atualizadas!', 'success')
        # Carrega permissões atuais do banco, mostrando todas as rotas agrupadas
        for grupo, rotas in grupos_rotas:
            permissoes = []
            for rota, label in rotas:
                perm = Permissao.query.filter_by(cargo=cargo_selecionado, rota=rota).first()
                permissoes.append((rota, label, perm.pode_acessar if perm else False))
            permissoes_grupo.append((grupo, permissoes))
    return render_template('permissoes.html', cargos=cargos, cargo_selecionado=cargo_selecionado, permissoes_grupo=permissoes_grupo)

@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash('Você foi desconectado.')
    return redirect(url_for('login'))

@app.route('/cadastro_usuario', methods=['GET', 'POST'])
@login_required
def cadastro_usuario():
    empresas = Empresa.query.all()
    alphabet = string.ascii_letters + string.digits + string.punctuation
    filtro = request.args.get('filtro', '')
    usuarios_query = Usuario.query
    if filtro:
        usuarios_query = usuarios_query.filter((Usuario.nome.ilike(f'%{filtro}%')) | (Usuario.sobrenome.ilike(f'%{filtro}%')) | (Usuario.username.ilike(f'%{filtro}%')))
    usuarios = usuarios_query.order_by(Usuario.nome.asc()).all()

    if request.method == 'POST':
        if 'editar_id' in request.form:
            usuario = Usuario.query.get(request.form['editar_id'])
            if usuario.username == 'master':
                flash('Não é permitido editar o usuário master.', 'danger')
                return redirect(url_for('cadastro_usuario'))
            usuario.nome = request.form['editar_nome']
            usuario.sobrenome = request.form['editar_sobrenome']
            usuario.role = request.form['editar_role']
            if request.form.get('editar_password'):
                usuario.password = generate_password_hash(request.form['editar_password'])
            usuario.empresa_id = request.form['editar_empresa']
            db.session.commit()
            flash('Usuário editado com sucesso!', 'success')
            return redirect(url_for('cadastro_usuario'))
        elif 'inativar_id' in request.form:
            usuario = Usuario.query.get(request.form['inativar_id'])
            if usuario.username == 'master':
                flash('Não é permitido desativar o usuário master.', 'danger')
                return redirect(url_for('cadastro_usuario'))
            usuario.ativo = False
            db.session.commit()
            flash('Usuário inativado!', 'success')
            return redirect(url_for('cadastro_usuario'))
        elif 'ativar_id' in request.form:
            usuario = Usuario.query.get(request.form['ativar_id'])
            if usuario.username == 'master':
                flash('Não é permitido ativar o usuário master.', 'danger')
                return redirect(url_for('cadastro_usuario'))
            usuario.ativo = True
            db.session.commit()
            flash('Usuário ativado!', 'success')
            return redirect(url_for('cadastro_usuario'))
        elif 'excluir_id' in request.form:
            usuario = Usuario.query.get(request.form['excluir_id'])
            if usuario.username == 'master':
                flash('Não é permitido excluir o usuário master.', 'danger')
                return redirect(url_for('cadastro_usuario'))
            db.session.delete(usuario)
            db.session.commit()
            flash('Usuário excluído!', 'success')
            return redirect(url_for('cadastro_usuario'))
        elif 'resetar_id' in request.form:
            usuario = Usuario.query.get(request.form['resetar_id'])
            if usuario.username == 'master':
                flash('Não é permitido resetar a senha do usuário master.', 'danger')
                return redirect(url_for('cadastro_usuario'))
            nova_senha = ''.join(secrets.choice(alphabet) for _ in range(12))
            usuario.password = generate_password_hash(nova_senha)
            db.session.commit()
            flash(f'Senha resetada! Nova senha: {nova_senha}', 'success')
            return redirect(url_for('cadastro_usuario'))
        else:
            # Cadastro novo usuário
            nome = request.form['nome'].strip()
            sobrenome = request.form['sobrenome'].strip()
            empresa_id = request.form['empresa']
            role = request.form['role']
            password = request.form['password']
            username = f"{nome.split()[0].lower()}.{sobrenome.split()[0].lower()}"
            if Usuario.query.filter_by(username=username).first():
                flash(f'Usuário já existe: {username}', 'danger')
                return redirect(url_for('cadastro_usuario'))
            usuario = Usuario(
                nome=nome,
                sobrenome=sobrenome,
                username=username,
                password=generate_password_hash(password),
                empresa_id=empresa_id,
                role=role
            )
            db.session.add(usuario)
            db.session.commit()
            flash('Usuário cadastrado com sucesso!', 'success')
            return redirect(url_for('cadastro_usuario'))
    senha_sugerida = ''.join(secrets.choice(alphabet) for _ in range(12))
    return render_template('cadastro_usuario.html', empresas=empresas, senha_sugerida=senha_sugerida, usuarios=usuarios, filtro=filtro)

@app.route('/empresa_cadastro', methods=['GET', 'POST'])
@login_required
def cadastro_empresa():
    filtro = request.args.get('filtro', '')
    empresas_query = Empresa.query
    if filtro:
        empresas_query = empresas_query.filter((Empresa.nome_empresa.ilike(f'%{filtro}%')) | (Empresa.id_empresa.ilike(f'%{filtro}%')))
    empresas = empresas_query.order_by(Empresa.nome_empresa.asc()).all()
    if request.method == 'POST':
        if 'editar_id' in request.form:
            empresa = Empresa.query.get(request.form['editar_id'])
            empresa.nome_empresa = request.form['editar_nome_empresa']
            empresa.id_empresa = request.form['editar_id_empresa']
            db.session.commit()
            flash('Empresa editada com sucesso!', 'success')
            return redirect(url_for('cadastro_empresa'))
        elif 'excluir_id' in request.form:
            empresa = Empresa.query.get(request.form['excluir_id'])
            db.session.delete(empresa)
            db.session.commit()
            flash('Empresa excluída!', 'success')
            return redirect(url_for('cadastro_empresa'))
        else:
            nome_empresa = request.form['nome_empresa']
            id_empresa = request.form['id_empresa']
            if not nome_empresa or not id_empresa:
                flash('Preencha todos os campos.', 'error')
                return redirect(url_for('cadastro_empresa'))
            empresa = Empresa(nome_empresa=nome_empresa, id_empresa=id_empresa)
            db.session.add(empresa)
            db.session.commit()
            flash('Empresa cadastrada com sucesso!', 'success')
            return redirect(url_for('cadastro_empresa'))
    return render_template('empresa_cadastro.html', empresas=empresas, filtro=filtro)

@app.route('/')
@login_required
def index():
    sucesso = None
    msgs = get_flashed_messages(category_filter=['success'])
    if msgs:
        sucesso = msgs[0]
    return render_template('index.html', codigo_barra='', sucesso=sucesso)

@app.route('/consultar_rua', methods=['POST'])
@login_required
def consultar_rua():
    codigo_barra = request.form.get('codigo_barra')
    empresa_db_id = session.get('empresa_id')
    empresa_obj = Empresa.query.filter_by(id=empresa_db_id).first() if empresa_db_id else None
    id_empresa_str = empresa_obj.id_empresa if empresa_obj else None

    if not codigo_barra:
        return render_template('index.html', erro='Código de barras não informado.', codigo_barra=None)

    # Buscar ruas selecionadas da empresa logada
    ruas_selecionadas = db.session.query(RuasSelecionadas.rua).filter_by(empresa_id=empresa_db_id).all()
    ruas_selecionadas = [r[0] for r in ruas_selecionadas]

    query = db.session.query(
        Estoque.Barra,
        Estoque.Local,
        Estoque.Rua,
        func.sum(Estoque.Estoque).label('total_estoque')
    ).filter(
        Estoque.Barra == codigo_barra,
        Estoque.H_IDDEPOSITANTE == id_empresa_str
    )
    if ruas_selecionadas:
        query = query.filter(Estoque.Rua.in_(ruas_selecionadas))
    query = query.group_by(Estoque.Barra, Estoque.Local, Estoque.Rua)
    query = query.having(func.sum(Estoque.Estoque) < QTDE_CABE_PICKING)
    query = query.order_by(cast(Estoque.Rua, Integer).asc())
    query = query.limit(1)
    estoque = query.first()

    if estoque:
        return render_template('index.html', rua=estoque.Rua, local=estoque.Local, codigo_barra=codigo_barra)
    else:
        return render_template('index.html', erro='Sem Picking disponível.', codigo_barra=codigo_barra)

@app.route('/atualizar_estoque', methods=['GET', 'POST'])
@login_required
def atualizar_estoque():
    cred = UserCredential.query.first()
    user = Usuario.query.filter_by(id=session.get('usuario_id')).first()
    if request.method == 'POST':
        try:
            success = extrair_dados_estoques_wms(
                link_wms=LINK_WMS,
                user_wms=cred.user1,
                senha_wms=cred.pass1,
                id_depositante=user.empresa.id_empresa
            )
            if success:
                flash('Estoque atualizado com sucesso!', 'success')
            else:
                flash('Falha ao atualizar estoque.', 'error')
        except Exception as e:
            logger.error(f"Erro ao atualizar estoque: {e}")
            flash(f'Erro ao atualizar estoque: {e}', 'error')
    # Buscar ruas distintas do estoque da empresa logada
    empresa_id = session.get('empresa_id')
    empresa_obj = Empresa.query.filter_by(id=empresa_id).first() if empresa_id else None
    id_empresa_str = empresa_obj.id_empresa if empresa_obj else None
    ruas = db.session.query(Estoque.Rua).filter(Estoque.H_IDDEPOSITANTE == id_empresa_str).distinct().all()
    ruas = [r[0] for r in ruas if r[0]]

    ruas_selecionadas = db.session.query(RuasSelecionadas.rua).filter_by(empresa_id=empresa_id).all()
    ruas_selecionadas = [r[0] for r in ruas_selecionadas]
    return render_template('atualizar_estoque.html', ruas=ruas, ruas_selecionadas=ruas_selecionadas)

@app.route('/salvar_ruas_selecionadas', methods=['POST'])
@login_required
def salvar_ruas_selecionadas():
    empresa_id = session.get('empresa_id')
    ruas_selecionadas = request.form.getlist('ruas')
    db.session.query(RuasSelecionadas).filter_by(empresa_id=empresa_id).delete()
    db.session.commit()
    for rua in ruas_selecionadas:
        nova_rua = RuasSelecionadas(rua=rua, empresa_id=empresa_id, data_selecao=datetime.now())
        db.session.add(nova_rua)
    db.session.commit()
    flash('Ruas selecionadas salvas com sucesso!', 'success')
    return redirect(url_for('atualizar_estoque'))

@app.route('/salvar_endereco', methods=['POST'])
@login_required
def salvar_endereco():
    codigo_barra = request.form.get('codigo_barra')
    rua = request.form.get('rua')
    endereco = request.form.get('endereco')
    empresa_id = session.get('empresa_id')
    if not (codigo_barra and rua and endereco):
        flash('Preencha todos os campos.', 'error')
        return render_template('index.html', erro='Preencha todos os campos.', codigo_barra=codigo_barra, rua=rua)

    endereco_existente = BarraEndereco.query.filter_by(endereco=endereco, id_empresa=empresa_id).first()
    if endereco_existente and endereco_existente.bloqueado:
        flash('Endereço bloqueado.', 'error')
        return render_template('index.html', erro='Endereço bloqueado.', codigo_barra=codigo_barra, rua=rua)

    try:
        novo = BarraEndereco(barra=codigo_barra, rua=rua, endereco=endereco, data_armazenamento=datetime.now(), id_empresa=empresa_id)
        db.session.add(novo)
        db.session.commit()
        flash('Endereço salvo com sucesso!', 'success')
        return redirect(url_for('index'))
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao salvar: {str(e)}', 'error')
        return render_template('index.html', erro=f'Erro ao salvar: {str(e)}', codigo_barra=codigo_barra, rua=rua)

@app.route('/enderecos')
@login_required
def enderecos():
    empresa_id = session.get('empresa_id')
    results = (
        db.session.query(BarraEndereco.endereco, func.count(BarraEndereco.barra))
        .filter(BarraEndereco.id_empresa == empresa_id)
        .group_by(BarraEndereco.endereco)
        .order_by(BarraEndereco.endereco)
        .all()
    )
    return render_template('enderecos.html', enderecos=results)

@app.route('/enderecos/<endereco>', methods=['GET', 'POST'])
@login_required
def detalhes_endereco(endereco):
    detalhes = db.session.query(
        BarraEndereco.barra,
        func.count(BarraEndereco.endereco).label('qtde'),
        BarraEndereco.rua,
        func.max(BarraEndereco.data_armazenamento).label('data_atualizado'),
        BarraEndereco.bloqueado
    ).filter(BarraEndereco.endereco == endereco).group_by(BarraEndereco.barra, BarraEndereco.rua, BarraEndereco.bloqueado).all()
    
    itens = []
    bloqueado = False
    for detalhe in detalhes:
        itens.append({
            'Codigo': detalhe.barra,
            'qtde': detalhe.qtde,
            'Local': endereco,
            'Rua': detalhe.rua,
            'DataAtualizado': detalhe.data_atualizado,
            'Bloqueado': detalhe.bloqueado
        })
        bloqueado = detalhe.bloqueado

    if request.method == 'POST':
        if 'bloquear' in request.form:
            try:
                BarraEndereco.query.filter_by(endereco=endereco).update({'bloqueado': True})
                db.session.commit()
                flash('Endereço bloqueado com sucesso!', 'success')
            except Exception as e:
                db.session.rollback()
                logger.error(f'Erro ao bloquear endereço: {e}', exc_info=True)
                flash(f'Erro ao bloquear endereço: {e}', 'error')
            return redirect(url_for('detalhes_endereco', endereco=endereco))
        
        if 'desbloquear' in request.form:
            try:
                BarraEndereco.query.filter_by(endereco=endereco).update({'bloqueado': False})
                db.session.commit()
                flash('Endereço desbloqueado com sucesso!', 'success')
            except Exception as e:
                db.session.rollback()
                logger.error(f'Erro ao desbloquear endereço: {e}', exc_info=True)
                flash(f'Erro ao desbloquear endereço: {e}', 'error')
            return redirect(url_for('detalhes_endereco', endereco=endereco))

        user1 = request.form.get('user1')
        pass1 = request.form.get('pass1')
        user2 = request.form.get('user2')
        pass2 = request.form.get('pass2')

        if not all([user1, pass1, user2, pass2]):
            flash('Todos os campos de autenticação são obrigatórios.', 'error')
            return redirect(url_for('detalhes_endereco', endereco=endereco))

        try:
            db.session.commit()

            executor = InventoryExecutor(
                user1=user1,
                pass1=pass1,
                user2=user2,
                pass2=pass2,
                locais_banco=[endereco],
                items_by_location=itens,
            )
            logger.info(f"Executing inventory for endereco: {endereco}")
            executor.execute_inventory()
            logger.info(f"Updating critica for endereco: {endereco}")
            executor.atualizar_critica()

            db.session.commit()

            with db.session.begin():
                registros = db.session.query(BarraEndereco).filter_by(endereco=endereco).all()
                if not registros:
                    logger.warning(f"No records found for endereco: {endereco}")
                    flash('Nenhum registro encontrado para o endereço.', 'warning')
                    return redirect(url_for('detalhes_endereco', endereco=endereco))

                for registro in registros:
                    inventario = InventariosRealizados(
                        barra=registro.barra,
                        rua=registro.rua,
                        endereco=registro.endereco,
                        data_armazenamento=registro.data_armazenamento,
                        data_inventario=datetime.now(pytz.UTC)
                    )
                    db.session.delete(registro)
                    logger.debug(f"Transferred and deleted record: barra={registro.barra}, endereco={endereco}")

                deleted_count = db.session.query(BarraEndereco).filter_by(endereco=endereco).delete()
                logger.debug(f"Deleted {deleted_count} remaining records for endereco: {endereco}")

            flash('Inventário executado com sucesso e todos os registros foram excluídos!', 'success')
        except Exception as e:
            db.session.rollback()
            logger.error(f'Erro ao executar inventário: {e}', exc_info=True)
            flash(f'Erro ao executar inventário: {str(e)}', 'error')
        return redirect(url_for('detalhes_endereco', endereco=endereco))
    
    cred = db.session.query(UserCredential).first()
    return render_template('detalhes_endereco.html', endereco=endereco, detalhes=detalhes, cred=cred, bloqueado=bloqueado)

@app.route('/enderecos/<endereco>/excluir', methods=['POST'])
@login_required
def excluir_endereco(endereco):
    try:
        db.session.query(BarraEndereco).filter_by(endereco=endereco).delete()
        db.session.commit()
        flash('Endereço excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir endereço: {e}', 'error')
    return redirect(url_for('enderecos'))

@app.route('/enderecos/<endereco>/excluir_item', methods=['POST'])
@login_required
def excluir_item(endereco):
    barra = request.form.get('barra')
    rua = request.form.get('rua')
    try:
        registro = db.session.query(BarraEndereco).filter_by(endereco=endereco, barra=barra, rua=rua).first()
        if registro:
            db.session.delete(registro)
            db.session.commit()
            flash('Item excluído com sucesso!', 'success')
        else:
            flash('Item não encontrado.', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir item: {e}', 'error')
    return redirect(url_for('detalhes_endereco', endereco=endereco))

@app.route('/credenciais', methods=['GET', 'POST'])
@login_required
def credenciais():
    empresa_id = session.get('empresa_id')
    cred = UserCredential.query.filter_by(id_empresa=empresa_id).first()
    if not cred:
        cred = UserCredential(user1='', pass1='', user2='', pass2='', id_empresa=empresa_id)
        db.session.add(cred)
        db.session.commit()
    if request.method == 'POST':
        cred.user1 = request.form.get('user1', '')
        cred.pass1 = request.form.get('pass1', '')
        cred.user2 = request.form.get('user2', '')
        cred.pass2 = request.form.get('pass2', '')
        db.session.commit()
        flash('Credenciais atualizadas com sucesso!', 'success')
        return redirect(url_for('credenciais'))
    return render_template('credenciais.html', cred=cred)

def criar_usuario_master():
    senha_master = os.getenv('SENHA_MASTER')
    if not senha_master:
        logger.error('SENHA_MASTER não definida no .env')
        return
    usuario_master = Usuario.query.filter_by(username='master').first()
    if not usuario_master:
        empresa = Empresa.query.first()
        if not empresa:
            empresa = Empresa(nome_empresa='MasterCorp', id_empresa='000')
            db.session.add(empresa)
            db.session.commit()
        master = Usuario(
            nome='Master',
            sobrenome='User',
            username='master',
            password=generate_password_hash(senha_master),
            empresa_id=empresa.id,
            role='master',
            ativo=True
        )
        db.session.add(master)
        db.session.commit()
        logger.info('Usuário master criado.')
    else:
        logger.info('Usuário master já existe.')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        criar_usuario_master()
    # app.run(host='0.0.0.0', port=5000, debug=False)
    app.run(debug=True) 