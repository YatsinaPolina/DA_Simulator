# DA_Simulator
В данном репозитории содержатся проекты с курса **"Симулятор Аналитика"** от **karpov.courses**.

## AA_test_split.ipynb
Проведена симуляция 10000 АА-тестов. На каждой итерации сформирована подвыборка без повторения в 500 юзеров из 2 и 3 экспериментальной группы. Проведено сравнение этих подвыборок t-testом. Построена гистограмма распределения получившихся 10000 p-values. Приведен вывод по результатам АА-теста.

## AB_test_CTR.ipynb
Проведен AB тест. В группе 2 был использован один из новых алгоритмов рекомендации постов, группа 1 использовалась в качестве контроля. 
Для сравнения CTR в двух группах были использованы: 
* t-тест
* Пуассоновский бутстреп 
* тест Манна-Уитни
* t-тест на сглаженном ctr (α=5) 
* t-тест и тест Манна-Уитни поверх бакетного преобразования

## AB_test_linearized_likes.ipynb
В AB тесте используется метрика линеаризованных лайков.

## Golubeva_DAG.py
Представлен вариант ETL задачи, на выходе которой формируется DAG в airflow, который будет считаться каждый день за вчера. 

* Параллельно обрабатываются две таблицы, каждая выгрузка в отдельном таске
* Обе таблицы объединяются в одну
* Считаем мтерики в различных разрезах (пол, возраст и тд)
* Финальные данные со всеми метриками записывАЮТСЯ в отдельную таблицу в ClickHouse
* Каждый день таблица дополняется новыми данными

## Golubeva_feed_alert.py
Автоматизация отчетности. В отчете следующие ключевые метрики: 
* DAU 
* Просмотры
* Лайки
* CTR

А так же их графики.
Сводка за предыдущий день приходит ежедневно в 11:00 в чат телеграмма.
DAG так же запускается в Apache Airflow.

## Golubeva_app_report.py
Автоматизация отчетности. Расширенный отчет для двух сервисов, метрики:
* DAU
* Новые пользователи
* Разбиение трафика (organic, ads)
* Число новых постов

А так же графики средней активности, активности по сервисам и динамика аудитории по неделям(new, gone, retained).
Сводка за предыдущий день приходит ежедневно в 11:00 в чат телеграмма.
DAG запускается в Apache Airflow.

## Golubeva_anomaly_alert.py
Система алертов которая с периодичностью каждые 15 минут проверяет ключевые метрики, такие как активные пользователи в ленте / мессенджере, просмотры, лайки, CTR, количество отправленных сообщений. Методом для детектирования аномалий выбран Межквартильный размах.
DAG запускается в Apache Airflow.

