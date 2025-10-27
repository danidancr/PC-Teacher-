import os
from functools import wraps
from datetime import datetime
import json # NOVO: Importa json para manipular a chave de serviço
import json 

import firebase_admin 
from firebase_admin import credentials, firestore, auth


# =========================================================
# 1. CONFIGURAÇÃO GERAL
# =========================================================
app = Flask(__name__)

# Configurações de segurança
# Em produção, o Render fornecerá a 'SECRET_KEY'
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'sua_chave_secreta_padrao_muito_longa')


# =========================================================
# 1.1 CONFIGURAÇÃO FIREBASE ADMIN SDK (NOVO)
# 1.1 CONFIGURAÇÃO FIREBASE ADMIN SDK
# =========================================================
try:
    # 1. Tenta carregar da variável de ambiente (USO EM PRODUÇÃO)
    FIREBASE_SERVICE_ACCOUNT_JSON = os.environ.get('FIREBASE_CONFIG_JSON')

    if FIREBASE_SERVICE_ACCOUNT_JSON:
        # Carrega o JSON da string (variável de ambiente)
        cred_json = json.loads(FIREBASE_SERVICE_ACCOUNT_JSON)
        cred = credentials.Certificate(cred_json)
        print("INFO: Credenciais carregadas da variável de ambiente 'FIREBASE_CONFIG_JSON'.")
    else:
        # 2. Tenta carregar de um arquivo local (USO EM DESENVOLVIMENTO)
        cred = credentials.Certificate('serviceAccountKey.json')
        print("INFO: Credenciais carregadas do arquivo local 'serviceAccountKey.json'.")

except FileNotFoundError:
    print("AVISO: Arquivo 'serviceAccountKey.json' não encontrado localmente.")
    cred = None
except Exception as e:
    # Este erro pode ocorrer se o JSON da variável de ambiente for mal-formado
    print(f"ERRO ao carregar credenciais: {e}")
    cred = None

# Inicializa o Firebase apenas se as credenciais foram carregadas com sucesso
if not firebase_admin._apps and cred:
    firebase_admin.initialize_app(cred, {
        'projectId': "pc-teacher-6c75f",
@@ -54,21 +45,21 @@
elif not firebase_admin._apps:
    print("ERRO CRÍTICO: Firebase Admin SDK não foi inicializado. Verifique as credenciais.")


# =========================================================
# 3. HELPERS E DECORATORS (REVISADOS)
# 1.2. CONFIGURAÇÃO ESTÁTICA DOS MÓDULOS (ATUALIZADO)
# =========================================================

# --- CONFIGURAÇÃO ESTÁTICA DOS MÓDULOS (Sem alterações) ---
# Adicionado 'min_acertos_para_desbloqueio'
MODULO_CONFIG = [
    # ... (Seu MODULO_CONFIG permanece o mesmo) ...
    {
        'title': '1. Introdução ao Pensamento Computacional',
        'field': 'introducao_concluido',
        'field': 'introducao_concluido', # Mantido para compatibilidade, mas o slug é a chave principal
        'slug': 'introducao',
        'template': 'conteudo-introducao.html', 
        'order': 1,
        'description': 'Entenda o que é o Pensamento Computacional, seus pilares e por que ele é crucial para o futuro.',
        'lessons': 1, 'exercises': 5, 'dependency_field': None
        'lessons': 1, 'exercises': 5, 'dependency_field': None,
        'min_acertos_para_desbloqueio': 3 # NOVO: Acertos mínimos para conclusão/desbloqueio
    },
    {
        'title': '2. Decomposição',
@@ -77,7 +68,8 @@
        'template': 'conteudo-decomposicao.html', 
        'order': 2,
        'description': 'Aprenda a quebrar problemas complexos em partes menores e gerenciáveis.',
        'lessons': 1, 'exercises': 5, 'dependency_field': 'introducao_concluido'
        'lessons': 1, 'exercises': 5, 'dependency_field': 'introducao', # Agora usa o slug
        'min_acertos_para_desbloqueio': 3
    },
    {
        'title': '3. Reconhecimento de Padrões',
@@ -86,7 +78,8 @@
        'template': 'conteudo-rec-padrao.html', 
        'order': 3,
        'description': 'Identifique similaridades e tendências para simplificar a resolução de problemas.',
        'lessons': 1, 'exercises': 5, 'dependency_field': 'decomposicao_concluido'
        'lessons': 1, 'exercises': 5, 'dependency_field': 'decomposicao',
        'min_acertos_para_desbloqueio': 3
    },
    {
        'title': '4. Abstração',
@@ -95,7 +88,8 @@
        'template': 'conteudo-abstracao.html', 
        'order': 4,
        'description': 'Foque apenas nas informações importantes, ignorando detalhes irrelevantes.',
        'lessons': 1, 'exercises': 5, 'dependency_field': 'reconhecimento_padroes_concluido'
        'lessons': 1, 'exercises': 5, 'dependency_field': 'rec-padrao',
        'min_acertos_para_desbloqueio': 3
    },
    {
        'title': '5. Algoritmos',
@@ -104,7 +98,8 @@
        'template': 'conteudo-algoritmo.html', 
        'order': 5,
        'description': 'Desenvolva sequências lógicas e organizadas para resolver problemas de forma eficaz.',
        'lessons': 1, 'exercises': 5, 'dependency_field': 'abstracao_concluido'
        'lessons': 1, 'exercises': 5, 'dependency_field': 'abstracao',
        'min_acertos_para_desbloqueio': 3
    },
    {
        'title': '6. Projeto Final',
@@ -113,33 +108,37 @@
        'template': 'conteudo-projeto-final.html', 
        'order': 6,
        'description': 'Aplique todos os pilares do PC para solucionar um desafio prático de sala de aula.',
        'lessons': 1, 'exercises': 0, 'dependency_field': 'algoritmo_concluido'
        'lessons': 1, 'exercises': 0, 'dependency_field': 'algoritmo',
        'min_acertos_para_desbloqueio': 0 # Não tem exercícios
    },
]

MODULO_BY_SLUG = {m['slug']: m for m in MODULO_CONFIG}


# =========================================================
# 2. HELPERS E DECORATORS (REVISADOS)
# =========================================================

def get_firestore_doc(collection_name, doc_id):
    """Auxiliar para buscar um documento no Firestore e retornar como dict."""
    doc_ref = db.collection(collection_name).document(str(doc_id))
    doc = doc_ref.get()
    if doc.exists:
        data = doc.to_dict()
        data['id'] = doc.id # Adiciona o ID do documento ao dict
        data['id'] = doc.id
        return data
    return None

def usuario_logado():
    """Retorna o objeto (dict) Usuario logado ou None, buscando no Firestore."""
    if 'usuario_id' in session:
        # Busca o usuário pelo ID armazenado na sessão
        user_data = get_firestore_doc('usuarios', session['usuario_id'])

        if user_data:
             # Busca o progresso associado (se existir)
            # Busca o progresso associado (se existir)
            progresso_data = get_firestore_doc('progresso', session['usuario_id'])
            # Anexa o progresso ao objeto do usuário para manter a compatibilidade
            # Anexa o progresso ao objeto do usuário
            user_data['progresso'] = progresso_data if progresso_data else {}
            return user_data
    return None
@@ -154,51 +153,74 @@ def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

# 2.2. calculate_progress (ATUALIZADO PARA USAR DICIONÁRIO E LÓGICA DE ACERTOS)
def calculate_progress(progresso_db):
    """Calcula todas as métricas de progresso do curso.
       progresso_db agora é um dicionário (dict) do Firestore."""
        progresso_db é o dicionário completo do documento 'progresso' do Firestore."""

    total_modules = len(MODULO_CONFIG)
    completed_modules = 0
    total_lessons = sum(m['lessons'] for m in MODULO_CONFIG)
    total_exercises = sum(m['exercises'] for m in MODULO_CONFIG)
    
    completed_lessons = 0
    completed_exercises = 0
    completed_exercises = 0 
    total_acertos = 0 
    total_erros = 0 

    dynamic_modules = []

    # Rastreia o progresso para a lógica de desbloqueio
    last_module_was_completed = True 

    for module_config in MODULO_CONFIG:
        db_field = module_config['field']
        slug = module_config['slug']

        # MUDANÇA: Acessa o status de conclusão como uma chave de dicionário
        is_completed = progresso_db.get(db_field, False) 
        # Pega os dados do módulo ou inicializa se não existir
        module_progress = progresso_db.get(slug, {'acertos': 0, 'erros': 0, 'concluido': False})

        # Lógica de Desbloqueio (BASEADA NA DEPENDÊNCIA explícita)
        dependency_field = module_config.get('dependency_field')
        # 1. Status de Conclusão e Contadores
        is_completed = module_progress.get('concluido', False)
        acertos = module_progress.get('acertos', 0)
        erros = module_progress.get('erros', 0)

        if dependency_field is None:
            is_unlocked_for_current_module = True
        module_exercises_done = acertos + erros
        
        # 2. Lógica de Desbloqueio
        # Um módulo está desbloqueado se:
        # a) É o primeiro módulo OU
        # b) O módulo anterior foi COMPLETADO (is_completed)
        if module_config['order'] == 1:
             is_unlocked = True
        else:
            # MUDANÇA: Acessa o status da dependência como chave de dicionário
            dependency_is_completed = progresso_db.get(dependency_field, False)
            is_unlocked_for_current_module = dependency_is_completed 

        # Contadores
             is_unlocked = last_module_was_completed
             
        # 3. Atualiza os Contadores GLOBAIS
        total_acertos += acertos
        total_erros += erros
        
        if is_completed:
            completed_modules += 1
            completed_lessons += module_config['lessons']
            completed_exercises += module_config['exercises']

            completed_exercises += module_config['exercises'] 
        
        # 4. Prepara dados para o template e atualiza o rastreador
        dynamic_modules.append({
            'title': module_config['title'],
            'description': module_config['description'],
            'slug': module_config['slug'],
            'slug': slug,
            'order': module_config['order'],
            'is_unlocked': is_unlocked_for_current_module,
            'is_unlocked': is_unlocked,
            'is_completed': is_completed,
            'lessons': module_config['lessons'],
            'exercises': module_config['exercises'],
            'min_acertos': module_config['min_acertos_para_desbloqueio'], # NOVO
            'acertos': acertos, 
            'erros': erros, 
            'exercises_done': module_exercises_done, 
        })
        
        last_module_was_completed = is_completed # Prepara para o próximo loop

    overall_progress_percent = int((completed_modules / total_modules) * 100) if total_modules > 0 else 0

@@ -208,13 +230,30 @@ def calculate_progress(progresso_db):
        'total_modules': total_modules,
        'completed_lessons': completed_lessons,
        'total_lessons': total_lessons,
        'completed_exercises': completed_exercises,
        'total_acertos': total_acertos,
        'total_erros': total_erros,
        'completed_exercises': completed_exercises, 
        'total_exercises': total_exercises,
        'modules': dynamic_modules 
    }

# 2.3. Função de Simulação de Correção (NOVO)
def check_answer(modulo_slug, user_answer):
    """
    Função de simulação de correção do exercício.
    Em um ambiente real, esta lógica seria complexa (e.g., verificar código, etc.).
    Aqui, simulamos com uma palavra-chave.
    """
    # Módulos 1-5 (introducao, decomposicao, rec-padrao, abstracao, algoritmo)
    if "certo" in user_answer.lower() or "correto" in user_answer.lower():
         return True
    
    # Se não for uma palavra-chave de acerto, simula um erro.
    return False 


# =========================================================
# 4. ROTAS DE AUTENTICAÇÃO (REVISADAS)
# 3. ROTAS DE AUTENTICAÇÃO (AJUSTE NO CADASTRO)
# =========================================================

@app.route('/cadastro', methods=['GET', 'POST'])
@@ -228,52 +267,45 @@ def cadastro():
        email = request.form.get('email')
        senha = request.form.get('senha')

        # 1. Verifica se o e-mail já existe (Firestore Query)
        email_exists_query = db.collection('usuarios').where('email', '==', email).limit(1).stream()
        email_exists = next(email_exists_query, None)

        if email_exists:
            flash('Este e-mail já está cadastrado. Tente fazer o login.', 'danger')
            return render_template('cadastro.html', nome_for_form=nome, email_for_form=email)

        # 2. Cria novo usuário no Firebase Authentication (Recomendado) e Firestore
        try:
            # 2.1 Criar no Firebase Authentication (para login seguro)
            # Isso gera um UID (ID do usuário) único
            # 2.1 Criar no Firebase Authentication
            user_auth = auth.create_user(email=email, password=senha, display_name=nome)
            user_id = user_auth.uid

            # 2.2 Salvar dados no Firestore (Coleção 'usuarios')
            novo_usuario_data = {
                'nome': nome,
                'email': email,
                'senha_hash': generate_password_hash(senha), # Mantém o hash da senha por compatibilidade, mas o Auth do Firebase deve ser a fonte de verdade
                'senha_hash': generate_password_hash(senha),
                'instituicao': '',
                'telefone': '',
                'cargo': 'Professor(a)',
                'created_at': firestore.SERVER_TIMESTAMP # Para registro de criação
                'created_at': firestore.SERVER_TIMESTAMP
            }
            # Usa o UID do Auth como ID do documento no Firestore
            db.collection('usuarios').document(user_id).set(novo_usuario_data)

            # 2.3 Cria um registro de progresso (Coleção 'progresso')
            # O progresso é um documento separado, usando o mesmo UID
            # 2.3 Cria um registro de progresso (Coleção 'progresso') (ATUALIZADO)
            novo_progresso_data = {
                'introducao_concluido': False,
                'decomposicao_concluido': False,
                'reconhecimento_padroes_concluido': False,
                'abstracao_concluido': False,
                'algoritmo_concluido': False,
                'projeto_final_concluido': False,
                'introducao': {'acertos': 0, 'erros': 0, 'concluido': False},
                'decomposicao': {'acertos': 0, 'erros': 0, 'concluido': False},
                'rec-padrao': {'acertos': 0, 'erros': 0, 'concluido': False},
                'abstracao': {'acertos': 0, 'erros': 0, 'concluido': False},
                'algoritmo': {'acertos': 0, 'erros': 0, 'concluido': False},
                'projeto-final': {'concluido': False}, # Projeto Final não tem acertos/erros
            }
            db.collection('progresso').document(user_id).set(novo_progresso_data)

            flash('Cadastro realizado com sucesso! Faça login para começar.', 'success')
            return redirect(url_for('login'))

        except Exception as e:
            # Em caso de falha de criação, tente limpar o registro
            # Nota: O Firebase Auth lida com a maior parte da transação de forma atômica
            flash(f'Erro interno ao cadastrar: {str(e)}', 'danger')

    return render_template('cadastro.html', user=usuario)
@@ -288,24 +320,15 @@ def login():
        email = request.form.get('email')
        senha = request.form.get('senha')

        # MUDANÇA: O Auth do Firebase é usado para validar a senha, mas
        # para projetos Flask/Admin SDK, é mais simples buscar no Firestore
        # e usar o werkzeug.security se você não estiver usando o Firebase
        # Client SDK para login. 
        
        # 1. Busca o usuário pelo e-mail
        user_query = db.collection('usuarios').where('email', '==', email).limit(1).stream()
        usuario_doc = next(user_query, None)

        if usuario_doc:
            usuario_data = usuario_doc.to_dict()
            usuario_data['id'] = usuario_doc.id # O ID é o UID/Doc ID
            usuario_data['id'] = usuario_doc.id

            # 2. Verifica a senha (usando o hash armazenado por compatibilidade)
            # IDEALMENTE: Você usaria o Firebase Client SDK aqui para fazer o login
            # e obter o Token de autenticação.
            if 'senha_hash' in usuario_data and check_password_hash(usuario_data['senha_hash'], senha):
                session['usuario_id'] = usuario_data['id'] # Salva o ID (UID) no Flask Session
                session['usuario_id'] = usuario_data['id']
                flash(f'Bem-vindo(a), {usuario_data["nome"]}!', 'success')
                return redirect(url_for('dashboard'))

@@ -314,14 +337,13 @@ def login():

    return render_template('login.html', user=usuario)

# A rota /logout permanece a mesma, pois só usa o Flask session
@app.route('/logout')
def logout():
    """Remove o ID da sessão e redireciona para a página inicial."""
    session.pop('usuario_id', None)
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('index'))


# =========================================================
# 4.1 INFORMAÇÃO
# =========================================================
@@ -347,14 +369,10 @@ def infor_curso_algoritmo():
    return render_template('infor-curso-algoritmo.html', user=usuario)



# =========================================================
# 5. ROTAS DE ÁREA RESTRITA E PERFIL (REVISADAS)
# 4. ROTAS DE CONTEÚDO E PROGRESSO (MAIS ALTERAÇÕES)
# =========================================================

# As rotas 'index', 'dashboard' e 'progresso' permanecem iguais em sua lógica de renderização,
# pois usam a função 'usuario_logado' e 'calculate_progress' que foram atualizadas.

@app.route('/')
def index():
    usuario = usuario_logado()
@@ -366,84 +384,10 @@ def dashboard():
    usuario = usuario_logado()
    return render_template('dashboard.html', user=usuario)


@app.route('/perfil', methods=['GET', 'POST']) 
@requires_auth
def perfil():
    usuario = usuario_logado()
    
    if request.method == 'POST':
        user_id = usuario['id'] # Obtém o ID/UID do usuário logado
        
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        institution = request.form.get('institution')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        tem_erro = False
        
        try:
            # 1. Dicionário para atualização no Firestore
            update_data = {}
            
            # 2. Checa e atualiza E-mail
            if email != usuario['email']:
                # Verifica se o novo e-mail já existe para outro usuário (Firestore Query)
                email_existente_query = db.collection('usuarios').where('email', '==', email).limit(1).stream()
                email_existente = next(email_existente_query, None)
                
                # Garante que, se o e-mail existir, não é o documento do usuário atual
                if email_existente and email_existente.id != user_id:
                    flash("Este novo e-mail já está em uso por outro usuário.", 'danger')
                    tem_erro = True
                else:
                    update_data['email'] = email
                    
            # 3. Processa a mudança de senha
            if new_password:
                if new_password != confirm_password:
                    flash("As novas senhas digitadas não coincidem.", 'danger')
                    tem_erro = True
                elif len(new_password) < 6:
                    flash("A nova senha deve ter no mínimo 6 caracteres.", 'danger')
                    tem_erro = True
                else:
                    # MUDANÇA: Atualiza no Firebase Authentication E no Firestore (para o hash)
                    auth.update_user(user_id, password=new_password)
                    update_data['senha_hash'] = generate_password_hash(new_password)
                    flash("Senha atualizada com sucesso!", 'success')

            # 4. Atualiza dados básicos
            update_data['nome'] = name
            update_data['telefone'] = phone
            update_data['instituicao'] = institution
            
            if not tem_erro and update_data:
                # 5. Commit no Firestore
                db.collection('usuarios').document(user_id).update(update_data)
                
                # Se não atualizou a senha, exibe sucesso nos dados
                if not new_password:
                    flash("Dados do perfil atualizados com sucesso!", 'success')
            
            # Redireciona para recarregar o usuário atualizado
            return redirect(url_for('perfil'))
                
        except Exception as e:
            flash(f"Ocorreu um erro inesperado ao salvar: {str(e)}", 'danger')
            # Retorna o template para não perder os dados do formulário
            return render_template('perfil.html', user=usuario) 

    # Lógica GET: A função usuario_logado já retorna o usuário atualizado
    return render_template('perfil.html', user=usuario)

@app.route('/progresso')
@requires_auth
def progresso():
    usuario = usuario_logado()
    # MUDANÇA: progresso_db agora é um dicionário contido dentro do objeto usuario
    progresso_db = usuario.get('progresso', {}) 

    progresso_data = calculate_progress(progresso_db) 
@@ -456,106 +400,194 @@ def progresso():

    return render_template('progresso.html', **context)

@app.route('/modulos')
@requires_auth
def modulos():
    usuario = usuario_logado()
    progresso = usuario.get('progresso', {})
    
    progresso_data = calculate_progress(progresso)
    modulos_list = progresso_data.get('modules', []) 

# =========================================================
# 6. ROTAS DE CERTIFICADO (REVISADAS)
# =========================================================
# O cálculo do progresso já foi adaptado, estas rotas só precisam garantir
# que pegam o progresso como dicionário.
    return render_template('modulos.html', user=usuario, modulos=modulos_list, progresso_data=progresso_data)

@app.route('/certificado')

@app.route('/conteudo/<string:modulo_slug>')
@requires_auth
def certificado():
def conteudo_dinamico(modulo_slug):
    usuario = usuario_logado()
    progresso_db = usuario.get('progresso', {})
    user_id = usuario['id']
    progresso = usuario.get('progresso', {})

    progresso_data = calculate_progress(progresso_db)
    modulo_config = MODULO_BY_SLUG.get(modulo_slug)

    if not modulo_config:
        flash('Módulo de conteúdo não encontrado.', 'danger')
        return redirect(url_for('modulos'))

    certificado_disponivel = progresso_data['overall_percent'] == 100
    data_emissao = datetime.now().strftime('%d/%m/%Y')
    # 2. Verifica a dependência (lógica de desbloqueio)
    dependency_slug = modulo_config.get('dependency_field')
    if dependency_slug:
         # Verifica se o módulo de dependência está concluído (o campo 'concluido' é True)
         is_dependency_met = progresso.get(dependency_slug, {}).get('concluido', False)
         if not is_dependency_met:
             flash(f'Você deve completar o módulo anterior primeiro para acessar este.', 'warning')
             return redirect(url_for('modulos'))
        
    # Lógica de contexto extra para o template (mantida a lógica de Projeto Final)
    extra_context = {}

    context = {
        'user': usuario,
        'title': "Certificado",
        'certificado_disponivel': certificado_disponivel,
        'nome_usuario': usuario['nome'], 
        'data_emissao': data_emissao
    }
    return render_template('certificado.html', **context)
    if modulo_slug == 'projeto-final':
        respostas_projeto_modulos = {}
        respostas_query = db.collection('respostas_projeto').where('usuario_id', '==', user_id).stream()
        
        for r_doc in respostas_query:
            r = r_doc.to_dict()
            respostas_projeto_modulos[r['modulo_slug']] = r['conteudo_resposta']
            
        respostas_projeto_ordenadas = []
        for mod in MODULO_CONFIG:
            if mod['slug'] != 'projeto-final': 
                respostas_projeto_ordenadas.append({
                    'title': mod['title'],
                    'slug': mod['slug'],
                    'resposta': respostas_projeto_modulos.get(mod['slug'], 'Nenhuma resposta salva.'),
                    'is_saved': mod['slug'] in respostas_projeto_modulos
                })
        
        extra_context = {'respostas_projeto': respostas_projeto_ordenadas}
    else:
        # Para outros módulos (1 a 5), checa se já existe uma resposta salva para preencher o campo
        doc_id = f"{user_id}_{modulo_slug}"
        resposta_pre_salva = get_firestore_doc('respostas_projeto', doc_id)
        
        extra_context = {
            'resposta_anterior': resposta_pre_salva.get('conteudo_resposta', '') if resposta_pre_salva else ''
        }
        
    # Adiciona o status do progresso do módulo para o template
    progresso_modulo = progresso.get(modulo_slug, {'acertos': 0, 'erros': 0, 'concluido': False})
    extra_context['progresso_modulo'] = progresso_modulo
    extra_context['min_acertos'] = modulo_config.get('min_acertos_para_desbloqueio')

@app.route('/gerar-certificado')
    template_name = modulo_config['template']
    return render_template(template_name, user=usuario, modulo=modulo_config, **extra_context)


@app.route('/submeter-exercicio/<string:modulo_slug>', methods=['POST'])
@requires_auth
def gerar_certificado():
def submeter_exercicio(modulo_slug):
    usuario = usuario_logado()
    user_id = usuario['id']
    progresso_ref = db.collection('progresso').document(user_id)
    progresso_db = usuario.get('progresso', {})
    progresso_data = calculate_progress(progresso_db)

    if progresso_data['overall_percent'] != 100:
        flash('Você deve concluir todos os módulos para gerar o certificado.', 'warning')
        return redirect(url_for('certificado'))
    modulo_config = MODULO_BY_SLUG.get(modulo_slug)
    
    if not modulo_config or modulo_config['exercises'] == 0:
        return jsonify({'success': False, 'message': 'Módulo não encontrado ou sem exercícios.'}), 404
        
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Requisição deve ser JSON.'}), 400
        
    user_answer = request.get_json().get('resposta', '').strip()
    
    # Verifica se o módulo já está concluído
    current_progress = progresso_db.get(modulo_slug, {'acertos': 0, 'erros': 0, 'concluido': False})
    if current_progress.get('concluido'):
        return jsonify({'success': True, 'message': 'Módulo já concluído!', 'is_module_completed': True, 'new_acertos': current_progress['acertos'], 'new_erros': current_progress['erros']})

    nome_completo = usuario['nome'].upper()
    data_conclusao_str = datetime.now().strftime('%d de \%B de \%Y')
    carga_horaria = 24 
    # --- 1. Corrige a Resposta e Prepara a Atualização ---
    is_correct = check_answer(modulo_slug, user_answer) 

    latex_content = generate_latex_certificate(nome_completo, data_conclusao_str, carga_horaria)
    acertos_path = f'{modulo_slug}.acertos'
    erros_path = f'{modulo_slug}.erros'
    concluido_path = f'{modulo_slug}.concluido'

    return Response(
        latex_content,
        mimetype='application/x-tex',
        headers={'Content-Disposition': f'attachment;filename=Certificado_{nome_completo.replace(" ", "_")}.tex'}
    )
    update_data = {}
    
    # Usa firestore.Increment para atualização atômica
    if is_correct:
        update_data[acertos_path] = firestore.Increment(1)
        
    else:
        update_data[erros_path] = firestore.Increment(1)

# A função generate_latex_certificate não foi alterada, pois não toca no DB.
    # --- 2. Simula o Status Pós-Incremento para Feedback ---
    
    current_acertos = current_progress.get('acertos', 0)
    current_erros = current_progress.get('erros', 0)
    
    new_acertos_simulated = current_acertos + (1 if is_correct else 0)
    new_erros_simulated = current_erros + (1 if not is_correct else 0)

    min_acertos = modulo_config.get('min_acertos_para_desbloqueio', 3) 
    
    is_module_completed = False
    flash_message = ""
    
    if new_acertos_simulated >= min_acertos:
        # Marca o módulo como concluído no DB
        update_data[concluido_path] = True
        is_module_completed = True
        flash_message = f'Parabéns! Você atingiu {min_acertos} acertos e concluiu o módulo "{modulo_config["title"]}". O próximo módulo foi desbloqueado.'
    elif is_correct:
         flash_message = f'Resposta correta! Faltam apenas {min_acertos - new_acertos_simulated} acertos para concluir o módulo.'
    else:
         flash_message = f'Resposta incorreta. Você tem {new_acertos_simulated} acerto(s) até agora. Mínimo: {min_acertos}.'

# =========================================================
# 8. ROTAS DE CONTEÚDO DE CURSO (REVISADAS)
# =========================================================

@app.route('/modulos')
@requires_auth
def modulos():
    usuario = usuario_logado()
    progresso = usuario.get('progresso', {})
    
    progresso_data = calculate_progress(progresso)
    modulos_list = progresso_data.get('modules', []) 
    # --- 3. Commit e Retorno JSON ---
    try:
        progresso_ref.update(update_data)
        
        # O Firestore.Increment é assíncrono, mas o resultado final é garantido.
        # Retornamos os valores simulados para um feedback mais imediato, 
        # ou forçamos um 'get' (o que é custoso) para ter o valor real.
        # Para fins práticos e de desempenho, usaremos os valores simulados no feedback.
        return jsonify({
            'success': True,
            'message': flash_message,
            'is_correct': is_correct,
            # Retorna o valor *após* a submissão (simulado)
            'new_acertos': new_acertos_simulated, 
            'new_erros': new_erros_simulated,     
            'is_module_completed': is_module_completed,
            'min_acertos': min_acertos
        })

    return render_template('modulos.html', user=usuario, modulos=modulos_list, progresso_data=progresso_data)
    except Exception as e:
        print(f"Erro ao salvar submissão do exercício {modulo_slug}: {e}") 
        return jsonify({'success': False, 'message': f'Erro interno ao salvar no DB: {str(e)}'}), 500


@app.route('/salvar-projeto-modulo/<string:modulo_slug>', methods=['POST'])
@requires_auth
def salvar_projeto_modulo(modulo_slug):
    usuario = usuario_logado()
    user_id = usuario['id'] # UID do Firestore
    user_id = usuario['id']

    if not request.is_json:
        return jsonify({'success': False, 'message': 'Requisição deve ser JSON.'}), 400

    data = request.get_json() 
    field_name = f'project_idea_{MODULO_BY_SLUG.get(modulo_slug, {}).get("order", 0)}'
    project_idea = data.get(field_name) 

    # NOTE: O campo 'field_name' não é necessário se você passa o slug. O slug deve ser suficiente.
    project_idea = data.get('conteudo_resposta') # Mudei para um nome genérico
    
    if not project_idea or len(project_idea.strip()) < 10:
        return jsonify({'success': False, 'message': 'Resposta muito curta ou ausente.'}), 400

    # MUDANÇA: As respostas são armazenadas em um documento na coleção 'respostas_projeto'.
    # Usamos uma chave composta (usuario_id + modulo_slug) para o ID do documento
    doc_id = f"{user_id}_{modulo_slug}"
    resposta_ref = db.collection('respostas_projeto').document(doc_id)

    try:
        # Dados a serem salvos/atualizados
        resposta_data = {
            'usuario_id': user_id,
            'modulo_slug': modulo_slug,
            'conteudo_resposta': project_idea,
            'data_atualizacao': firestore.SERVER_TIMESTAMP # Atualiza o timestamp
            'data_atualizacao': firestore.SERVER_TIMESTAMP 
        }

        # Use set(data, merge=True) para criar se não existir ou atualizar se existir
        resposta_ref.set(resposta_data, merge=True)

        return jsonify({'success': True, 'message': 'Ideia de projeto salva com sucesso!'})
@@ -565,115 +597,189 @@ def salvar_projeto_modulo(modulo_slug):
        return jsonify({'success': False, 'message': f'Erro interno ao salvar no DB: {str(e)}'}), 500


@app.route('/concluir-modulo/<string:modulo_nome>', methods=['POST'])
# Rota para concluir o Projeto Final (Módulo 6), já que não é por acertos
@app.route('/concluir-projeto-final', methods=['POST'])
@requires_auth
def concluir_modulo(modulo_nome):
def concluir_projeto_final():
    usuario = usuario_logado()
    user_id = usuario['id']
    progresso = usuario.get('progresso', {}) # Progresso como dicionário
    
    slug_normalizado = modulo_nome.replace('_', '-')
    modulo_config = MODULO_BY_SLUG.get(slug_normalizado)
    progresso = usuario.get('progresso', {})

    modulo_slug = 'projeto-final'
    modulo_config = MODULO_BY_SLUG.get(modulo_slug)

    if not modulo_config:
        flash(f'Erro: Módulo "{modulo_nome}" não encontrado no mapeamento.', 'danger')
        flash(f'Erro: Módulo Projeto Final não encontrado.', 'danger')
        return redirect(url_for('modulos'))

    db_field = modulo_config['field']
    
    # 1. VERIFICA DEPENDÊNCIA (usa o dicionário 'progresso')
    dependency_field = modulo_config.get('dependency_field')
    if dependency_field and not progresso.get(dependency_field, False):
        flash('Você deve completar o módulo anterior primeiro para registrar a conclusão deste.', 'warning')
        return redirect(url_for('modulos'))
    # Verifica se a dependência (Algoritmo) foi concluída
    dependency_slug = modulo_config.get('dependency_field')
    if dependency_slug and not progresso.get(dependency_slug, {}).get('concluido', False):
         flash('Você deve completar todos os módulos anteriores para concluir o Projeto Final.', 'warning')
         return redirect(url_for('modulos'))

    # 2. ATUALIZA o campo no documento de progresso do usuário no Firestore
    try:
        progresso_ref = db.collection('progresso').document(user_id)

        # Atualiza o campo específico no documento
        # Atualiza o campo 'concluido' do projeto-final
        progresso_ref.update({
            db_field: True
             f'{modulo_slug}.concluido': True
        })

        # Encontra o próximo módulo (lógica de redirecionamento permanece a mesma)
        proximo_modulo_order = modulo_config['order'] + 1
        proximo_modulo = next((m for m in MODULO_CONFIG if m['order'] == proximo_modulo_order), None)
        
        if proximo_modulo:
            flash(f'Módulo "{modulo_config["title"]}" concluído com sucesso! Prossiga para o próximo: {proximo_modulo["title"]}', 'success')
        else:
            flash(f'Módulo "{modulo_config["title"]}" concluído com sucesso! Você finalizou o curso!', 'success')
        flash(f'{modulo_config["title"]} concluído com sucesso! Você finalizou o curso!', 'success')

    except Exception as e:
        flash(f'Erro ao concluir o módulo: {e}', 'danger')
        flash(f'Erro ao concluir o Projeto Final: {e}', 'danger')

    return redirect(url_for('modulos'))

# =========================================================
# 5. ROTAS DE CERTIFICADO (SEM ALTERAÇÕES RELEVANTES NA LÓGICA)
# =========================================================

@app.route('/conteudo/<string:modulo_slug>')
# Esta função precisa existir para que o código funcione, mas você não a forneceu no prompt.
def generate_latex_certificate(nome, data, carga):
    """Gera o conteúdo LaTeX do certificado."""
    # Retorna um TEX de exemplo
    return f"""\\documentclass{{article}}
\\usepackage[utf8]{{inputenc}}
\\usepackage[T1]{{fontenc}}
\\begin{{document}}
\\centering
\\Huge CERTIFICADO DE CONCLUSÃO \\par
\\vspace{{1cm}}
\\Large Certificamos que \\textbf{{{nome}}} \\par
concluiu com êxito o Curso de Pensamento Computacional. \\par
\\vspace{{1cm}}
\\large Carga Horária: {carga} horas. \\par
\\vspace{{1cm}}
\\small Emitido em: {data}
\\end{{document}}
"""

@app.route('/certificado')
@requires_auth
def conteudo_dinamico(modulo_slug):
def certificado():
    usuario = usuario_logado()
    user_id = usuario['id']
    progresso = usuario.get('progresso', {})
    progresso_db = usuario.get('progresso', {})

    modulo_config = MODULO_BY_SLUG.get(modulo_slug)
    progresso_data = calculate_progress(progresso_db)
    
    certificado_disponivel = progresso_data['overall_percent'] == 100
    data_emissao = datetime.now().strftime('%d/%m/%Y')
    
    context = {
        'user': usuario,
        'title': "Certificado",
        'certificado_disponivel': certificado_disponivel,
        'nome_usuario': usuario['nome'], 
        'data_emissao': data_emissao
    }
    return render_template('certificado.html', **context)

    if not modulo_config:
        flash('Módulo de conteúdo não encontrado.', 'danger')
        return redirect(url_for('modulos'))
@app.route('/gerar-certificado')
@requires_auth
def gerar_certificado():
    usuario = usuario_logado()
    progresso_db = usuario.get('progresso', {})
    progresso_data = calculate_progress(progresso_db)

    # 2. Verifica a dependência (lógica de desbloqueio)
    dependency_field = modulo_config.get('dependency_field')
    if dependency_field and not progresso.get(dependency_field, False):
        flash(f'Você deve completar o módulo anterior primeiro.', 'warning')
        return redirect(url_for('modulos'))
        
    # 3. LÓGICA ESPECÍFICA PARA O MÓDULO FINAL (carregar respostas)
    respostas_projeto_modulos = {}
    extra_context = {}
    if progresso_data['overall_percent'] != 100:
        flash('Você deve concluir todos os módulos para gerar o certificado.', 'warning')
        return redirect(url_for('certificado'))

    nome_completo = usuario['nome'].upper()
    data_conclusao_str = datetime.now().strftime('%d de \%B de \%Y')
    carga_horaria = 24 

    if modulo_slug == 'projeto-final':
        # MUDANÇA: Busca todas as respostas do projeto deste usuário (Firestore Query)
        respostas_query = db.collection('respostas_projeto').where('usuario_id', '==', user_id).stream()
    latex_content = generate_latex_certificate(nome_completo, data_conclusao_str, carga_horaria)
    
    return Response(
        latex_content,
        mimetype='application/x-tex',
        headers={'Content-Disposition': f'attachment;filename=Certificado_{nome_completo.replace(" ", "_")}.tex'}
    )


# =========================================================
# 6. ROTAS DE PERFIL
# =========================================================

@app.route('/perfil', methods=['GET', 'POST']) 
@requires_auth
def perfil():
    usuario = usuario_logado()
    
    if request.method == 'POST':
        user_id = usuario['id'] 

        for r_doc in respostas_query:
            r = r_doc.to_dict()
            # Mapeia as respostas para um dicionário: {'introducao': 'texto...', 'decomposicao': 'texto...'}
            respostas_projeto_modulos[r['modulo_slug']] = r['conteudo_resposta']
            
        respostas_projeto_ordenadas = []
        for mod in MODULO_CONFIG:
            if mod['slug'] != 'projeto-final': 
                respostas_projeto_ordenadas.append({
                    'title': mod['title'],
                    'slug': mod['slug'],
                    'resposta': respostas_projeto_modulos.get(mod['slug'], 'Nenhuma resposta salva.'),
                    'is_saved': mod['slug'] in respostas_projeto_modulos
                })
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        institution = request.form.get('institution')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        extra_context = {'respostas_projeto': respostas_projeto_ordenadas}
    else:
        # Para outros módulos (1 a 5), checa se já existe uma resposta salva para preencher o campo
        doc_id = f"{user_id}_{modulo_slug}"
        resposta_pre_salva = get_firestore_doc('respostas_projeto', doc_id)
        tem_erro = False

        extra_context = {
            'resposta_anterior': resposta_pre_salva.get('conteudo_resposta', '') if resposta_pre_salva else ''
        }
        try:
            update_data = {}
            
            # 2. Checa e atualiza E-mail
            if email != usuario['email']:
                email_existente_query = db.collection('usuarios').where('email', '==', email).limit(1).stream()
                email_existente = next(email_existente_query, None)
                
                if email_existente and email_existente.id != user_id:
                    flash("Este novo e-mail já está em uso por outro usuário.", 'danger')
                    tem_erro = True
                else:
                    update_data['email'] = email
                    
            # 3. Processa a mudança de senha
            if new_password:
                if new_password != confirm_password:
                    flash("As novas senhas digitadas não coincidem.", 'danger')
                    tem_erro = True
                elif len(new_password) < 6:
                    flash("A nova senha deve ter no mínimo 6 caracteres.", 'danger')
                    tem_erro = True
                else:
                    # Atualiza no Firebase Authentication E no Firestore (para o hash)
                    auth.update_user(user_id, password=new_password)
                    update_data['senha_hash'] = generate_password_hash(new_password)
                    flash("Senha atualizada com sucesso!", 'success')

    # 4. Renderiza o template do módulo
    template_name = modulo_config['template']
    return render_template(template_name, user=usuario, progresso=progresso, modulo=modulo_config, **extra_context)
            # 4. Atualiza dados básicos
            update_data['nome'] = name
            update_data['telefone'] = phone
            update_data['instituicao'] = institution
            
            if not tem_erro and update_data:
                # 5. Commit no Firestore
                db.collection('usuarios').document(user_id).update(update_data)
                
                if not new_password:
                    flash("Dados do perfil atualizados com sucesso!", 'success')
                
                # Redireciona para recarregar o usuário atualizado
                return redirect(url_for('perfil'))
                    
            if tem_erro:
                 # Se houve erro no processamento (e.g., senhas não coincidem), 
                 # re-renderiza com os dados do formulário
                 return render_template('perfil.html', user=usuario)
                
        except Exception as e:
            flash(f"Ocorreu um erro inesperado ao salvar: {str(e)}", 'danger')
            return render_template('perfil.html', user=usuario) 

    return render_template('perfil.html', user=usuario)


# =========================================================
# 9. EXECUÇÃO
# 7. EXECUÇÃO
# =========================================================

if __name__ == '__main__':
    # REMOVIDO: db.create_all() 
    
    # Roda o servidor de desenvolvimento
    app.run(debug=True)
