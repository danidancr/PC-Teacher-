# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# Tabela 1: Usuários
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(100), nullable=False)
    
    progresso_usuario = db.relationship('Progresso', backref='usuario', lazy=True)

# Tabela 2: Cursos
class Curso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    
    modulos = db.relationship('Modulo', backref='curso', lazy=True)

# Tabela 3: Módulos
class Modulo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    curso_id = db.Column(db.Integer, db.ForeignKey('curso.id'), nullable=False)
    titulo = db.Column(db.String(100), nullable=False)
    ordem = db.Column(db.Integer, nullable=False)
    
    aulas = db.relationship('Aula', backref='modulo', lazy=True)

# Tabela 4: Aulas/Conteúdo
class Aula(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    modulo_id = db.Column(db.Integer, db.ForeignKey('modulo.id'), nullable=False)
    titulo = db.Column(db.String(100), nullable=False)
    # Aqui, guardamos apenas o conteúdo central da aula (vídeo, texto, exercício)
    conteudo_html = db.Column(db.Text, nullable=False) 
    ordem = db.Column(db.Integer, nullable=False)
    sequencial = db.Column(db.Boolean, default=True) # Se for obrigatória para liberar a próxima

# Tabela 5: Progresso
class Progresso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    aula_id = db.Column(db.Integer, db.ForeignKey('aula.id'), nullable=False)
    concluido = db.Column(db.Boolean, default=False)
    data_conclusao = db.Column(db.DateTime, nullable=True)
    
    __table_args__ = (db.UniqueConstraint('usuario_id', 'aula_id', name='_user_aula_uc'),)
    
    aula = db.relationship('Aula', backref='progresso', lazy=True)