from flask import Flask, render_template, request, redirect, url_for, session, flash, get_flashed_messages
from werkzeug.security import generate_password_hash, check_password_hash
from database import db
from flask_migrate import Migrate
import os
from dotenv import load_dotenv
import logging
from sqlalchemy import func
from models import Estoque, BarraEndereco
from sqlalchemy import cast, Integer
from config import LINK_WMS, LOGINS_WMS, SENHAS_WMS, ID_TOKEN_WMS, TOKENS_SENHAS
from ApiWMS.extrair_dados_estoque import extrair_dados_estoques_wms
from datetime import datetime

app = Flask(__name__)

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
    return render_template('index.html', codigo_barra=None, sucesso=sucesso)

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
        .having(func.sum(Estoque.Estoque) < 50)
        .order_by(cast(Estoque.Rua, Integer).asc())
        .limit(1)
        .first()
    )

    if estoque:
        return render_template('index.html', rua=estoque.Rua, local=estoque.Local, codigo_barra=codigo_barra)
    else:
        return render_template('index.html', erro='Nenhuma rua com saldo disponível para esse código de barras.', codigo_barra=codigo_barra)
    
@app.route('/atualizar_estoque', methods=['GET'])
def atualizar_estoque():
    success = extrair_dados_estoques_wms(
        link_wms=LINK_WMS,
        user_wms=LOGINS_WMS[0],
        senha_wms=SENHAS_WMS[0],
        save_path=app.instance_path
    )
    
    os.remove(os.path.join(app.instance_path, "Estoque Local Por Produto.csv"))
    
    return redirect(url_for('index'))

@app.route('/salvar_endereco', methods=['POST'])
def salvar_endereco():
    codigo_barra = request.form.get('codigo_barra')
    rua = request.form.get('rua')
    endereco = request.form.get('endereco')
    if not (codigo_barra and rua and endereco):
        return render_template('index.html', erro='Preencha todos os campos.', codigo_barra=codigo_barra, rua=rua)

    try:
        novo = BarraEndereco(barra=codigo_barra, rua=rua, endereco=endereco, data_armazenamento=datetime.now())
        db.session.add(novo)
        db.session.commit()
        flash('Endereço salvo com sucesso!', 'success')
        return redirect(url_for('index'))
    except Exception as e:
        return render_template('index.html', erro=f'Erro ao salvar: {e}', codigo_barra=codigo_barra, rua=rua)

@app.route('/enderecos')
def enderecos():
    results = db.session.query(BarraEndereco.endereco, func.count(BarraEndereco.barra)).group_by(BarraEndereco.endereco).all()
    return render_template('enderecos.html', enderecos=results)

@app.route('/enderecos/<endereco>')
def detalhes_endereco(endereco):
    detalhes = BarraEndereco.query.filter_by(endereco=endereco).all()
    return render_template('detalhes_endereco.html', endereco=endereco, detalhes=detalhes)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)