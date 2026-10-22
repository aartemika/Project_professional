import streamlit as st
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import OneHotEncoder
from sklearn.metrics import mean_absolute_error

# Настройка страницы
st.set_page_config(page_title="МОСС", layout="wide")

st.title("МОСС - Модель оценки стоимости специалиста")
st.markdown("Интеллектуальная система прогнозирования рыночной заработной платы на основе машинного обучения.")


# Загрузка и подготовка данных
@st.cache_data
def load_data():
    df = pd.read_csv('data/hh_vacancies_final_clean.csv.csv', encoding='utf-8')
    df = df.dropna(subset=['salary_avg', 'area_name', 'experience', 'employment_form'])
    return df


# Обучение модели и создание encoder
@st.cache_resource
def train_model(df):
    features = ['area_name', 'experience', 'employment_form']
    target = 'salary_avg'

    X = df[features]
    y = df[target]

    # Создаем и обучаем OneHotEncoder
    encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
    X_encoded = encoder.fit_transform(X)

    # Получаем названия столбцов после кодирования
    feature_names = encoder.get_feature_names_out(features)

    # Обучаем модель
    model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
    model.fit(X_encoded, y)

    # Считаем ошибку
    y_pred = model.predict(X_encoded)
    mae = mean_absolute_error(y, y_pred)

    return model, encoder, feature_names, mae


df = load_data()
model, encoder, feature_names, mae = train_model(df)

# Боковая панель с настройками
st.sidebar.header("Параметры профиля")

city = st.sidebar.selectbox("Город", sorted(df['area_name'].unique()))
experience = st.sidebar.selectbox("Опыт работы", sorted(df['experience'].unique()))
employment = st.sidebar.selectbox("Тип занятости", sorted(df['employment_form'].unique()))

# Кнопка расчета
if st.sidebar.button("Рассчитать рыночную стоимость"):
    # Подготовка введенных данных
    input_data = pd.DataFrame({
        'area_name': [city],
        'experience': [experience],
        'employment_form': [employment]
    })

    # Используем ТОТ ЖЕ encoder, что и при обучении
    input_encoded = encoder.transform(input_data)

    # Прогноз
    prediction = model.predict(input_encoded)[0]

    # Отображение результата
    st.success(f"Прогнозируемая рыночная зарплата: {int(prediction):,} руб.")
    st.info(f"Средняя ошибка модели (MAE): {int(mae):,} руб.")

# Отображение статистики
st.markdown("---")
col1, col2, col3 = st.columns(3)
col1.metric("Проанализировано вакансий", f"{len(df):,}")
col2.metric("Количество городов", df['area_name'].nunique())
col3.metric("Точность модели (MAE)", f"{int(mae):,} руб.")