from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from sqlalchemy import select
from functools import wraps
from datetime import datetime

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
    
    # Relação com Progresso (uselist=False significa 1:1)
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
    
    # Colunas de progresso COMPLETADAS:
    introducao_concluido = db.Column(db.Boolean, default=False)
    decomposicao_concluido = db.Column(db.Boolean, default=False)
    reconhecimento_padroes_concluido = db.Column(db.Boolean, default=False)
    abstracao_concluido = db.Column(db.Boolean, default=False)
    algoritmo_concluido = db.Column(db.Boolean, default=False)
    projeto_final_concluido = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f'<Progresso Usuario: {self.usuario_id}>'

# =========================================================
# 3. HELPERS E DECORATORS
# =========================================================

# --- CONFIGURAÇÃO ESTÁTICA DOS MÓDULOS ---
# Usamos esta lista para gerar os dados dinâmicos
MODULO_CONFIG = [
    {
        'title': '1. Introdução ao Pensamento Computacional',
        'field': 'introducao_concluido',
        'slug': 'introducao',
        'template': 'conteudo-introducao.html', # NOVO CAMPO: nome do template
        'order': 1,
        'description': 'Entenda o que é o Pensamento Computacional, seus pilares e por que ele é crucial para o futuro.',
        'lessons': 2, 'exercises': 1, 'dependency_field': None
    },
    {
        'title': '2. Decomposição',
        'field': 'decomposicao_concluido',
        'slug': 'decomposicao',
        'template': 'conteudo-decomposicao.html', # NOVO CAMPO
        'order': 2,
        'description': 'Aprenda a quebrar problemas complexos em partes menores e gerenciáveis.',
        'lessons': 2, 'exercises': 1, 'dependency_field': 'introducao_concluido'
    },
    {
        'title': '3. Reconhecimento de Padrões',
        'field': 'reconhecimento_padroes_concluido',
        'slug': 'rec-padrao',
        'template': 'conteudo-rec-padrao.html', # NOVO CAMPO
        'order': 3,
        'description': 'Identifique similaridades e tendências para simplificar a resolução de problemas.',
        'lessons': 2, 'exercises': 1, 'dependency_field': 'decomposicao_concluido'
    },
    {
        'title': '4. Abstração',
        'field': 'abstracao_concluido',
        'slug': 'abstracao',
        'template': 'conteudo-abstracao.html', # NOVO CAMPO
        'order': 4,
        'description': 'Foque apenas nas informações importantes, ignorando detalhes irrelevantes.',
        'lessons': 2, 'exercises': 1, 'dependency_field': 'reconhecimento_padroes_concluido'
    },
    {
        'title': '5. Algoritmos',
        'field': 'algoritmo_concluido',
        'slug': 'algoritmo',
        'template': 'conteudo-algoritmo.html', # NOVO CAMPO
        'order': 5,
        'description': 'Desenvolva sequências lógicas e organizadas para resolver problemas de forma eficaz.',
        'lessons': 2, 'exercises': 1, 'dependency_field': 'abstracao_concluido'
    },
    {
        'title': '6. Projeto Final',
        'field': 'projeto_final_concluido',
        'slug': 'projeto-final',
        'template': 'conteudo-projeto-final.html', # NOVO CAMPO
        'order': 6,
        'description': 'Aplique todos os pilares do PC para solucionar um desafio prático de sala de aula.',
        'lessons': 1, 'exercises': 0, 'dependency_field': 'algoritmo_concluido'
    },
]

# DICIONÁRIO AUXILIAR PARA ACESSO RÁPIDO AO MÓDULO POR SLUG (Otimização)
MODULO_BY_SLUG = {m['slug']: m for m in MODULO_CONFIG}


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

def calculate_progress(progresso_db):
    """Calcula todas as métricas de progresso do curso e retorna a lista de módulos."""
    
    total_modules = len(MODULO_CONFIG)
    completed_modules = 0
    total_lessons = sum(m['lessons'] for m in MODULO_CONFIG)
    total_exercises = sum(m['exercises'] for m in MODULO_CONFIG)
    completed_lessons = 0
    completed_exercises = 0
    
    dynamic_modules = []
    
    for module_config in MODULO_CONFIG:
        db_field = module_config['field']
        is_completed = getattr(progresso_db, db_field, False)
        
        # Lógica de Desbloqueio (BASEADA NA DEPENDÊNCIA explícita)
        dependency_field = module_config.get('dependency_field')
        
        if dependency_field is None:
            # Módulo 1 (Introdução) é sempre desbloqueado
            is_unlocked_for_current_module = True
        else:
            # Desbloqueado se o módulo de dependência estiver concluído no banco de dados
            dependency_is_completed = getattr(progresso_db, dependency_field, False)
            is_unlocked_for_current_module = dependency_is_completed 

        # Contadores
        if is_completed:
            completed_modules += 1
            completed_lessons += module_config['lessons']
            completed_exercises += module_config['exercises']

        dynamic_modules.append({
            'title': module_config['title'],
            'description': module_config['description'],
            'slug': module_config['slug'],
            'order': module_config['order'],
            'is_unlocked': is_unlocked_for_current_module,
            'is_completed': is_completed,
            'lessons': module_config['lessons'],
            'exercises': module_config['exercises'],
        })
    
    overall_progress_percent = int((completed_modules / total_modules) * 100) if total_modules > 0 else 0
    
    return {
        'overall_percent': overall_progress_percent,
        'completed_modules': completed_modules,
        'total_modules': total_modules,
        'completed_lessons': completed_lessons,
        'total_lessons': total_lessons,
        'completed_exercises': completed_exercises,
        'total_exercises': total_exercises,
        'modules': dynamic_modules 
    }

# =========================================================
# 4. ROTAS DE AUTENTICAÇÃO (Sem alterações)
# ... (cadastro, login, logout)
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
# 5. ROTAS DE ÁREA RESTRITA E PERFIL (GET/POST) (Sem alterações)
# ... (index, dashboard, perfil, progresso)
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
            
        # Garante que o usuário tem o objeto mais recente em caso de erro/sucesso
        return render_template('perfil.html', user=usuario) # Este retorno é o final da lógica POST

    # Lógica GET
    return render_template('perfil.html', user=usuario)

@app.route('/progresso')
@requires_auth
def progresso():
    usuario = usuario_logado()
    progresso_db = usuario.progresso 
    
    # CHAMA A FUNÇÃO DE CÁLCULO
    progresso_data = calculate_progress(progresso_db) 

    context = {
        'user': usuario,
        'title': "Meu Progresso",
        'progresso_data': progresso_data 
    }
    
    return render_template('progresso.html', **context)

# =========================================================
# 6. ROTAS DE CERTIFICADO (Gerando o documento LaTeX) (Sem alterações)
# ... (certificado, gerar_certificado, generate_latex_certificate)
# =========================================================

@app.route('/certificado')
@requires_auth
def certificado():
    usuario = usuario_logado()
    progresso_db = usuario.progresso
    
    # Recalcula o progresso para garantir o status de conclusão
    progresso_data = calculate_progress(progresso_db)
    
    # 1. Verifica se o certificado está disponível (100% de conclusão)
    certificado_disponivel = progresso_data['overall_percent'] == 100
    
    # 2. GERA A DATA FORMATADA NO PYTHON
    data_emissao = datetime.now().strftime('%d/%m/%Y')
    
    context = {
        'user': usuario,
        'title': "Certificado",
        'certificado_disponivel': certificado_disponivel,
        'nome_usuario': usuario.nome, # Nome para exibição no certificado
        'data_emissao': data_emissao # Data formatada para o template
    }
    return render_template('certificado.html', **context)

@app.route('/gerar-certificado')
@requires_auth
def gerar_certificado():
    usuario = usuario_logado()
    progresso_db = usuario.progresso
    progresso_data = calculate_progress(progresso_db)
    
    # Verifica se o certificado está disponível
    if progresso_data['overall_percent'] != 100:
        flash('Você deve concluir todos os módulos para gerar o certificado.', 'warning')
        return redirect(url_for('certificado'))

    # Dados para o certificado
    nome_completo = usuario.nome.upper()
    
    # Formato de data para LaTeX: "21 de \%B de \%Y"
    data_conclusao_str = datetime.now().strftime('%d de \%B de \%Y')
    
    # Gera o conteúdo LaTeX
    latex_content = generate_latex_certificate(nome_completo, data_conclusao_str)
    
    # Retorna o arquivo LaTeX como resposta
    # A plataforma irá compilar este arquivo .tex para PDF para o usuário
    return Response(
        latex_content,
        mimetype='application/x-tex',
        headers={'Content-Disposition': f'attachment;filename=Certificado_{nome_completo.replace(" ", "_")}.tex'}
    )

def generate_latex_certificate(nome_completo, data_conclusao):
    """Gera o código LaTeX para o certificado."""
    # Definição das cores para replicar o fundo escuro e a borda clara.
    # Usando Noto Serif para dar um toque mais formal e acadêmico.
    return f"""
\\documentclass[landscape, a4paper, 12pt]{{article}}

% --- UNIVERSAL PREAMBLE BLOCK ---
% Define geometria e margens
\\usepackage[a4paper, top=1.5cm, bottom=1.5cm, left=1.5cm, right=1.5cm]{{geometry}}
\\usepackage{{fontspec}}

% Configuração de línguas e fontes (Português e Inglês)
\\usepackage[portuguese, bidi=basic, provide=*]{{babel}}

\\babelprovide[import, onchar=ids fonts]{{portuguese}}
\\babelprovide[import, onchar=ids fonts]{{english}}

% Define a fonte principal (serif)
\\babelfont{{rm}}{{Noto Serif}}
\\pagestyle{{empty}} % Remove números de página e cabeçalhos

% Pacotes de estilo
\\usepackage{{xcolor}}
\\usepackage{{parskip}}
\\usepackage{{ragged2e}}
\\usepackage{{tikz}} % Usado para desenhar o fundo e a borda

% Define cores para o esquema de design
\\definecolor{{CorFundo}}{{HTML}}{{191923}} % Cor escura (quase preta)
\\definecolor{{CorPrincipal}}{{HTML}}{{FFFFFF}} % Branco
\\definecolor{{CorDestaque}}{{HTML}}{{F9D038}} % Amarelo Dourado

% Comando para a linha de assinatura
\\newcommand{{\\assinatura}}[2]{{
    \\begin{{minipage}}[t]{{0.45\\textwidth}}
        \\centering
        \\vspace{{1cm}}
        {{\\color{{CorDestaque}}\\rule{{\\linewidth}}{{0.5pt}}}} % Linha dourada
        \\small{{\\color{{CorPrincipal}}\\textbf{{#1}}}} \\\\
        \\tiny{{\\color{{CorPrincipal}}\\textit{{#2}}}}
    \\end{{minipage}}
}}

\\begin{{document}}
\\begin{{tikzpicture}}[overlay, remember picture]
    % Desenha o fundo preto/escuro que preenche toda a página
    \\fill[fill=CorFundo] (current page.south west) rectangle (current page.north east);
    
    % Desenha a borda decorativa (retângulo mais interno, estilo moldura)
    \\draw[color=CorPrincipal, line width=8pt]
        ([xshift=5mm, yshift=5mm]current page.south west)
        rectangle ([xshift=-5mm, yshift=-5mm]current page.north east);
\\end{{tikzpicture}}

\\begin{{center}}
\\color{{CorPrincipal}} % Todo o texto será branco

\\vspace*{{2cm}}

% Título do Logo (Simulando o "PC Teacher" com cores)
{{\\Huge\\textbf{PC} \\color{{CorDestaque}}\\textbf{TEACHER}}}

\\vspace{{1.5cm}}

% Título Principal
{{\\fontsize{{50pt}}{{60pt}}\\selectfont\\textbf{CERTIFICADO}}} 

\\vspace{{1.5cm}}

{{\\Large Certificamos que}}

\\vspace{{1cm}}

% Nome do Aluno
{{\\fontsize{{35pt}}{{40pt}}\\selectfont\\textbf{{{nome_completo}}}}}

\\vspace{{1.5cm}}

% Conteúdo
\\parbox{{0.8\\textwidth}}{{\\centering
    concluiu com êxito o curso de \\textbf{{Pensamento Computacional}} realizado
    na plataforma \\textbf{{PC Teacher}}, com carga horária total de \\textbf{{40 horas}}.
}}

\\vspace{{1.5cm}}

{{\\large Manaus, {data_conclusao}.}}

\\vspace{{2cm}}

% Assinaturas
\\begin{{tabular}}{{@{{\\extracolsep{{3cm}}}}cc}}
\\assinatura{{PC TEACHER}}{{Instrutor Chefe}} & \\assinatura{{PROFESSOR}}{{Professor do Curso}} \\\\
\\end{{tabular}}

\\end{{center}}

\\end{{document}}
"""


# =========================================================
# 7. ROTAS DE INFORMAÇÕES (Sem alterações)
# ... (infor-curso-decomposicao, etc.)
# =========================================================
@app.route('/infor-curso-decomposicao')
def infor_curso_decomposicao():
    usuario = usuario_logado()
    return render_template('infor-curso-decomposicao.html', user=usuario)

@app.route('/infor-curso-rec-padrao')
def infor_curso_rec_padrao():
    usuario = usuario_logado()
    return render_template('infor-curso-rec-padrao.html', user=usuario)

@app.route('/infor-curso-abstracao')
def infor_curso_abstracao():
    usuario = usuario_logado()
    return render_template('infor-curso-abstracao.html', user=usuario)

@app.route('/infor-curso-algoritmo')
def infor_curso_algoritmo():
    usuario = usuario_logado()
    return render_template('infor-curso-algoritmo.html', user=usuario)


# =========================================================
# 8. ROTAS DE CONTEÚDO DE CURSO (Protegidas por autenticação)
# =========================================================

@app.route('/modulos')
@requires_auth
def modulos():
    usuario = usuario_logado()
    progresso = usuario.progresso
    
    # 1. Calcula o progresso e obtém os dados dinâmicos
    progresso_data = calculate_progress(progresso)
    
    # 2. Extrai a lista de módulos com status de desbloqueio/conclusão
    modulos_list = progresso_data.get('modules', []) 

    # 3. Passa a lista e o progresso_data para o template
    return render_template('modulos.html', user=usuario, modulos=modulos_list, progresso_data=progresso_data)

@app.route('/concluir-modulo/<string:modulo_nome>', methods=['POST'])
@requires_auth
def concluir_modulo(modulo_nome):
    usuario = usuario_logado()
    progresso = usuario.progresso
    
    # CORREÇÃO CRÍTICA: Normaliza o nome do módulo (substitui '_' por '-')
    # para garantir que o slug corresponde ao MODULO_CONFIG.
    slug_normalizado = modulo_nome.replace('_', '-')
    
    # Usa o dicionário auxiliar MODULO_BY_SLUG para obter as informações
    modulo_config = MODULO_BY_SLUG.get(slug_normalizado) # <-- Usa o SLUG NORMALIZADO
    
    if not modulo_config:
        # Se ainda falhar, exibe o nome original que causou o erro
        flash(f'Erro: Módulo "{modulo_nome}" não encontrado no mapeamento.', 'danger')
        return redirect(url_for('modulos'))

    db_field = modulo_config['field']
    
    # 1. VERIFICA SE O MÓDULO ANTERIOR ESTÁ CONCLUÍDO ANTES DE PERMITIR A CONCLUSÃO
    # (Prevenção contra requisições POST diretas)
    dependency_field = modulo_config.get('dependency_field')
    if dependency_field and not getattr(progresso, dependency_field, False):
         flash('Você deve completar o módulo anterior primeiro para registrar a conclusão deste.', 'warning')
         return redirect(url_for('modulos'))

    # 2. ATUALIZA o campo no objeto de progresso do usuário
    try:
        # Define a flag de conclusão como True
        setattr(progresso, db_field, True) 
        
        # Tenta comitar a mudança no banco de dados
        db.session.commit() 
        
        # Encontra o próximo módulo para sugerir o redirecionamento
        proximo_modulo_order = modulo_config['order'] + 1
        proximo_modulo = next((m for m in MODULO_CONFIG if m['order'] == proximo_modulo_order), None)
        
        if proximo_modulo:
            flash(f'Módulo "{modulo_config["title"]}" concluído com sucesso! Prossiga para o próximo: {proximo_modulo["title"]}', 'success')
        else:
             flash(f'Módulo "{modulo_config["title"]}" concluído com sucesso! Você finalizou o curso!', 'success')
        
    except Exception as e:
        # Em caso de erro no DB, faz rollback e notifica
        db.session.rollback()
        flash(f'Erro ao concluir o módulo: {e}', 'danger')
        
    return redirect(url_for('modulos'))


# ROTA DINÂMICA (Não precisa de alteração, pois já usa o slug do MODULO_CONFIG)
@app.route('/conteudo/<string:modulo_slug>')
@requires_auth
def conteudo_dinamico(modulo_slug):
    usuario = usuario_logado()
    progresso = usuario.progresso
    
    # 1. Encontra a configuração do módulo
    modulo_config = MODULO_BY_SLUG.get(modulo_slug)

    if not modulo_config:
        flash('Módulo de conteúdo não encontrado.', 'danger')
        return redirect(url_for('modulos'))
    
    # 2. Verifica a dependência (lógica de desbloqueio)
    dependency_field = modulo_config.get('dependency_field')
    
    # Se existe uma dependência, e ela não está concluída no DB
    if dependency_field and not getattr(progresso, dependency_field, False):
        # NOTA: Removi a informação do campo do DB da flash message, pois é técnica
        flash(f'Você deve completar o módulo anterior primeiro.', 'warning')
        return redirect(url_for('modulos'))
        
    # 3. Renderiza o template do módulo
    template_name = modulo_config['template']
    return render_template(template_name, user=usuario, progresso=progresso, modulo=modulo_config)

# =========================================================
# 9. EXECUÇÃO
# =========================================================

if __name__ == '__main__':
    with app.app_context():
        # Cria as tabelas do banco de dados se elas não existirem
        db.create_all()
        
    app.run(debug=True)