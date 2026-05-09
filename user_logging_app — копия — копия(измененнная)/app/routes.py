from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, Response, send_file, session
from app.models import User, ActivityLog, SystemSettings
from app import db
from sqlalchemy import func
import csv, io, json, os, time, functools
from datetime import datetime, timedelta

main_bp = Blueprint('main', __name__)
APP_START_TIME = time.time()

DEMO_USERS = {
    'admin': {'password': 'admin123', 'role': 'admin', 'full_name': 'Системный администратор'},
    'operator': {'password': 'operator123', 'role': 'operator', 'full_name': 'Оператор мониторинга'},
    'user': {'password': 'user123', 'role': 'user', 'full_name': 'Сотрудник'}
}

def to_msk(dt, sec=False):
    if not dt: return '—'
    fmt = '%d.%m.%Y %H:%M:%S' if sec else '%d.%m.%Y %H:%M'
    return (dt + timedelta(hours=3)).strftime(fmt)

def get_set(key, default='light'):
    s = SystemSettings.query.filter_by(key=key).first()
    return s.value if s else default

def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated

def role_required(*roles):
    def decorator(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            if session.get('role') not in roles:
                flash('⛔ Доступ запрещён. Недостаточно прав.', 'danger')
                return redirect(url_for('main.dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator

def pass_settings():
    return {
        'theme': get_set('theme'), 'auto_refresh': get_set('auto_refresh') == 'true',
        'table_density': get_set('table_density', 'normal'), 'show_ip': get_set('show_ip', 'true'),
        'hl_err': get_set('highlight_errors', 'true') == 'true',
        'hl_warn': get_set('highlight_warnings', 'true') == 'true',
        'hl_succ': get_set('highlight_success', 'true') == 'true',
        'rows_per_page': int(get_set('rows_per_page', '20')),
        'refresh_interval': int(get_set('refresh_interval', '30')),
        'error_threshold': int(get_set('error_threshold', '10')),
        'enable_sound_alert': get_set('enable_sound_alert', 'true') == 'true',
        'enable_browser_notify': get_set('enable_browser_notify', 'false') == 'true',
        'current_role': session.get('role', 'guest')
    }

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user_data = DEMO_USERS.get(username)
        if user_data and user_data['password'] == password:
            session['user_id'] = username
            session['role'] = user_data['role']
            session['full_name'] = user_data['full_name']
            session['logged_in'] = True
            return redirect(url_for('main.dashboard'))
        flash('❌ Неверный логин или пароль', 'danger')
    return render_template('login.html', theme=get_set('theme'))

@main_bp.route('/logout')
def logout():
    session.clear()
    flash('👋 Вы успешно вышли из системы.', 'info')
    return redirect(url_for('main.login'))

@main_bp.route('/')
@main_bp.route('/dashboard')
@login_required
def dashboard():
    ctx = pass_settings()
    page = request.args.get('page', 1, type=int)
    per_page = ctx['rows_per_page']
    
    # ✅ Разделение доступа по ролям
    is_regular_user = session['role'] == 'user'
    db_user = User.query.filter_by(username='user1').first() if is_regular_user else None
    
    if is_regular_user and db_user:
        # Пользователь видит ТОЛЬКО свою активность
        base_q = ActivityLog.query.filter_by(user_id=db_user.id)
        total_logs = base_q.count()
        active_users = 1
        error_count = base_q.filter(ActivityLog.action_type.in_(['ERROR_404', 'ACCESS_DENIED'])).count()
        
        type_data = db.session.query(ActivityLog.action_type, func.count(ActivityLog.id))\
            .filter(ActivityLog.user_id == db_user.id)\
            .group_by(ActivityLog.action_type).all()
            
        dates = [(datetime.utcnow() - timedelta(days=i)).strftime('%d.%m') for i in range(6, -1, -1)]
        counts = []
        for i in range(6, -1, -1):
            start = datetime.utcnow() - timedelta(days=i+1)
            end = datetime.utcnow() - timedelta(days=i)
            counts.append(ActivityLog.query.filter(
                ActivityLog.user_id == db_user.id,
                ActivityLog.timestamp.between(start, end)
            ).count())
            
        pagination = base_q.order_by(ActivityLog.timestamp.desc()).paginate(page=page, per_page=per_page, error_out=False)
    else:
        # Admin и Operator видят ВСЁ
        base_q = ActivityLog.query
        total_logs = base_q.count()
        active_users = db.session.query(func.count(func.distinct(ActivityLog.user_id))).scalar()
        error_count = base_q.filter(ActivityLog.action_type.in_(['ERROR_404', 'ACCESS_DENIED'])).count()
        
        type_data = db.session.query(ActivityLog.action_type, func.count(ActivityLog.id)).group_by(ActivityLog.action_type).all()
        dates = [(datetime.utcnow() - timedelta(days=i)).strftime('%d.%m') for i in range(6, -1, -1)]
        counts = [ActivityLog.query.filter(ActivityLog.timestamp.between(datetime.utcnow() - timedelta(days=i+1), datetime.utcnow() - timedelta(days=i))).count() for i in range(6, -1, -1)]
        
        pagination = base_q.order_by(ActivityLog.timestamp.desc()).paginate(page=page, per_page=per_page, error_out=False)

    labels_map = {
        'LOGIN': 'Вход в систему', 'LOGOUT': 'Выход', 'VIEW_PAGE': 'Просмотр', 'VIEW': 'Просмотр',
        'EDIT': 'Редактирование', 'EDIT_PROFILE': 'Профиль', 'EXPORT': 'Экспорт', 'EXPORT_DATA': 'Экспорт CSV',
        'UPLOAD': 'Загрузка', 'UPLOAD_FILE': 'Загрузка файла', 'DELETE_FILE': 'Удаление', 'CHANGE_PASS': 'Пароль',
        'ACCESS_DENIED': 'Доступ запрещён', 'DENIED': 'Отказ', 'ERROR_404': '404',
        'WARN_TIMEOUT': 'Таймаут', 'WARN_DISK': 'Диск', 'WARN_LOGIN': 'Неверный пароль'
    }
    
    ctx.update({
        'total_logs': total_logs,
        'active_users': active_users,
        'error_count': error_count,
        'logs': pagination.items, 'pagination': pagination,
        'chart_types_labels': [labels_map.get(t[0], t[0]) for t in type_data],
        'chart_types_data': [t[1] for t in type_data],
        'chart_dates': dates,
        'chart_dates_data': counts
    })
    return render_template('dashboard.html', **ctx)

@main_bp.route('/users')
@login_required
@role_required('admin')
def users(): return render_template('users.html', users=User.query.all(), **pass_settings())

@main_bp.route('/user/<int:user_id>')
@login_required
@role_required('admin', 'operator')
def user_detail(user_id):
    user = User.query.get_or_404(user_id)
    logs = ActivityLog.query.filter_by(user_id=user.id).order_by(ActivityLog.timestamp.desc()).all()
    return render_template('user_detail.html', user=user, logs=logs, **pass_settings())

@main_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'operator')
def settings():
    if request.method == 'POST':
        form_map = {
            'theme': request.form.get('theme', 'light'),
            'auto_refresh': 'true' if request.form.get('auto_refresh') == 'true' else 'false',
            'table_density': request.form.get('table_density', 'normal'),
            'show_ip': 'true' if request.form.get('show_ip') == 'true' else 'false',
            'highlight_errors': 'true' if request.form.get('highlight_errors') == 'true' else 'false',
            'highlight_warnings': 'true' if request.form.get('highlight_warnings') == 'true' else 'false',
            'highlight_success': 'true' if request.form.get('highlight_success') == 'true' else 'false',
            'rows_per_page': request.form.get('rows_per_page', '20'),
            'refresh_interval': request.form.get('refresh_interval', '30'),
            'error_threshold': request.form.get('error_threshold', '10'),
            'enable_sound_alert': 'true' if request.form.get('enable_sound_alert') == 'true' else 'false',
            'enable_browser_notify': 'true' if request.form.get('enable_browser_notify') == 'true' else 'false',
            'retention_days': request.form.get('retention_days', '30')
        }
        for k, v in form_map.items():
            s = SystemSettings.query.filter_by(key=k).first()
            if s: s.value = str(v)
            else: db.session.add(SystemSettings(key=k, value=str(v)))
        db.session.commit()
        flash('✅ Настройки сохранены.', 'success')
        return redirect(url_for('main.settings'))

    ctx = pass_settings()
    ctx['retention'] = int(get_set('retention_days', '30'))
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database.db'))
    ctx['db_size'] = f"{round(os.path.getsize(db_path) / (1024*1024), 2)} МБ" if os.path.exists(db_path) else "—"
    ctx['total_rows'] = ActivityLog.query.count()
    return render_template('settings.html', **ctx)

@main_bp.route('/clear_logs', methods=['POST'])
@login_required
@role_required('admin')
def clear_logs():
    days = int(get_set('retention_days', '30'))
    deleted = ActivityLog.query.filter(ActivityLog.timestamp < (datetime.utcnow() - timedelta(days=days))).delete()
    db.session.commit()
    flash(f'🗑 Удалено {deleted} записей.', 'warning')
    return redirect(url_for('main.settings'))

@main_bp.route('/api/system_info')
@login_required
def api_system_info():
    up = time.time() - APP_START_TIME
    h, m = divmod(int(up // 60), 60)
    return jsonify({'up': f'{h}ч {m}м', 'logs': ActivityLog.query.count(), 'users': User.query.count()})

@main_bp.route('/api/export_config')
@login_required
@role_required('admin')
def api_export_config():
    settings = {r.key: r.value for r in SystemSettings.query.all()}
    return Response(json.dumps(settings, indent=2, ensure_ascii=False), mimetype='application/json', headers={'Content-Disposition': 'attachment;filename=settings.json'})

@main_bp.route('/api/reset_config', methods=['POST'])
@login_required
@role_required('admin')
def api_reset_config():
    defaults = {'theme': 'light', 'auto_refresh': 'false', 'retention_days': '30', 'table_density': 'normal',
                'show_ip': 'true', 'highlight_errors': 'true', 'highlight_warnings': 'true', 'highlight_success': 'true',
                'rows_per_page': '20', 'refresh_interval': '30', 'error_threshold': '10',
                'enable_sound_alert': 'true', 'enable_browser_notify': 'false'}
    for k, v in defaults.items():
        s = SystemSettings.query.filter_by(key=k).first()
        if s: s.value = v
        else: db.session.add(SystemSettings(key=k, value=v))
    db.session.commit()
    flash('⚙️ Сброшено.', 'info')
    return redirect(url_for('main.settings'))

@main_bp.route('/api/logs/<int:log_id>')
@login_required
def api_log_detail(log_id):
    log = ActivityLog.query.get_or_404(log_id)
    return jsonify({'time': to_msk(log.timestamp, True), 'user': log.user.username if log.user else 'Sys',
                    'full_name': log.user.full_name if log.user else '—', 'position': log.user.position if log.user else '—',
                    'role': log.user.role if log.user else '—', 'action': log.action_type, 'desc': log.description, 'ip': log.ip_address})

@main_bp.route('/api/logs/filter/<status>')
@login_required
def api_filter_logs(status):
    q = ActivityLog.query
    if status == 'error': q = q.filter(ActivityLog.action_type.in_(['ERROR_404', 'ACCESS_DENIED']))
    elif status == 'success': q = q.filter(~ActivityLog.action_type.in_(['ERROR_404', 'ACCESS_DENIED']))
    data = q.order_by(ActivityLog.timestamp.desc()).limit(20).all()
    return jsonify([{'id': l.id, 'time': to_msk(l.timestamp), 'user': l.user.username, 'desc': l.description, 'type': l.action_type, 'ip': l.ip_address} for l in data])

@main_bp.route('/api/simulate_action')
@login_required
def simulate_action():
    import random
    user = User.query.order_by(db.func.random()).first()
    if not user: return jsonify({'status': 'error'}), 400
    acts = [("LOGIN", "Вход"), ("VIEW_PAGE", "Просмотр"), ("UPLOAD", "Загрузка"), ("EDIT_PROFILE", "Редактирование"),
            ("EXPORT", "Экспорт"), ("DENIED", "Доступ запрещён"), ("WARN_TIMEOUT", "Таймаут"),
            ("WARN_DISK", "Диск"), ("WARN_LOGIN", "Неверный пароль"), ("ERROR_404", "404")]
    t, d = random.choice(acts)
    db.session.add(ActivityLog(user_id=user.id, action_type=t, description=d, timestamp=datetime.utcnow(), ip_address=f"192.168.1.{random.randint(10,250)}"))
    db.session.commit()
    return jsonify({'status': 'success'})

@main_bp.route('/export')
@login_required
@role_required('admin', 'operator')
def export_logs():
    logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).all()
    
    si = io.StringIO()
    si.write('\ufeff') # ✅ BOM-метка: Excel сразу поймёт, что это UTF-8 с кириллицей
    cw = csv.writer(si, delimiter=';') # ✅ Точка с запятой: стандарт для русского Excel
    
    cw.writerow(['ID', 'User', 'Action', 'Description', 'IP', 'Time'])
    for l in logs:
        cw.writerow([
            l.id, 
            l.user.username if l.user else 'Sys', 
            l.action_type, 
            l.description, 
            l.ip_address, 
            to_msk(l.timestamp, True)
        ])
        
    output = si.getvalue().encode('utf-8')
    return Response(
        output,
        mimetype='text/csv; charset=utf-8-sig',
        headers={'Content-Disposition': 'attachment; filename=logs_export.csv'}
    )

@main_bp.route('/api/backup_db')
@login_required
@role_required('admin')
def backup_db():
    return send_file(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database.db')), as_attachment=True, download_name='userlog_backup.db')

@main_bp.route('/api/optimize_db', methods=['POST'])
@login_required
@role_required('admin')
def optimize_db():
    db.session.execute(db.text('VACUUM'))
    db.session.commit()
    flash('✅ База оптимизирована.', 'success')
    return redirect(url_for('main.settings'))