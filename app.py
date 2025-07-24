from flask import Flask, render_template, request, redirect, url_for, flash, get_flashed_messages
from database import db
from flask_migrate import Migrate
import os
from dotenv import load_dotenv
import logging
from sqlalchemy import func
from models import Estoque, BarraEndereco, InventariosRealizados, UserCredential

from sqlalchemy import cast, Integer
from config import LINK_WMS, LOGINS_WMS, SENHAS_WMS, ID_TOKEN_WMS, TOKENS_SENHAS, QTDE_CABE_PICKING
from ApiWMS.extrair_dados_estoque import extrair_dados_estoques_wms
from ApiWMS.executar_inventario import InventoryExecutor
from datetime import datetime
import pytz

app = Flask(__name__)

load_dotenv()

# POSTGRES_USER = os.getenv('POSTGRES_USER')
# POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
# POSTGRES_DB = os.getenv('POSTGRES_DB')
# POSTGRES_HOST = os.getenv('POSTGRES_HOST')
# POSTGRES_PORT = os.getenv('POSTGRES_PORT')

# app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}'


app.config['SECRET_KEY'] = 'admin_anderson_luft'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/')
def index():
    sucesso = None
    msgs = get_flashed_messages(category_filter=['success'])
    if msgs:
        sucesso = msgs[0]
    data_atualizacao_estoque = db.session.query(func.max(Estoque.data_atualizacao)).scalar()
    return render_template('index.html', codigo_barra='', sucesso=sucesso, data_atualizacao_estoque=data_atualizacao_estoque)

@app.route('/consultar_rua', methods=['POST'])
def consultar_rua():
    codigo_barra = request.form.get('codigo_barra')
    
    if not codigo_barra:
        return render_template('index.html', erro='Código de barras não informado.', codigo_barra=None)

    estoque = (
        db.session.query(
            Estoque.Barra,
            Estoque.Local,
            Estoque.Rua,
            func.sum(Estoque.Estoque).label('total_estoque')
        )
        .filter(Estoque.Barra == codigo_barra)
        .group_by(Estoque.Barra, Estoque.Local, Estoque.Rua)
        .having(func.sum(Estoque.Estoque) < QTDE_CABE_PICKING)
        .order_by(cast(Estoque.Rua, Integer).asc())
        .limit(1)
        .first()
    )
    data_atualizacao_estoque = db.session.query(func.max(Estoque.data_atualizacao)).scalar()
    if estoque:
        return render_template('index.html', rua=estoque.Rua, local=estoque.Local, codigo_barra=codigo_barra, data_atualizacao_estoque=data_atualizacao_estoque)
    else:
        return render_template('index.html', erro='Sem Picking disponível.', codigo_barra=codigo_barra, data_atualizacao_estoque=data_atualizacao_estoque)
    
@app.route('/atualizar_estoque', methods=['GET'])
def atualizar_estoque():
    try:
        success = extrair_dados_estoques_wms(
            link_wms=LINK_WMS,
            user_wms=LOGINS_WMS[0],
            senha_wms=SENHAS_WMS[0],
            save_path=app.instance_path
        )
        if success:
            os.remove(os.path.join(app.instance_path, "Estoque Local Por Produto.csv"))
            flash('Estoque atualizado com sucesso!', 'success')
        else:
            flash('Falha ao atualizar estoque.', 'error')
    except Exception as e:
        logger.error(f"Erro ao atualizar estoque: {e}")
        flash(f'Erro ao atualizar estoque: {e}', 'error')
    return redirect(url_for('index'))

@app.route('/salvar_endereco', methods=['POST'])
def salvar_endereco():
    codigo_barra = request.form.get('codigo_barra')
    rua = request.form.get('rua')
    endereco = request.form.get('endereco')
    
    if not (codigo_barra and rua and endereco):
        flash('Preencha todos os campos.', 'error')
        return render_template('index.html', erro='Preencha todos os campos.', codigo_barra=codigo_barra, rua=rua)

    endereco_existente = BarraEndereco.query.filter_by(endereco=endereco).first()
    if endereco_existente and endereco_existente.bloqueado:
        flash('Endereço bloqueado.', 'error')
        return render_template('index.html', erro='Endereço bloqueado.', codigo_barra=codigo_barra, rua=rua)
    
    try:
        novo = BarraEndereco(barra=codigo_barra, rua=rua, endereco=endereco, data_armazenamento=datetime.now())
        db.session.add(novo)
        db.session.commit()
        flash('Endereço salvo com sucesso!', 'success')
        return redirect(url_for('index'))
    except Exception as e:
        flash(f'Erro ao salvar: {str(e)}', 'error')
        return render_template('index.html', erro=f'Erro ao salvar: {str(e)}', codigo_barra=codigo_barra, rua=rua)

@app.route('/enderecos')
def enderecos():
    results = db.session.query(BarraEndereco.endereco, func.count(BarraEndereco.barra)).group_by(BarraEndereco.endereco).all()
    data_atualizacao_estoque = db.session.query(func.max(Estoque.data_atualizacao)).scalar()
    return render_template('enderecos.html', enderecos=results, data_atualizacao_estoque=data_atualizacao_estoque)

@app.route('/enderecos/<endereco>', methods=['GET', 'POST'])
def detalhes_endereco(endereco):
    detalhes = db.session.query(
        BarraEndereco.barra,
        func.count(BarraEndereco.endereco).label('qtde'),
        BarraEndereco.rua,
        func.max(BarraEndereco.data_armazenamento).label('data_atualizado'),
        BarraEndereco.bloqueado  # Adicionar campo bloqueado
    ).filter_by(endereco=endereco).group_by(BarraEndereco.barra, BarraEndereco.rua, BarraEndereco.bloqueado).all()
    
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
        bloqueado = detalhe.bloqueado  # Assume que todos os registros do mesmo endereço têm o mesmo status de bloqueio

    if request.method == 'POST':
        if 'bloquear' in request.form:
            try:
                BarraEndereco.query.filter_by(endereco=endereco).update({'bloqueado': True})
                db.session.commit()
                flash('Endereço bloqueado com sucesso!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Erro ao bloquear endereço: {e}', 'error')
            return redirect(url_for('detalhes_endereco', endereco=endereco))
        
        if 'desbloquear' in request.form:
            try:
                BarraEndereco.query.filter_by(endereco=endereco).update({'bloqueado': False})
                db.session.commit()
                flash('Endereço desbloqueado com sucesso!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Erro ao desbloquear endereço: {e}', 'error')
            return redirect(url_for('detalhes_endereco', endereco=endereco))

        user1 = request.form.get('user1')
        pass1 = request.form.get('pass1')
        user2 = request.form.get('user2')
        pass2 = request.form.get('pass2')

        try:
            executor = InventoryExecutor(
                user1=user1,
                pass1=pass1,
                user2=user2,
                pass2=pass2,
                locais_banco=[endereco],
                items_by_location=itens,
            )
            executor.execute_inventory()
            executor.atualizar_critica()

            # Buscar todos os registros da BarraEndereco para o endereço
            registros = db.session.query(BarraEndereco).filter_by(endereco=endereco).all()
            for registro in registros:
                inventario = InventariosRealizados(
                    barra=registro.barra,
                    rua=registro.rua,
                    endereco=registro.endereco,
                    data_armazenamento=registro.data_armazenamento,
                    data_inventario=datetime.now()
                )
                db.session.add(inventario)
                db.session.delete(registro)
            db.session.commit()

            # Após executar o inventário, desbloquear o endereço
            BarraEndereco.query.filter_by(endereco=endereco).update({'bloqueado': False})
            db.session.commit()

            flash('Inventário executado com sucesso!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao executar inventário: {e}', 'error')
        return redirect(url_for('detalhes_endereco', endereco=endereco))
        
    cred = db.session.query(UserCredential).first()
    data_atualizacao_estoque = db.session.query(func.max(Estoque.data_atualizacao)).scalar()
    return render_template('detalhes_endereco.html', endereco=endereco, detalhes=detalhes, cred=cred, 
                         data_atualizacao_estoque=data_atualizacao_estoque, bloqueado=bloqueado)

@app.route('/enderecos/<endereco>/excluir', methods=['POST'])
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
def credenciais():
    cred = UserCredential.query.first()
    if not cred:
        cred = UserCredential(user1='', pass1='', user2='', pass2='')
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
    data_atualizacao_estoque = db.session.query(func.max(Estoque.data_atualizacao)).scalar()
    return render_template('credenciais.html', cred=cred, data_atualizacao_estoque=data_atualizacao_estoque)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # app.run(host='0.0.0.0', port=5000, debug=False)
    app.run(debug=True)