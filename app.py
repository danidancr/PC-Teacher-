# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash 
import os 
from sqlalchemy import select 
from functools import wraps

# =========================================================
# 1. CONFIGURAÇÃO GERAL
# =========================================================
app = Flask(__name__)

# Configurações de segurança e banco de dados
# Em produção, use uma variável de ambiente REAL e longa para SECRET_KEY
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'sua_chave_secreta_padrao_muito_longa') 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pcteacher.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False 
db = SQLAlchemy(app)

# =========================================================
# 2. MODELOS (Estrutura do Banco de Dados)
# =========================================================

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha_hash = db.Column(db.String(128), nullable=False)
    
    # NOVAS COLUNAS PARA O PERFIL (Implementadas para a rota /perfil)
    instituicao = db.Column(db.String(100), default='')
    telefone = db.Column(db.String(20), default='')
    cargo = db.Column(db.String(100), default='Professor(a)') 
    
    # Relação com Progresso
    progresso = db.relationship('Progresso', backref='usuario', lazy=True, uselist=False)

    def set_senha(self, senha):
        """Armazena a senha usando hashing seguro."""
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        """Verifica se a senha fornecida corresponde ao hash armazenado."""
        return check_password_hash(self.senha_hash, senha)
    
    def __repr__(self):
        return f'<Usuario {self.nome}>'

class Progresso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), unique=True, nullable=False)
    # Colunas de progresso
    decomposicao_concluido = db.Column(db.Boolean, default=False)
    abstracao_concluido = db.Column(db.Boolean, default=False)
    # Adicione mais campos de progresso aqui conforme os módulos
    
    def __repr__(self):
        return f'<Progresso Usuario: {self.usuario_id}>'

# =========================================================
# 3. HELPERS E DECORATORS
# =========================================================

def usuario_logado():
    """Retorna o objeto Usuario logado ou None."""
    if 'usuario_id' in session:
        # Usa db.session.get para buscar pelo ID de forma eficiente
        return db.session.get(Usuario, session['usuario_id'])
    return None

def requires_auth(func):
    """Decorator para verificar se o usuário está logado antes de acessar a rota."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not usuario_logado():
            flash('Você precisa estar logado para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    return wrapper

# =========================================================
# 4. ROTAS DE AUTENTICAÇÃO
# =========================================================

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    usuario = usuario_logado()
    if usuario:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        senha = request.form.get('senha')
        
        # 1. Verifica se o e-mail já existe
        email_exists = db.session.execute(
            select(Usuario).filter_by(email=email)
        ).scalar_one_or_none()
        
        if email_exists:
            flash('Este e-mail já está cadastrado. Tente fazer o login.', 'danger')
            return render_template('cadastro.html', nome_for_form=nome, email_for_form=email)

        # 2. Cria novo usuário, hash de senha e salva no DB
        try:
            novo_usuario = Usuario(nome=nome, email=email)
            novo_usuario.set_senha(senha)
            db.session.add(novo_usuario)
            db.session.flush() # Obtém o ID
            
            # 3. Cria um registro de progresso
            novo_progresso = Progresso(usuario_id=novo_usuario.id)
            db.session.add(novo_progresso)
            db.session.commit()

            flash('Cadastro realizado com sucesso! Faça login para começar.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro interno ao cadastrar: {str(e)}', 'danger')
            
    # Variável ajustada: user=usuario
    return render_template('cadastro.html', user=usuario)

@app.route('/login', methods=['GET', 'POST'])
def login():
    usuario = usuario_logado()
    if usuario:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        
        usuario = db.session.execute(
            select(Usuario).filter_by(email=email)
        ).scalar_one_or_none()

        if usuario and usuario.check_senha(senha):
            session['usuario_id'] = usuario.id
            flash(f'Bem-vindo(a), {usuario.nome}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('E-mail ou senha incorretos.', 'danger')
            return render_template('login.html', email_for_form=email)

    # Variável ajustada: user=usuario
    return render_template('login.html', user=usuario)

@app.route('/logout')
def logout():
    """Remove o ID da sessão e redireciona para a página inicial."""
    session.pop('usuario_id', None)
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('index'))

# =========================================================
# 5. ROTAS DE ÁREA RESTRITA E PERFIL (GET/POST)
# =========================================================

@app.route('/')
def index():
    usuario = usuario_logado()
    # Variável ajustada: user=usuario
    return render_template('index.html', user=usuario)

@app.route('/dashboard')
@requires_auth
def dashboard():
    usuario = usuario_logado()
    return render_template('dashboard.html', user=usuario)

@app.route('/perfil', methods=['GET', 'POST']) 
@requires_auth
def perfil():
    usuario = usuario_logado()
    
    if request.method == 'POST':
        # Pega os dados do formulário
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        institution = request.form.get('institution')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        tem_erro = False
        
        try:
            # 1. Atualiza dados básicos
            usuario.nome = name
            usuario.telefone = phone
            usuario.instituicao = institution
            
            # 2. Checa e atualiza E-mail
            if email != usuario.email:
                email_existente = db.session.execute(
                    select(Usuario).filter_by(email=email)
                ).scalar_one_or_none()
                
                if email_existente and email_existente.id != usuario.id:
                     flash("Este novo e-mail já está em uso por outro usuário.", 'danger')
                     tem_erro = True
                else:
                    usuario.email = email

            # 3. Processa a mudança de senha
            if new_password:
                if new_password != confirm_password:
                    flash("As novas senhas digitadas não coincidem.", 'danger')
                    tem_erro = True
                elif len(new_password) < 6:
                    flash("A nova senha deve ter no mínimo 6 caracteres.", 'danger')
                    tem_erro = True
                else:
                    usuario.set_senha(new_password)
                    flash("Senha atualizada com sucesso!", 'success')

            # 4. Commit no Banco de Dados
            if not tem_erro:
                db.session.commit()
                # Se não atualizou a senha, exibe sucesso nos dados
                if not new_password:
                    flash("Dados do perfil atualizados com sucesso!", 'success')
            else:
                db.session.rollback() # Desfaz alterações se houve erro de validação
                
        except Exception as e:
            db.session.rollback()
            flash(f"Ocorreu um erro inesperado ao salvar: {str(e)}", 'danger')
            
        # Variável ajustada: user=usuario
        return render_template('perfil.html', user=usuario)

    # Variável ajustada: user=usuario
    return render_template('perfil.html', user=usuario)

@app.route('/progresso')
@requires_auth
def progresso():
    usuario = usuario_logado()
    progresso = usuario.progresso
    return render_template('progresso.html', user=usuario, title="Meu Progresso", progresso=progresso)

@app.route('/certificado')
@requires_auth
def certificado():
    usuario = usuario_logado()
    # Variável ajustada: user=usuario
    return render_template('certificado.html', user=usuario, title="Certificado", content="Acesse e baixe seu certificado de conclusão aqui.")


# 7. ROTAS DE CONTEÚDO DE CURSO
@app.route('/infor-curso-decomposicao')
def infor_curso_decomposicao():
    usuario = usuario_logado()
    # Variável ajustada: user=usuario
    return render_template('infor-curso-decomposicao.html', user=usuario)

@app.route('/infor-curso-rec-padrao')
def infor_curso_rec_padrao():
    usuario = usuario_logado()
    # Variável ajustada: user=usuario
    return render_template('infor-curso-rec-padrao.html', user=usuario)

@app.route('/infor-curso-abstracao')
def infor_curso_abstracao():
    usuario = usuario_logado()
    # Variável ajustada: user=usuario
    return render_template('infor-curso-abstracao.html', user=usuario)

@app.route('/infor-curso-algoritmo')
def infor_curso_algoritmo():
    usuario = usuario_logado()
    # Variável ajustada: user=usuario
    return render_template('infor-curso-algoritmo.html', user=usuario)


# =========================================================
# 7. ROTAS DE CONTEÚDO DE CURSO (Protegidas por autenticação)
# =========================================================

# 6. ROTAS DE INFORMAÇÃO DOS MÓDULOS 
@app.route('/modulos')
@requires_auth
def modulos():
    usuario = usuario_logado()
    progresso = usuario.progresso
    # Variável ajustada: user=usuario
    return render_template('modulos.html', user=usuario, progresso=progresso)



# Rota para finalizar um módulo (chamada via formulário POST)
@app.route('/concluir-modulo/<string:modulo_nome>', methods=['POST'])
@requires_auth
def concluir_modulo(modulo_nome):
    usuario = usuario_logado()
    progresso = usuario.progresso
    
    # Mapeamento do nome da rota/identificador para o campo do DB
    modulo_map = {
        'introducao': 'introducao_concluido',
        'decomposicao': 'decomposicao_concluido',
        'rec_padrao': 'reconhecimento_padroes_concluido',
        'abstracao': 'abstracao_concluido',
        'algoritmo': 'algoritmo_concluido',
        'projeto_final': 'projeto_final_concluido',
    }
    
    db_field = modulo_map.get(modulo_nome)
    
    if db_field:
        try:
            # 1. Altera o status do campo no objeto progresso
            setattr(progresso, db_field, True)
            
            # 2. Salva a alteração no banco
            db.session.commit()
            
            # Formata o nome para a mensagem
            display_name = modulo_nome.replace("_", " ").title()
            flash(f'Módulo "{display_name}" concluído com sucesso! O próximo foi desbloqueado.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao concluir o módulo: {str(e)}', 'danger')
            
    else:
        flash('Módulo inválido.', 'danger')
        
    # Redireciona sempre para a lista de módulos
    return redirect(url_for('modulos'))

@app.route('/conteudo-introducao')
@requires_auth
def conteudo_introducao():
    usuario = usuario_logado()
    # Esta rota deve renderizar o conteúdo real do módulo.
    # No final do conteúdo, deve haver um formulário POST para '/concluir-modulo/introducao'
    return render_template('conteudo-introducao.html', user=usuario)

@app.route('/conteudo-decomposicao')
@requires_auth
def conteudo_decomposicao():
    usuario = usuario_logado()
    # Adicione aqui uma verificação de bloqueio se for estritamente necessário no backend
    if not usuario.progresso.introducao_concluido:
         flash('Você deve completar o módulo de Introdução primeiro.', 'warning')
         return redirect(url_for('modulos'))
    return render_template('conteudo-decomposicao.html', user=usuario)

@app.route('/conteudo-rec-padrao')
@requires_auth
def conteudo_rec_padrao():
    usuario = usuario_logado()
    if not usuario.progresso.decomposicao_concluido:
         flash('Você deve completar o módulo de Decomposição primeiro.', 'warning')
         return redirect(url_for('modulos'))
    return render_template('conteudo-rec-padrao.html', user=usuario)

@app.route('/conteudo-abstracao')
@requires_auth
def conteudo_abstracao():
    usuario = usuario_logado()
    if not usuario.progresso.reconhecimento_padroes_concluido:
         flash('Você deve completar o módulo de Reconhecimento de Padrões primeiro.', 'warning')
         return redirect(url_for('modulos'))
    return render_template('conteudo-abstracao.html', user=usuario)

@app.route('/conteudo-algoritmo')
@requires_auth
def conteudo_algoritmo():
    usuario = usuario_logado()
    if not usuario.progresso.abstracao_concluido:
         flash('Você deve completar o módulo de Abstração primeiro.', 'warning')
         return redirect(url_for('modulos'))
    return render_template('conteudo-algoritmo.html', user=usuario)

@app.route('/conteudo-projeto-final')
@requires_auth
def conteudo_projeto_final():
    usuario = usuario_logado()
    if not usuario.progresso.algoritmo_concluido:
         flash('Você deve completar o módulo de Algoritmos primeiro.', 'warning')
         return redirect(url_for('modulos'))
    return render_template('conteudo-projeto-final.html', user=usuario)



# =========================================================
# 8. EXECUÇÃO
# =========================================================

if __name__ == '__main__':
    # Se você ainda estiver tendo o erro "no such column", delete o arquivo 'pcteacher.db' antes de rodar!
    with app.app_context():
        db.create_all() 
        
    app.run(debug=True)
