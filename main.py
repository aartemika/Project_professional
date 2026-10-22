import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

# 1. Загрузка очищенных данных
print("1. Загрузка очищенных данных...")
# Убедись, что файл лежит в той же папке, что и main.py.
# Если он в папке data, измени путь на 'data/hh_vacancies_final_clean.csv'
df = pd.read_csv('data/hh_vacancies_final_clean.csv.csv', encoding='utf-8')

# Проверка наличия нужных столбцов
required_cols = ['salary_avg', 'area_name', 'experience', 'employment_form']
for col in required_cols:
    if col not in df.columns:
        raise ValueError(f"В файле отсутствует необходимый столбец: {col}. Проверь названия.")

# Удаляем строки, где есть пропуски в ключевых столбцах
df = df.dropna(subset=required_cols)

# 2. Подготовка признаков (Feature Engineering)
print("2. Подготовка признаков и кодирование...")
features = ['area_name', 'experience', 'employment_form']
target = 'salary_avg'

X = df[features]
y = df[target]

# One-Hot Encoding для категориальных признаков
X_encoded = pd.get_dummies(X, columns=features, drop_first=True)

# 3. Разделение на обучающую и тестовую выборки
print("3. Разделение данных (80% обучение, 20% тест)...")
X_train, X_test, y_train, y_test = train_test_split(
    X_encoded, y, test_size=0.2, random_state=42
)

# 4. Обучение модели Random Forest
print("4. Обучение модели Random Forest Regressor...")
model = RandomForestRegressor(
    n_estimators=100,
    random_state=42,
    n_jobs=-1
)
model.fit(X_train, y_train)

# 5. Прогноз и оценка качества
print("5. Оценка качества модели...")
y_pred = model.predict(X_test)

mae = mean_absolute_error(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))

print("\n--- РЕЗУЛЬТАТЫ ОЦЕНКИ МОДЕЛИ ---")
print(f"Средняя абсолютная ошибка (MAE): {mae:,.0f} руб.")
print(f"Среднеквадратичная ошибка (RMSE): {rmse:,.0f} руб.")
print("Вывод: Модель в среднем ошибается на указанную сумму при прогнозировании рыночной стоимости.")

# 6. Важность признаков (Feature Importance)
print("6. Построение графика важности признаков...")
importances = model.feature_importances_
feature_names = X_encoded.columns

# Создаем DataFrame и сортируем по убыванию важности
feature_imp_df = pd.DataFrame({
    'Признак': feature_names,
    'Важность': importances
}).sort_values(by='Важность', ascending=False)

# Берем топ-10 самых важных признаков для красивого графика
top_features = feature_imp_df.head(10)

plt.figure(figsize=(10, 6))
sns.barplot(
    x='Важность',
    y='Признак',
    data=top_features,
    palette='Blues_r',
    edgecolor='black'
)
plt.title('Важность признаков для прогнозирования зарплаты (Топ-10)', fontsize=14, fontweight='bold')
plt.xlabel('Доля влияния на прогноз', fontsize=12)
plt.ylabel('Признак', fontsize=12)
plt.tight_layout()

# Сохраняем график в папку с проектом
plt.savefig('feature_importance.png', dpi=150)
print("График успешно сохранен как 'feature_importance.png'")
plt.show()