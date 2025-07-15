from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from database import db
from flask_migrate import Migrate
import requests
import json
import os
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime
from functools import wraps
import logging
from sqlalchemy import func
from models import Estoque
from config import LINK_WMS, LOGINS_WMS, SENHAS_WMS, ID_TOKEN_WMS, TOKENS_SENHAS

# Configuração do Flask
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
    estoques = Estoque.query.all()
    return render_template('index.html', estoques=estoques)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)