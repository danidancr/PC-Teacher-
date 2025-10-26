from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import os
from functools import wraps
from datetime import datetime
import json 

import firebase_admin 
from firebase_admin import credentials, firestore, auth

# =========================================================
# 1. CONFIGURAÇÃO GERAL
# =========================================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'sua_chave_secreta_padrao_muito_longa')


# =========================================================
# 1.1 CONFIGURAÇÃO FIREBASE ADMIN SDK
# =========================================================
try:
    FIREBASE_SERVICE_ACCOUNT_JSON = os.environ.get('FIREBASE_CONFIG_JSON')
    
    if FIREBASE_SERVICE_ACCOUNT_JSON:
        cred_json = json.loads(FIREBASE_SERVICE_ACCOUNT_JSON)
        cred = credentials.Certificate(cred_json)
        print("INFO: Credenciais carregadas da variável de ambiente 'FIREBASE_CONFIG_JSON'.")
    else:
        cred = credentials.Certificate('serviceAccountKey.json')
        print("INFO: Credenciais carregadas do arquivo local 'serviceAccountKey.json'.")
        
except FileNotFoundError:
    print("AVISO: Arquivo 'serviceAccountKey.json' não encontrado localmente.")
    cred = None
except Exception as e:
    print(f"ERRO ao carregar credenciais: {e}")
    cred = None

if not firebase_admin._apps and cred:
    firebase_admin.initialize_app(cred, {
        'projectId': "pc-teacher-6c75f",
    })
    db = firestore.client()
    print("INFO: Firebase Admin SDK inicializado com sucesso.")
elif not firebase_admin._apps:
    print("ERRO CRÍTICO: Firebase Admin SDK não foi inicializado. Verifique as credenciais.")


# =========================================================
# 1.2. CONFIGURAÇÃO ESTÁTICA DOS MÓDULOS (ATUALIZADO)
# =========================================================
# Adicionado 'min_acertos_para_desbloqueio'
MODULO_CONFIG = [
    {
        'title': '1. Introdução ao Pensamento Computacional',
        'field': 'introducao_concluido', # Mantido para compatibilidade, mas o slug é a chave principal
        'slug': 'introducao',
        'template': 'conteudo-introducao.html', 
        'order': 1,
        'description': 'Entenda o que é o Pensamento Computacional, seus pilares e por que ele é crucial para o futuro.',
        'lessons': 1, 'exercises': 5, 'dependency_field': None,
        'min_acertos_para_desbloqueio': 3 # NOVO: Acertos mínimos para conclusão/desbloqueio
    },
    {
        'title': '2. Decomposição',
        'field': 'decomposicao_concluido',
        'slug': 'decomposicao',
        'template': 'conteudo-decomposicao.html', 
        'order': 2,
        'description': 'Aprenda a quebrar problemas complexos em partes menores e gerenciáveis.',
        'lessons': 1, 'exercises': 5, 'dependency_field': 'introducao', # Agora usa o slug
        'min_acertos_para_desbloqueio': 3
    },
    {
        'title': '3. Reconhecimento de Padrões',
        'field': 'reconhecimento_padroes_concluido',
        'slug': 'rec-padrao',
        'template': 'conteudo-rec-padrao.html', 
        'order': 3,
        'description': 'Identifique similaridades e tendências para simplificar a resolução de problemas.',
        'lessons': 1, 'exercises': 5, 'dependency_field': 'decomposicao',
        'min_acertos_para_desbloqueio': 3
    },
    {
        'title': '4. Abstração',
        'field': 'abstracao_concluido',
        'slug': 'abstracao',
        'template': 'conteudo-abstracao.html', 
        'order': 4,
        'description': 'Foque apenas nas informações importantes, ignorando detalhes irrelevantes.',
        'lessons': 1, 'exercises': 5, 'dependency_field': 'rec-padrao',
        'min_acertos_para_desbloqueio': 3
    },
    {
        'title': '5. Algoritmos',
        'field': 'algoritmo_concluido',
        'slug': 'algoritmo',
        'template': 'conteudo-algoritmo.html', 
        'order': 5,
        'description': 'Desenvolva sequências lógicas e organizadas para resolver problemas de forma eficaz.',
        'lessons': 1, 'exercises': 5, 'dependency_field': 'abstracao',
        'min_acertos_para_desbloqueio': 3
    },
    {
        'title': '6. Projeto Final',
        'field': 'projeto_final_concluido',
        'slug': 'projeto-final',
        'template': 'conteudo-projeto-final.html', 
        'order': 6,
        'description': 'Aplique todos os pilares do PC para solucionar um desafio prático de sala de aula.',
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
        data['id'] = doc.id
        return data
    return None

def usuario_logado():
    """Retorna o objeto (dict) Usuario logado ou None, buscando no Firestore."""
    if 'usuario_id' in session:
        user_data = get_firestore_doc('usuarios', session['usuario_id'])
        
        if user_data:
            # Busca o progresso associado (se existir)
            progresso_data = get_firestore_doc('progresso', session['usuario_id'])
            # Anexa o progresso ao objeto do usuário
            user_data['progresso'] = progresso_data if progresso_data else {}
            return user_data
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

# 2.2. calculate_progress (ATUALIZADO PARA USAR DICIONÁRIO E LÓGICA DE ACERTOS)
def calculate_progress(progresso_db):
    """Calcula todas as métricas de progresso do curso.
        progresso_db é o dicionário completo do documento 'progresso' do Firestore."""
    
    total_modules = len(MODULO_CONFIG)
    completed_modules = 0
    total_lessons = sum(m['lessons'] for m in MODULO_CONFIG)
    total_exercises = sum(m['exercises'] for m in MODULO_CONFIG)
    
    completed_lessons = 0
    completed_exercises = 0 
    total_acertos = 0 
    total_erros = 0 
    
    dynamic_modules = []
    
    # Rastreia o progresso para a lógica de desbloqueio
    last_module_was_completed = True 

    for module_config in MODULO_CONFIG:
        slug = module_config['slug']
        
        # Pega os dados do módulo ou inicializa se não existir
        module_progress = progresso_db.get(slug, {'acertos': 0, 'erros': 0, 'concluido': False})
        
        # 1. Status de Conclusão e Contadores
        is_completed = module_progress.get('concluido', False)
        acertos = module_progress.get('acertos', 0)
        erros = module_progress.get('erros', 0)
        
        module_exercises_done = acertos + erros
        
        # 2. Lógica de Desbloqueio
        # Um módulo está desbloqueado se:
        # a) É o primeiro módulo OU
        # b) O módulo anterior foi COMPLETADO (is_completed)
        if module_config['order'] == 1:
             is_unlocked = True
        else:
             is_unlocked = last_module_was_completed
             
        # 3. Atualiza os Contadores GLOBAIS
        total_acertos += acertos
        total_erros += erros
        
        if is_completed:
            completed_modules += 1
            completed_lessons += module_config['lessons']
            completed_exercises += module_config['exercises'] 
        
        # 4. Prepara dados para o template e atualiza o rastreador
        dynamic_modules.append({
            'title': module_config['title'],
            'description': module_config['description'],
            'slug': slug,
            'order': module_config['order'],
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
    
    return {
        'overall_percent': overall_progress_percent,
        'completed_modules': completed_modules,
        'total_modules': total_modules,
        'completed_lessons': completed_lessons,
        'total_lessons': total_lessons,
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
# 3. ROTAS DE AUTENTICAÇÃO (AJUSTE NO CADASTRO)
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
        
        email_exists_query = db.collection('usuarios').where('email', '==', email).limit(1).stream()
        email_exists = next(email_exists_query, None)
        
        if email_exists:
            flash('Este e-mail já está cadastrado. Tente fazer o login.', 'danger')
            return render_template('cadastro.html', nome_for_form=nome, email_for_form=email)

        try:
            # 2.1 Criar no Firebase Authentication
            user_auth = auth.create_user(email=email, password=senha, display_name=nome)
            user_id = user_auth.uid
            
            # 2.2 Salvar dados no Firestore (Coleção 'usuarios')
            novo_usuario_data = {
                'nome': nome,
                'email': email,
                'senha_hash': generate_password_hash(senha),
                'instituicao': '',
                'telefone': '',
                'cargo': 'Professor(a)',
                'created_at': firestore.SERVER_TIMESTAMP
            }
            db.collection('usuarios').document(user_id).set(novo_usuario_data)
            
            # 2.3 Cria um registro de progresso (Coleção 'progresso') (ATUALIZADO)
            novo_progresso_data = {
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
            flash(f'Erro interno ao cadastrar: {str(e)}', 'danger')
            
    return render_template('cadastro.html', user=usuario)

@app.route('/login', methods=['GET', 'POST'])
def login():
    usuario = usuario_logado()
    if usuario:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        
        user_query = db.collection('usuarios').where('email', '==', email).limit(1).stream()
        usuario_doc = next(user_query, None)
        
        if usuario_doc:
            usuario_data = usuario_doc.to_dict()
            usuario_data['id'] = usuario_doc.id
            
            if 'senha_hash' in usuario_data and check_password_hash(usuario_data['senha_hash'], senha):
                session['usuario_id'] = usuario_data['id']
                flash(f'Bem-vindo(a), {usuario_data["nome"]}!', 'success')
                return redirect(url_for('dashboard'))

        flash('E-mail ou senha incorretos.', 'danger')
        return render_template('login.html', email_for_form=email)

    return render_template('login.html', user=usuario)

@app.route('/logout')
def logout():
    session.pop('usuario_id', None)
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('index'))


# =========================================================
# 4.1 INFORMAÇÃO
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
# 4. ROTAS DE CONTEÚDO E PROGRESSO (MAIS ALTERAÇÕES)
# =========================================================

@app.route('/')
def index():
    usuario = usuario_logado()
    return render_template('index.html', user=usuario)

@app.route('/dashboard')
@requires_auth
def dashboard():
    usuario = usuario_logado()
    return render_template('dashboard.html', user=usuario)

@app.route('/progresso')
@requires_auth
def progresso():
    usuario = usuario_logado()
    progresso_db = usuario.get('progresso', {}) 
    
    progresso_data = calculate_progress(progresso_db) 

    context = {
        'user': usuario,
        'title': "Meu Progresso",
        'progresso_data': progresso_data 
    }
    
    return render_template('progresso.html', **context)

@app.route('/modulos')
@requires_auth
def modulos():
    usuario = usuario_logado()
    progresso = usuario.get('progresso', {})
    
    progresso_data = calculate_progress(progresso)
    modulos_list = progresso_data.get('modules', []) 

    return render_template('modulos.html', user=usuario, modulos=modulos_list, progresso_data=progresso_data)


@app.route('/conteudo/<string:modulo_slug>')
@requires_auth
def conteudo_dinamico(modulo_slug):
    usuario = usuario_logado()
    user_id = usuario['id']
    progresso = usuario.get('progresso', {})
    
    modulo_config = MODULO_BY_SLUG.get(modulo_slug)

    if not modulo_config:
        flash('Módulo de conteúdo não encontrado.', 'danger')
        return redirect(url_for('modulos'))
    
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

    template_name = modulo_config['template']
    return render_template(template_name, user=usuario, modulo=modulo_config, **extra_context)


@app.route('/submeter-exercicio/<string:modulo_slug>', methods=['POST'])
@requires_auth
def submeter_exercicio(modulo_slug):
    usuario = usuario_logado()
    user_id = usuario['id']
    progresso_ref = db.collection('progresso').document(user_id)
    progresso_db = usuario.get('progresso', {})
    
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

    # --- 1. Corrige a Resposta e Prepara a Atualização ---
    is_correct = check_answer(modulo_slug, user_answer) 
    
    acertos_path = f'{modulo_slug}.acertos'
    erros_path = f'{modulo_slug}.erros'
    concluido_path = f'{modulo_slug}.concluido'
    
    update_data = {}
    
    # Usa firestore.Increment para atualização atômica
    if is_correct:
        update_data[acertos_path] = firestore.Increment(1)
        
    else:
        update_data[erros_path] = firestore.Increment(1)

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

    except Exception as e:
        print(f"Erro ao salvar submissão do exercício {modulo_slug}: {e}") 
        return jsonify({'success': False, 'message': f'Erro interno ao salvar no DB: {str(e)}'}), 500


@app.route('/salvar-projeto-modulo/<string:modulo_slug>', methods=['POST'])
@requires_auth
def salvar_projeto_modulo(modulo_slug):
    usuario = usuario_logado()
    user_id = usuario['id']
    
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Requisição deve ser JSON.'}), 400
        
    data = request.get_json() 
    # NOTE: O campo 'field_name' não é necessário se você passa o slug. O slug deve ser suficiente.
    project_idea = data.get('conteudo_resposta') # Mudei para um nome genérico
    
    if not project_idea or len(project_idea.strip()) < 10:
        return jsonify({'success': False, 'message': 'Resposta muito curta ou ausente.'}), 400

    doc_id = f"{user_id}_{modulo_slug}"
    resposta_ref = db.collection('respostas_projeto').document(doc_id)

    try:
        resposta_data = {
            'usuario_id': user_id,
            'modulo_slug': modulo_slug,
            'conteudo_resposta': project_idea,
            'data_atualizacao': firestore.SERVER_TIMESTAMP 
        }
        
        resposta_ref.set(resposta_data, merge=True)
        
        return jsonify({'success': True, 'message': 'Ideia de projeto salva com sucesso!'})
    
    except Exception as e:
        print(f"Erro ao salvar projeto do módulo {modulo_slug}: {e}") 
        return jsonify({'success': False, 'message': f'Erro interno ao salvar no DB: {str(e)}'}), 500


# Rota para concluir o Projeto Final (Módulo 6), já que não é por acertos
@app.route('/concluir-projeto-final', methods=['POST'])
@requires_auth
def concluir_projeto_final():
    usuario = usuario_logado()
    user_id = usuario['id']
    progresso = usuario.get('progresso', {})

    modulo_slug = 'projeto-final'
    modulo_config = MODULO_BY_SLUG.get(modulo_slug)
    
    if not modulo_config:
        flash(f'Erro: Módulo Projeto Final não encontrado.', 'danger')
        return redirect(url_for('modulos'))

    # Verifica se a dependência (Algoritmo) foi concluída
    dependency_slug = modulo_config.get('dependency_field')
    if dependency_slug and not progresso.get(dependency_slug, {}).get('concluido', False):
         flash('Você deve completar todos os módulos anteriores para concluir o Projeto Final.', 'warning')
         return redirect(url_for('modulos'))

    try:
        progresso_ref = db.collection('progresso').document(user_id)
        
        # Atualiza o campo 'concluido' do projeto-final
        progresso_ref.update({
             f'{modulo_slug}.concluido': True
        })
        
        flash(f'{modulo_config["title"]} concluído com sucesso! Você finalizou o curso!', 'success')
        
    except Exception as e:
        flash(f'Erro ao concluir o Projeto Final: {e}', 'danger')
        
    return redirect(url_for('modulos'))

# =========================================================
# 5. ROTAS DE CERTIFICADO (SEM ALTERAÇÕES RELEVANTES NA LÓGICA)
# =========================================================

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
def certificado():
    usuario = usuario_logado()
    progresso_db = usuario.get('progresso', {})
    
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

@app.route('/gerar-certificado')
@requires_auth
def gerar_certificado():
    usuario = usuario_logado()
    progresso_db = usuario.get('progresso', {})
    progresso_data = calculate_progress(progresso_db)
    
    if progresso_data['overall_percent'] != 100:
        flash('Você deve concluir todos os módulos para gerar o certificado.', 'warning')
        return redirect(url_for('certificado'))

    nome_completo = usuario['nome'].upper()
    data_conclusao_str = datetime.now().strftime('%d de \%B de \%Y')
    carga_horaria = 24 
    
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
        
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        institution = request.form.get('institution')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        tem_erro = False
        
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
# 7. EXECUÇÃO
# =========================================================

if __name__ == '__main__':
    app.run(debug=True)
