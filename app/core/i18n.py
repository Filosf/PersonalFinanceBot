DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = {"en", "ru"}
BASE_CATEGORY_TRANSLATIONS = {
    "ru": {
        "Food": "Еда",
        "Taxi": "Такси",
        "Rent": "Аренда",
        "Entertainment": "Развлечения",
        "General": "Общее",
        "Income": "Доход",
    }
}

TRANSLATIONS = {
    "en": {
        "balance": "Growth / loss",
        "income_added": "Income added",
        "active_expense_days": "Periods with expenses",
        "average_daily_expense": "Average daily expense",
        "biggest_category": "Biggest category",
        "biggest_expense_day": "Biggest expense period",
        "insights": "Period insights",
        "total_expense": "Total expenses",
        "total_income": "Total income",
        "access_key": "Access key",
        "add": "Add",
        "add_expense": "Add expense",
        "add_transaction": "Add transaction",
        "all_categories": "All categories",
        "amount": "Amount",
        "analytics": "Analytics",
        "admin_help": (
            "Admin commands:\n"
            "/admin_stats - service statistics\n"
            "/admin_users - recent users\n"
            "/admin_logs - where to read service logs\n"
            "/admin_last_errors - recent captured errors\n"
            "/admin_db_health - database health check"
        ),
        "apply": "Apply",
        "by_category": "By category",
        "budget_alert": (
            "Budget alert: {name} reached {percent:.0f}%\n"
            "Spent: {spent:.2f} of {amount:.2f} {currency}\n"
            "Remaining: {remaining:.2f} {currency}"
        ),
        "budget_report_empty": (
            "No budgets are set for this month. Open the website to configure budgets."
        ),
        "budget_report_title": "Budgets for {month}",
        "budget_remainders": "Budget remainders",
        "budgets": "Budgets",
        "budgets_saved": "Budgets saved.",
        "categories": "Categories",
        "category": "Category",
        "create": "Create",
        "currency": "Currency",
        "currency_updated": "Currency label updated. Amounts were not converted.",
        "custom": "Custom",
        "dashboard": "Dashboard",
        "date": "Date",
        "delete": "Delete",
        "description": "Description",
        "developer_login": "Developer login",
        "edit": "Edit",
        "edit_hint": "Use the web dashboard to edit all fields.",
        "expense_categories": "Expense categories",
        "expense_added": "Expense added",
        "expense_deleted": "Expense deleted",
        "expenses": "Expenses",
        "filters": "Filters",
        "from_date": "From date",
        "general": "General",
        "amount_error": "Could not recognize the amount. Send something like: 250 taxi",
        "amount_positive_error": "Amount must be greater than zero.",
        "category_added": "Category added: {name}",
        "category_deleted": "Category deleted: {name}",
        "category_created": "Category created.",
        "category_deleted_web": "Category deleted.",
        "category_renamed": "Category renamed.",
        "category_not_found": "Category not found",
        "category_updated": "Category updated",
        "custom_categories": "Editable categories",
        "deleted": "Deleted",
        "commands": (
            "/start - register\n"
            "/help - detailed help\n"
            "/commands - command list\n"
            "/language - choose bot language\n"
            "/month or /month YYYY-MM - monthly income/expense report\n"
            "/range YYYY-MM-DD YYYY-MM-DD - income/expense report for dates\n"
            "/categories - list categories\n"
            "/add_category NAME - create category\n"
            "/web - get a dashboard login link\n"
            "/budgets - monthly budget status\n"
            "/last - show last expense\n"
            "/delete_last - delete last expense"
        ),
        "help": (
            "How to use the finance bot:\n\n"
            "1. Add an expense by sending an amount and optional text:\n"
            "250 taxi\n"
            "120 food\n"
            "70\n\n"
            "2. Add income with a plus sign:\n"
            "+15000 salary\n\n"
            "3. The bot guesses a category from the text. You can change the category "
            "using buttons after adding an expense, or edit everything on the website.\n\n"
            "4. Use /month for this month, /month YYYY-MM for another month, and "
            "/range YYYY-MM-DD YYYY-MM-DD for a custom period.\n\n"
            "5. Use /budgets to see monthly budget progress. Budgets are configured "
            "on the website.\n\n"
            "6. Use /web to get a secure login link for the dashboard. The dashboard "
            "has filters, charts, category editing, budget settings, and full record editing.\n\n"
            "Use /commands when you only need the command list."
        ),
        "language": "Language",
        "language_updated": "Language updated.",
        "choose_language": "Choose language:",
        "last_7_days": "7 days",
        "last_5_years": "5 years",
        "login_hint": "Send /web to the Telegram bot and paste the access key here.",
        "logout": "Logout",
        "max": "Max",
        "min": "Min",
        "month": "Month",
        "month_category_report": "Categories this month",
        "menu_commands": "Commands",
        "menu_help": "Help",
        "menu_web": "Website",
        "new_category": "New category",
        "no_categories": "No categories",
        "no_expenses": "No expenses found",
        "no_expenses_to_delete": "No expenses to delete",
        "no_expenses_yet": "No expenses yet",
        "operations": "Operations",
        "open_dashboard": "Open dashboard",
        "period": "Period",
        "rename": "Rename",
        "merge": "Merge",
        "merge_into": "Merge into",
        "category_empty": "Category is empty",
        "delete_empty_or_merge": "Delete if empty, or merge into selected category",
        "remaining": "left",
        "save": "Save",
        "search_description": "Search description",
        "sign_in": "Sign in",
        "signed_in_as": "Signed in as",
        "tab_analytics": "Analytics",
        "tab_transactions": "Transactions",
        "tab_budgets": "Budgets",
        "tab_categories": "Categories",
        "telegram_id": "Telegram ID",
        "to_date": "To date",
        "total": "Total",
        "total_budget": "Total monthly budget",
        "valid_for_minutes": "Valid for {minutes} minutes.",
        "web_key_intro": "Dashboard access key:",
        "welcome": (
            "Welcome! I help you track personal expenses.\n\n"
            "Send an expense as a message: `250 taxi`, `120 food`, or `70`.\n"
            "Use /month for a monthly summary and /last to see the latest expense.\n"
            "Use /web to get a dashboard login link for filtering, charts, editing, "
            "and category management.\n\n"
            "The permanent buttons below keep website login and help close at hand."
        ),
        "usage_add_category": "Usage: /add_category Groceries",
        "usage_delete_category": "Usage: /delete_category Groceries",
        "usage_month": "Usage: /month or /month YYYY-MM",
        "usage_range": "Usage: /range YYYY-MM-DD YYYY-MM-DD",
        "year": "Year",
    },
    "ru": {
        "balance": "Прирост / убыток",
        "income_added": "Доход добавлен",
        "active_expense_days": "Периодов с расходами",
        "average_daily_expense": "Средний расход в день",
        "biggest_category": "Самая дорогая категория",
        "biggest_expense_day": "Самый дорогой период",
        "insights": "Инсайты периода",
        "total_expense": "Всего расходов",
        "total_income": "Всего доходов",
        "access_key": "Ключ доступа",
        "add": "Добавить",
        "add_expense": "Добавить расход",
        "add_transaction": "Добавить транзакцию",
        "all_categories": "Все категории",
        "amount": "Сумма",
        "analytics": "Аналитика",
        "admin_help": (
            "Админ-команды:\n"
            "/admin_stats - статистика сервиса\n"
            "/admin_users - последние пользователи\n"
            "/admin_logs - где смотреть логи сервиса\n"
            "/admin_last_errors - последние пойманные ошибки\n"
            "/admin_db_health - проверка базы данных"
        ),
        "apply": "Применить",
        "by_category": "По категориям",
        "budget_alert": (
            "Предупреждение по бюджету: {name} достиг {percent:.0f}%\n"
            "Потрачено: {spent:.2f} из {amount:.2f} {currency}\n"
            "Осталось: {remaining:.2f} {currency}"
        ),
        "budget_report_empty": (
            "На этот месяц бюджеты не настроены. Для настройки перейдите на сайт."
        ),
        "budget_report_title": "Бюджеты на {month}",
        "budget_remainders": "Остатки по бюджетам",
        "budgets": "Бюджеты",
        "budgets_saved": "Бюджеты сохранены.",
        "categories": "Категории",
        "category": "Категория",
        "create": "Создать",
        "currency": "Валюта",
        "currency_updated": "Обозначение валюты обновлено. Суммы не пересчитывались.",
        "custom": "Период",
        "dashboard": "Панель",
        "date": "Дата",
        "delete": "Удалить",
        "description": "Описание",
        "developer_login": "Вход для разработки",
        "edit": "Изменить",
        "edit_hint": "Изменить все поля можно в web-панели.",
        "expense_categories": "Категории расходов",
        "expense_added": "Расход добавлен",
        "expense_deleted": "Расход удален",
        "expenses": "Расходы",
        "filters": "Фильтры",
        "from_date": "Дата с",
        "general": "Общее",
        "amount_error": "Не удалось распознать сумму. Отправьте, например: 250 такси",
        "amount_positive_error": "Сумма должна быть больше нуля.",
        "category_added": "Категория добавлена: {name}",
        "category_deleted": "Категория удалена: {name}",
        "category_created": "Категория создана.",
        "category_deleted_web": "Категория удалена.",
        "category_renamed": "Категория переименована.",
        "category_not_found": "Категория не найдена",
        "category_updated": "Категория обновлена",
        "custom_categories": "Редактируемые категории",
        "deleted": "Удалено",
        "commands": (
            "/start - регистрация\n"
            "/help - подробная помощь\n"
            "/commands или /команды - список команд\n"
            "/language или /язык - выбрать язык бота\n"
            "/month или /месяц YYYY-MM - отчет о доходах и расходах за месяц\n"
            "/range или /период YYYY-MM-DD YYYY-MM-DD - отчет о доходах и расходах за период\n"
            "/categories или /категории - список категорий\n"
            "/add_category или /добавить_категорию НАЗВАНИЕ - создать категорию\n"
            "/web или /сайт - ссылка для входа на сайт\n"
            "/budgets или /бюджеты - состояние бюджетов на месяц\n"
            "/last или /последний - последний расход\n"
            "/delete_last или /удалить_последний - удалить последний расход"
        ),
        "help": (
            "Как пользоваться ботом:\n\n"
            "1. Чтобы добавить расход, просто отправьте сумму и описание:\n"
            "250 такси\n"
            "120 еда\n"
            "70\n\n"
            "2. Чтобы добавить доход, поставьте плюс перед суммой:\n"
            "+15000 зарплата\n\n"
            "3. Бот сам попробует выбрать категорию по тексту. После добавления расхода "
            "категорию можно изменить кнопками. На сайте можно изменить сумму, дату, "
            "категорию и описание.\n\n"
            "4. Отчеты: /month покажет текущий месяц, /month YYYY-MM - другой месяц, "
            "а /range YYYY-MM-DD YYYY-MM-DD - выбранный период.\n\n"
            "5. Бюджеты: команда /budgets покажет, сколько уже потрачено и сколько "
            "осталось. Настраиваются бюджеты на сайте.\n\n"
            "6. Сайт открывается через /web. Там есть фильтры, графики, категории, "
            "бюджеты и полное редактирование записей.\n\n"
            "Если нужен только список команд, используйте /commands или /команды."
        ),
        "language": "Язык",
        "language_updated": "Язык обновлен.",
        "choose_language": "Выберите язык:",
        "last_7_days": "7 дней",
        "last_5_years": "5 лет",
        "login_hint": "Отправьте /web боту в Telegram и вставьте ключ доступа здесь.",
        "logout": "Выйти",
        "max": "Макс.",
        "min": "Мин.",
        "month": "Месяц",
        "month_category_report": "Категории за месяц",
        "menu_commands": "Команды",
        "menu_help": "Помощь",
        "menu_web": "Сайт",
        "new_category": "Новая категория",
        "no_categories": "Категорий нет",
        "no_expenses": "Расходов не найдено",
        "no_expenses_to_delete": "Нет расходов для удаления",
        "no_expenses_yet": "Расходов пока нет",
        "operations": "Операций",
        "open_dashboard": "Открыть панель",
        "period": "Период",
        "rename": "Переименовать",
        "merge": "Слить",
        "merge_into": "Слить в",
        "category_empty": "Категория пустая",
        "delete_empty_or_merge": "Удалить пустую или слить в выбранную категорию",
        "remaining": "осталось",
        "save": "Сохранить",
        "search_description": "Поиск по описанию",
        "sign_in": "Войти",
        "signed_in_as": "Вошли как",
        "tab_analytics": "Аналитика",
        "tab_transactions": "Транзакции",
        "tab_budgets": "Бюджеты",
        "tab_categories": "Категории",
        "telegram_id": "Telegram ID",
        "to_date": "Дата по",
        "total": "Итого",
        "total_budget": "Общий бюджет на месяц",
        "valid_for_minutes": "Действует {minutes} минут.",
        "web_key_intro": "Ключ доступа к панели:",
        "welcome": (
            "Добро пожаловать! Я помогаю вести учет личных расходов.\n\n"
            "Отправьте расход сообщением: `250 такси`, `120 еда` или `70`.\n"
            "Команда /month покажет отчет за месяц, а /last - последний расход.\n"
            "Команда /web выдаст ссылку для входа на сайт, где есть фильтры, "
            "графики, редактирование и управление категориями.\n\n"
            "Постоянные кнопки ниже помогут быстро открыть сайт или помощь."
        ),
        "usage_add_category": "Использование: /add_category Продукты",
        "usage_delete_category": "Использование: /delete_category Продукты",
        "usage_month": "Использование: /month или /month YYYY-MM",
        "usage_range": "Использование: /range YYYY-MM-DD YYYY-MM-DD",
        "year": "Год",
    },
}


def normalize_locale(locale: str | None) -> str:
    if locale and locale.lower().startswith("ru"):
        return "ru"
    return DEFAULT_LOCALE


def labels(locale: str | None) -> dict[str, str]:
    return TRANSLATIONS[normalize_locale(locale)]


def tr(locale: str | None, key: str, **kwargs) -> str:
    text = labels(locale).get(key, TRANSLATIONS[DEFAULT_LOCALE].get(key, key))
    return text.format(**kwargs) if kwargs else text


def category_label(name: str, locale: str | None) -> str:
    return BASE_CATEGORY_TRANSLATIONS.get(normalize_locale(locale), {}).get(name, name)
