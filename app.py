# app.py
from flask import Flask, render_template, request, redirect, url_for, session, abort
from models import db, Usuario, Curso, Modulo, Aula, Progresso
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# --- CONFIGURAÇÃO DO FLASK ---
app = Flask(__name__)
app.secret_key = 'chave_secreta_pc_teacher_123' 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# --- CONTEXT PROCESSOR ---
# Garante que o usuário esteja disponível em todos os templates
@app.context_processor
def inject_user_info():
    if 'logged_in' in session:
        return {'user_name': session.get('user_name'),
                'user_id': session.get('user_id')}
    return {}


# --- FUNÇÕES AUXILIARES DE BACK-END ---

def verificar_acesso_aula(usuario_id, aula_id):
    """Verifica se o usuário pode acessar a aula com base na conclusão sequencial."""
    
    aula_atual = Aula.query.get(aula_id)
    if not aula_atual:
        return False, "Aula não encontrada."
    
    # Busca a aula imediatamente anterior que é sequencial
    aula_anterior = Aula.query.filter(
        Aula.modulo_id == aula_atual.modulo_id,
        Aula.ordem < aula_atual.ordem,
        Aula.sequencial == True 
    ).order_by(Aula.ordem.desc()).first()

    # Se existe uma aula sequencial anterior, verifica o progresso nela
    if aula_anterior:
        progresso_anterior = Progresso.query.filter_by(usuario_id=usuario_id, aula_id=aula_anterior.id).first()
        
        if not progresso_anterior or not progresso_anterior.concluido:
            # Se a anterior não foi concluída, bloqueia
            return False, f"Acesso bloqueado. Conclua: {aula_anterior.titulo}"
            
    # Se não tem aula anterior sequencial OU a anterior foi concluída
    return True, "Acesso permitido."


# --- ROTAS DE AUTENTICAÇÃO ---

@app.route('/')
@app.route('/index.html')
def home():
    return render_template('index.html')

@app.route('/login-simple.html', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('password')
        
        usuario = Usuario.query.filter_by(email=email).first()
        
        if usuario and check_password_hash(usuario.senha, senha):
            session['logged_in'] = True
            session['user_id'] = usuario.id
            session['user_name'] = usuario.nome.split()[0]
            return redirect(url_for('modulos'))
        
        return render_template('login-simple.html', error="Email ou senha incorretos.")
        
    return render_template('login-simple.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('user_id', None)
    session.pop('user_name', None)
    return redirect(url_for('login'))

# --- ROTAS DO DASHBOARD ---

@app.route('/modulos.html')
def modulos():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    cursos = Curso.query.all()
    cursos_com_progresso = []
    usuario_id = session['user_id']
    
    for curso in cursos:
        todas_aulas = Aula.query.join(Modulo).filter(Modulo.curso_id == curso.id).all()
        total_aulas = len(todas_aulas)
        
        aulas_concluidas = Progresso.query.join(Aula).filter(
            Progresso.usuario_id == usuario_id,
            Progresso.concluido == True,
            Aula.id.in_([a.id for a in todas_aulas])
        ).count()
        
        progresso_percentual = int((aulas_concluidas / total_aulas) * 100) if total_aulas > 0 else 0
        
        cursos_com_progresso.append({
            'titulo': curso.titulo,
            'descricao': curso.descricao,
            'progresso_percentual': progresso_percentual,
            'progresso_texto': f"{progresso_percentual}%",
            'modulos': curso.modulos
        })

    return render_template('modulos.html', 
                           cursos=cursos_com_progresso,
                           active_page='modulos')

@app.route('/perfil.html')
def perfil():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    usuario = Usuario.query.get(session['user_id'])
    
    return render_template('perfil.html', 
                           usuario=usuario,
                           active_page='perfil')


# --- ROTAS DE CONTEÚDO E PROGRESSO ---

@app.route('/conteudo-aula/<int:aula_id>', methods=['GET', 'POST'])
def aula_conteudo(aula_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
        
    usuario_id = session['user_id']
    aula = Aula.query.get_or_404(aula_id)

    # 1. Verifica Acesso
    acesso_liberado, _ = verificar_acesso_aula(usuario_id, aula_id)
    if not acesso_liberado:
        # Se for bloqueado, redireciona para a lista de módulos (ou aula anterior)
        # return redirect(url_for('modulos')) 
        # Ou mostra uma página de erro/bloqueio (por simplicidade, vamos permitir 
        # a visualização, mas bloquear o botão de conclusão no template)
        pass 

    # 2. Busca o progresso do usuário para esta aula
    progresso = Progresso.query.filter_by(usuario_id=usuario_id, aula_id=aula_id).first()
    is_concluido = progresso.concluido if progresso else False

    # 3. Monta a navegação lateral
    modulo = aula.modulo
    aulas_navegacao = []
    
    for a in Modulo.query.get(modulo.id).aulas:
        # Status de Conclusão da aula atual da iteração
        p_nav = Progresso.query.filter_by(usuario_id=usuario_id, aula_id=a.id).first()
        concluido_nav = p_nav.concluido if p_nav else False

        # Verifica o status de bloqueio para a navegação
        acesso_nav, _ = verificar_acesso_aula(usuario_id, a.id)
        
        aulas_navegacao.append({
            'id': a.id,
            'titulo': a.titulo,
            'concluido': concluido_nav,
            'ativo': a.id == aula_id,
            'bloqueado': not acesso_nav,
            'url': url_for('aula_conteudo', aula_id=a.id)
        })
    
    return render_template('conteudo-aula-template.html', 
                           aula=aula, 
                           is_concluido=is_concluido,
                           acesso_liberado=acesso_liberado,
                           modulo=modulo,
                           aulas_navegacao=aulas_navegacao,
                           active_page='modulos')


@app.route('/marcar_concluido/<int:aula_id>', methods=['POST'])
def marcar_concluido(aula_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    usuario_id = session['user_id']
    
    # Garante que ele não marque se estiver bloqueado
    acesso_liberado, _ = verificar_acesso_aula(usuario_id, aula_id)
    if not acesso_liberado:
        return redirect(url_for('modulos')) 
        
    progresso = Progresso.query.filter_by(usuario_id=usuario_id, aula_id=aula_id).first()
    if not progresso:
        progresso = Progresso(usuario_id=usuario_id, aula_id=aula_id)
        
    progresso.concluido = True
    progresso.data_conclusao = datetime.utcnow()
    
    db.session.add(progresso)
    db.session.commit()
    
    # Redireciona para a próxima aula
    aula_atual = Aula.query.get_or_404(aula_id)
    
    proxima_aula = Aula.query.filter(
        Aula.modulo_id == aula_atual.modulo_id,
        Aula.ordem > aula_atual.ordem
    ).order_by(Aula.ordem.asc()).first()
    
    if proxima_aula:
        return redirect(url_for('aula_conteudo', aula_id=proxima_aula.id))
    else:
        # Se for a última aula do módulo, volta para a lista de módulos
        return redirect(url_for('modulos'))

# --- Rota do Certificado e Progresso (Simples) ---

@app.route('/progresso.html')
def progresso():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    # Para a rota progresso.html, você pode retornar o template estático por enquanto
    # ou adicionar a lógica de cálculo (que é complexa e faremos depois)
    return render_template('progresso.html', active_page='progresso')
    
@app.route('/certificado.html')
def certificado():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
        
    # Lógica de verificação de conclusão total (simplificada)
    usuario_id = session['user_id']
    
    total_aulas_curso1 = Aula.query.join(Modulo).join(Curso).filter(Curso.titulo == "Pensamento Computacional: Estrutura e Aplicação").count()
    aulas_concluidas = Progresso.query.join(Aula).join(Modulo).join(Curso).filter(
        Progresso.usuario_id == usuario_id,
        Progresso.concluido == True,
        Curso.titulo == "Pensamento Computacional: Estrutura e Aplicação"
    ).count()

    certificado_disponivel = (aulas_concluidas == total_aulas_curso1) and (total_aulas_curso1 > 0)
    
    return render_template('certificado.html', 
                           certificado_disponivel=certificado_disponivel,
                           active_page='certificado')


# --- CRIAÇÃO DO BANCO DE DADOS E DADOS INICIAIS ---

@app.cli.command("initdb")
def initdb_command():
    """Cria as tabelas do banco de dados e popula com dados iniciais."""
    with app.app_context():
        db.drop_all()
        db.create_all()
        
        # 1. Usuário de Teste
        hashed_password = generate_password_hash("123456", method='pbkdf2:sha256')
        user_joao = Usuario(nome="João Professor Silva", email="joao@teste.com", senha=hashed_password)
        db.session.add(user_joao)
        
        # 2. Curso Principal
        curso_pc = Curso(titulo="Pensamento Computacional: Estrutura e Aplicação", 
                         descricao="Este curso abrange os quatro pilares do Pensamento Computacional e sua aplicação prática no currículo do Ensino Fundamental.")
        db.session.add(curso_pc)
        
        curso_robotica = Curso(titulo="Introdução à Robótica Educacional", 
                              descricao="Fundamentos básicos de eletrônica e programação com foco na criação de projetos interativos em sala de aula.")
        db.session.add(curso_robotica)
        db.session.commit() 

        # 3. Módulos
        mod1 = Modulo(curso_id=curso_pc.id, titulo="Decomposição", ordem=1)
        mod2 = Modulo(curso_id=curso_pc.id, titulo="Reconhecimento de Padrões", ordem=2)
        mod3 = Modulo(curso_id=curso_pc.id, titulo="Abstração", ordem=3)
        
        mod_r1 = Modulo(curso_id=curso_robotica.id, titulo="Introdução ao Arduino", ordem=1)
        mod_r2 = Modulo(curso_id=curso_robotica.id, titulo="Sensores e Atuadores", ordem=2)
        
        db.session.add_all([mod1, mod2, mod3, mod_r1, mod_r2])
        db.session.commit()

        # 4. Aulas do Módulo 1 (Decomposição) - Usando o HTML estático como base de conteúdo
        conteudo_aula1_1 = '<p>Seja bem-vindo ao primeiro módulo! Decomposição é o processo de quebrar um problema complexo em partes menores e mais gerenciáveis. Assista ao vídeo e comece o exercício!</p><div class="video-player"><iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ" title="Video Aula" allowfullscreen></iframe></div>'
        aula1_1 = Aula(modulo_id=mod1.id, titulo="Aula 1.1: Introdução ao Conceito", ordem=1, sequencial=True, conteudo_html=conteudo_aula1_1)
        
        conteudo_aula1_2 = '<p>Aprofundando: Usamos a decomposição todos os dias, mas formalizá-la ajuda no pensamento lógico. Veja como aplicar isso em problemas de sala de aula.</p>'
        aula1_2 = Aula(modulo_id=mod1.id, titulo="Aula 1.2: Exemplos Práticos", ordem=2, sequencial=True, conteudo_html=conteudo_aula1_2)
        
        conteudo_ex1_3 = '<p><strong>Desafio!</strong> Dado o cenário: "Organizar a formatura", decomponha-o em 5 subproblemas. Envie suas respostas no campo abaixo.</p>'
        aula1_3 = Aula(modulo_id=mod1.id, titulo="1.3: Exercício de Fixação", ordem=3, sequencial=True, conteudo_html=conteudo_ex1_3)
        
        db.session.add_all([aula1_1, aula1_2, aula1_3])
        
        # 5. Aulas do Módulo 2 (Bloqueado)
        conteudo_aula2_1 = '<p>Este é o conteúdo do módulo 2. Você precisa concluir todas as aulas anteriores para liberar este módulo!</p>'
        aula2_1 = Aula(modulo_id=mod2.id, titulo="Aula 2.1: Conceitos Básicos", ordem=1, sequencial=True, conteudo_html=conteudo_aula2_1)
        db.session.add(aula2_1)
        
        db.session.commit()
        
        # Popula progresso inicial (simulando que o usuário concluiu a primeira aula)
        progresso_1_1 = Progresso(usuario_id=user_joao.id, aula_id=aula1_1.id, concluido=True, data_conclusao=datetime.utcnow())
        db.session.add(progresso_1_1)
        
        db.session.commit()
        print('Banco de dados criado e dados iniciais (usuário e curso) inseridos.')

if __name__ == '__main__':
    # Cria o DB se ainda não existir antes de rodar o Flask
    with app.app_context():
        db.create_all() 
    app.run(debug=True)