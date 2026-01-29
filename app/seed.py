from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Option, Question, Response, Survey


async def seed_if_empty(session: AsyncSession) -> None:
    survey = await session.scalar(select(Survey).limit(1))
    if survey:
        responses_count = await session.scalar(
            select(func.count(Response.id)).where(Response.survey_id == survey.id)
        )
        if responses_count and responses_count > 0:
            return
        question_ids = (
            await session.scalars(select(Question.id).where(Question.survey_id == survey.id))
        ).all()
        if question_ids:
            await session.execute(delete(Option).where(Option.question_id.in_(question_ids)))
            await session.execute(delete(Question).where(Question.id.in_(question_ids)))
            await session.commit()
    else:
        survey = Survey(code="assistant_v1", title="Анкета ассистента")
        session.add(survey)
        await session.flush()

    questions_data = [
        {
            "code": "consent",
            "text": (
                "Согласие на обработку персональных данных:\n\n"
                "Нажимая кнопку «Продолжить» и заполняя анкету, я даю согласие на обработку моих персональных данных: "
                "ФИО, контактных данных, сведений об опыте работы, профессиональных навыках и иной информации, "
                "указанной мной в анкете и резюме.\n"
                "Я подтверждаю, что данные предоставляются добровольно с целью подбора вакансий и возможной передачи "
                "моей анкеты и резюме потенциальным работодателям.\n"
                "Мне известно, что я могу отозвать своё согласие, написав по контактам, указанным в политике конфиденциальности."
            ),
            "type": "single_choice",
            "order": 0,
            "options": ["Продолжить"],
        },
        {
            "code": "fio",
            "text": "Имя",
            "type": "text",
            "order": 1,
            "help_text": "Формат: Имя",
        },
        {
            "code": "contact",
            "text": "Контакты",
            "type": "contact",
            "order": 2,
            "help_text": "Формат: Ссылка на соц.сеть / номер телефона",
        },
        {
            "code": "tasks",
            "text": "Какие задачи хочешь (и умеешь) делать? ➡️",
            "type": "multi_choice",
            "order": 3,
            "options": [
                "Ведение календаря, встреч, перелётов",
                "Контроль задач руководителя",
                "Коммуникация с подрядчиками",
                "Поиск и контроль исполнителей",
                "Подготовка документов / презентаций",
                "Организация мероприятий / поездок",
                "Финансовый контроль / отчёты / таблицы",
                "Ведение личных дел руководителя",
                "Личные поручения (подарки, химчистки, записи к врачам и тд)",
                "Полный day-to-day быт руководителя",
                "Технический SMM / постинг",
            ],
        },
        {
            "code": "work_format",
            "text": "Предпочтительный формат работы ➡️",
            "type": "multi_choice",
            "order": 4,
            "options": ["Удалённо", "Гибрид", "Только офис"],
        },
        {
            "code": "conditions_schedule",
            "text": "Удобные условия и график работы ➡️",
            "type": "multi_choice",
            "order": 5,
            "options": [
                "Готова к переезду",
                "Готова к командировкам",
                "Полный день",
                "Частичная",
                "Проектная",
                "Несколько проектов параллельно",
            ],
        },
        {
            "code": "work_style",
            "text": "Предпочтительный стиль работы➡️",
            "type": "multi_choice",
            "order": 6,
            "options": [
                "Быстрый, динамичный",
                "Спокойный, системный",
                "Чёткие задачи и дедлайны",
                "Уважение к личному времени",
                "Доверие и делегирование",
                "Без микроменеджмента",
                "Открытый к диалогу",
            ],
        },
        {
            "code": "spheres",
            "text": "В каких сферах предпочтительно работать?➡️",
            "type": "multi_choice",
            "order": 7,
            "options": [
                "IT / стартапы",
                "Онлайн-бизнес / инфобизнес",
                "E-commerce",
                "Продакшн / медиа / блогеры",
                "Инвестиции / финансы",
                "Международные проекты",
                "Креативные индустрии",
                "Госструктуры",
            ],
        },
        {
            "code": "salary",
            "text": "Твой желаемый доход?",
            "type": "single_choice",
            "order": 8,
            "help_text": (
                "Укажи желаемый уровень дохода, исходя из твоего опыта, навыков и уровня ответственности, "
                "который готовы брать на себя."
            ),
            "options": [
                "50 000₽ - 80 000₽",
                "80 000 – 130 000 ₽",
                "130 000 – 200 000 ₽",
                "200 000 – 350 000+ ₽",
            ],
        },
        {
            "code": "official_contract",
            "text": "Оформление?",
            "type": "single_choice",
            "order": 9,
            "options": ["Нужен официальный договор", "Самозанятость/ ГПХ", "Неважно"],
        },
        {
            "code": "positioning",
            "text": "КОРОТКОЕ ПОЗИЦИОНИРОВАНИЕ (САМОЕ ГЛАВНОЕ)",
            "type": "text",
            "order": 10,
            "help_text": (
                "Немного о тебе в свободной форме — как о специалисте и человеке.\n"
                "Всё, что считаешь важным рассказать.\n\n"
                "Пример сильного описания:\n"
                "Системный бизнес/персональный ассистент для занятого руководителя. Беру на себя операционку, "
                "контроль задач, коммуникации и организационные вопросы, чтобы освободить время собственника для стратегии. "
                "Люблю порядок, структуру и понятные договорённости."
            ),
        },
        {
            "code": "files",
            "text": "Резюме кандидата:",
            "type": "file",
            "order": 11,
            "help_text": (
                "Пожалуйста, прикрепите резюме - это самый важный этап анкеты.\n"
                "Без резюме мы не сможем подобрать для вас подходящие вакансии!"
            ),
        },
    ]

    questions = []
    for item in questions_data:
        options = item.pop("options", [])
        question = Question(survey_id=survey.id, **item)
        if question.type == "multi_choice":
            question.allow_multiple = True
        session.add(question)
        await session.flush()
        questions.append(question)
        for idx, opt in enumerate(options, start=1):
            session.add(Option(question_id=question.id, text=opt, value=opt, order=idx))

    await session.commit()
