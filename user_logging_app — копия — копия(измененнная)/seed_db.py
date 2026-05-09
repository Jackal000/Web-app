from app import create_app, db
from app.models import User, ActivityLog
import random
from datetime import datetime, timedelta

app = create_app()

with app.app_context():
    # Очистка и создание таблиц
    db.drop_all()
    db.create_all()
    print("🗑 База данных очищена. Создаём новые таблицы...")

    # Генерация пользователей
    roles = ['admin', 'operator', 'user']
    positions = [
        'Руководитель отдела', 'Системный администратор', 'Аналитик данных',
        'Менеджер проектов', 'Разработчик', 'Тестировщик', 'Бухгалтер',
        'Специалист поддержки', 'Архитектор ПО', 'Дизайнер интерфейсов',
        'DevOps-инженер', 'HR-менеджер', 'Юрист', 'Финансист', 'Логист',
        'Маркетолог', 'Технический писатель', 'Системный аналитик',
        'Специалист по безопасности', 'Оператор ПК'
    ]
    first_names = ['Александр', 'Мария', 'Дмитрий', 'Анна', 'Иван', 'Елена', 'Сергей', 'Ольга', 'Андрей', 'Наталья', 'Павел', 'Татьяна', 'Максим', 'Ирина', 'Артём', 'Светлана', 'Кирилл', 'Юлия', 'Роман', 'Екатерина']
    last_names = ['Иванов', 'Петрова', 'Сидоров', 'Козлова', 'Смирнов', 'Новикова', 'Фёдоров', 'Морозова', 'Волков', 'Лебедева', 'Кузнецов', 'Попова', 'Соколов', 'Михайлова', 'Попов', 'Васильева', 'Лебедев', 'Павлова', 'Новиков', 'Семёнова']

    users = []
    for i in range(20):
        users.append(User(
            username=f'user{i+1}',
            full_name=f'{last_names[i]} {first_names[i]}',
            position=positions[i],
            role=random.choice(roles)
        ))
    db.session.add_all(users)
    db.session.commit()
    print(f"✅ Создано {len(users)} пользователей.")

    # Генерация логов
    actions = [
        ("LOGIN", "Вход в систему"), ("LOGOUT", "Выход из системы"),
        ("VIEW_PAGE", "Просмотр страницы /dashboard"), ("EDIT_PROFILE", "Изменение настроек профиля"),
        ("EXPORT_DATA", "Экспорт отчёта в CSV"), ("ACCESS_DENIED", "Попытка доступа к /admin"),
        ("ERROR_404", "Обращение к несуществующей странице"), ("UPLOAD_FILE", "Загрузка документа"),
        ("CHANGE_PASS", "Смена пароля"), ("DELETE_FILE", "Удаление вложения"),
        ("WARN_TIMEOUT", "Превышение времени сессии"), ("WARN_DISK", "Нехватка места на диске"),
        ("WARN_LOGIN", "Неудачная попытка входа")
    ]

    logs = []
    start_date = datetime.utcnow() - timedelta(days=30)
    for i in range(800):
        user = random.choice(users)
        act_type, desc = random.choice(actions)
        ts = start_date + timedelta(seconds=random.randint(0, 30 * 24 * 3600))
        ip = f"192.168.1.{random.randint(10, 250)}"
        logs.append(ActivityLog(
            user_id=user.id,
            action_type=act_type,
            description=desc,
            timestamp=ts,
            ip_address=ip
        ))

    db.session.add_all(logs)
    db.session.commit()
    print(f"✅ Сгенерировано {len(logs)} записей в логах.")
    print("🚀 База данных успешно пересоздана. Запускайте python run.py")