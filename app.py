import streamlit as st
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import OneHotEncoder
from sklearn.metrics import mean_absolute_error

st.set_page_config(page_title="МОСС", layout="wide")

st.title("МОСС - Модель оценки стоимости специалиста")
st.markdown("Интеллектуальная система прогнозирования рыночной заработной платы на основе машинного обучения.")


# Загрузка и очистка данных
@st.cache_data
def load_data():
    # Убедитесь, что имя файла верное (возможно, должно быть .csv, а не .csv.csv)
    df = pd.read_csv('data/hh_vacancies_final_clean.csv.csv', encoding='utf-8')

    # ДОБАВЛЕНО: professional_roles или name критически важны для прогноза!
    cols_to_use = ['salary_avg', 'area_name', 'professional_roles', 'experience', 'employment_form', 'work_schedule',
                   'working_hours']
    cols_to_use = [c for c in cols_to_use if c in df.columns]

    # 1. Удаление пропусков в целевой переменной
    df = df.dropna(subset=['salary_avg'])

    # 2. Удаление экстремальных выбросов (оставляем только от 1-го до 99-го процентиля)
    q_low = df['salary_avg'].quantile(0.01)
    q_high = df['salary_avg'].quantile(0.99)
    df = df[(df['salary_avg'] >= q_low) & (df['salary_avg'] <= q_high)]

    for col in cols_to_use:
        if col != 'salary_avg':
            df[col] = df[col].fillna('Не указано')
            # Если в ячейке несколько значений через запятую, берем первое и очищаем от пробелов
            df[col] = df[col].apply(
                lambda x: str(x).split(',')[0].strip() if pd.notna(x) and ',' in str(x) else str(x).strip())
            df[col] = df[col].replace(['', 'nan', 'NaN', 'None', 'null'], 'Не указано')

    return df[cols_to_use]


# Ограничение редких категорий (увеличили до 20 для сохранения полезной информации)
def limit_categories(df, col, top_n=20):
    top_cats = df[col].value_counts().head(top_n).index
    df[col] = df[col].where(df[col].isin(top_cats), 'Другое')
    return df


# Обучение модели
@st.cache_resource
def train_model(df):
    with st.spinner('⏳ Обучение модели... Это может занять 1-2 минуты.'):
        df_processed = df.copy()

        for col in df_processed.columns:
            if col != 'salary_avg':
                df_processed = limit_categories(df_processed, col, top_n=20)

        features = [c for c in df_processed.columns if c != 'salary_avg']
        target = 'salary_avg'

        X = df_processed[features]
        # СЕКРЕТНЫЙ ИНГРЕДИЕНТ: обучаем модель на логарифме зарплаты
        y = np.log1p(df_processed[target])

        progress = st.progress(0)
        progress.text('Кодирование признаков...')

        encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
        X_encoded = encoder.fit_transform(X)

        progress.progress(50)
        progress.text('Обучение Random Forest (100 деревьев, оптимизированных)...')

        # Улучшенные гиперпараметры: больше деревьев, ограничение глубины для борьбы с переобучением
        model = RandomForestRegressor(
            n_estimators=100,
            max_depth=15,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1
        )
        model.fit(X_encoded, y)

        progress.progress(100)
        progress.text('✅ Модель обучена!')

        # Предсказываем логарифм и возвращаем к обычным числам через expm1
        y_pred_log = model.predict(X_encoded)
        y_pred = np.expm1(y_pred_log)
        y_true = np.expm1(y)  # возвращаем истинные значения для расчета ошибки

        mae = mean_absolute_error(y_true, y_pred)

        return model, encoder, features, mae


# Основной поток
with st.spinner('📂 Загрузка и очистка данных...'):
    df = load_data()

model, encoder, features, mae = train_model(df)

st.sidebar.header("Параметры профиля")

# Если в данных есть колонка professional_roles, добавляем её в интерфейс
has_roles = 'professional_roles' in df.columns
if has_roles:
    role = st.sidebar.selectbox("Должность / Профессия", sorted(df['professional_roles'].unique()))

city = st.sidebar.selectbox("Город", sorted(df['area_name'].unique()))
experience = st.sidebar.selectbox("Опыт работы", sorted(df['experience'].unique()))
employment = st.sidebar.selectbox("Тип занятости", sorted(df['employment_form'].unique()))
schedule = st.sidebar.selectbox("График работы",
                                sorted(df['work_schedule'].unique())) if 'work_schedule' in df.columns else None
hours = st.sidebar.selectbox("Рабочее время",
                             sorted(df['working_hours'].unique())) if 'working_hours' in df.columns else None

if st.sidebar.button("Рассчитать рыночную стоимость", type="primary"):
    input_dict = {
        'area_name': city,
        'experience': experience,
        'employment_form': employment
    }
    if has_roles:
        input_dict['professional_roles'] = role
    if schedule:
        input_dict['work_schedule'] = schedule
    if hours:
        input_dict['working_hours'] = hours

    input_data = pd.DataFrame([input_dict])

    # Приводим входные данные к тому же виду, что и обучающая выборка
    for col in features:
        if col not in input_data.columns:
            input_data[col] = 'Не указано'

    input_data = input_data[features]

    input_encoded = encoder.transform(input_data)

    # Предсказываем логарифм и расшифровываем его обратно в рубли
    prediction_log = model.predict(input_encoded)[0]
    prediction = np.expm1(prediction_log)

    st.success(f"💰 Прогнозируемая рыночная зарплата: **{int(prediction):,} руб.**")
    st.info(f"📊 Средняя ошибка модели (MAE): ±{int(mae):,} руб.")

st.markdown("---")
col1, col2, col3 = st.columns(3)
col1.metric("Проанализировано вакансий (после очистки)", f"{len(df):,}")
col2.metric("Количество признаков", len(features))
col3.metric("Точность модели (MAE)", f"{int(mae):,} руб.")