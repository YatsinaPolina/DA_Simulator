import telegram
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import pandas as pd
import requests
from datetime import date
import pandahouse as ph
import io

from airflow.decorators import dag, task
from airflow.operators.python import get_current_context

#Коннекшн для выгрузки
connection = {
    'host': 'https://clickhouse.lab.karpov.courses',
    'password': 'dpo_python_2020',
    'user': 'student',
    'database': 'simulator_20221020'
}
# Дефолтные параметры, которые прокидываются в таски
default_args = {
    'owner': 'p-golubeva-12',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2022, 11, 13),
}

# Интервал запуска DAG
schedule_interval = '0 11 * * *'

@dag(default_args=default_args, schedule_interval=schedule_interval, catchup=False)
def dag_golubeva_app():

    @task()
    def extract_for_text():
    #общее число пользователей
        q_total = '''SELECT count(distinct user_id) as total
                                        FROM  simulator_20221020.feed_actions t1
                                        left join simulator_20221020.message_actions t2 on t1.user_id=t2.user_id
                                        WHERE toDate(time) = toDate(today() - 1)  '''

        #новые уникальные пользователи приложения за вчера
        q_new = '''SELECT COUNT(user_id) as new FROM 
                                        (SELECT user_id, MIN(toDate(time)) AS start_date
                                        FROM simulator_20221020.feed_actions t1
                                        left join simulator_20221020.message_actions t2 on t1.user_id=t2.user_id
                                        GROUP BY user_id
                                        HAVING start_date = yesterday())
                                        '''
        #новые посты за вчера
        q_post = '''SELECT COUNT(post_id) as post FROM
                                        (SELECT post_id, MIN(toDate(time)) AS create_date
                                        FROM simulator_20221020.feed_actions
                                        GROUP BY post_id
                                        HAVING create_date = yesterday())'''

        q_source = '''SELECT countIf(source = 'ads') as ads, 
                               countIf(source = 'organic') as organic  FROM
                                        (SELECT user_id, source, MIN(toDate(time)) AS start_date
                                        FROM simulator_20221020.feed_actions t1
                                        left join simulator_20221020.message_actions t2 on t1.user_id=t2.user_id
                                        GROUP BY user_id, source
                                        HAVING start_date = yesterday())     '''                                    


        df_total = ph.read_clickhouse(q_total, connection=connection)
        df_new = ph.read_clickhouse(q_new, connection=connection)
        df_source = ph.read_clickhouse(q_source, connection=connection)
        df_post = ph.read_clickhouse(q_post, connection=connection)
        today = date.today()
        yesterday = today - timedelta(days = 1)
        msg = (f'Доброе утро! Основные показатели приложения за {yesterday} ниже:\n \nОбщее число активных пользователей: {df_total.at[0, "total"]}\n \nНовые пользователи приложения: {df_new.at[0, "new"]}\n \nРазбиение по каналам привлечения:\n  ADS: {df_source.at[0, "ads"]}\n  Organic: {df_source.at[0, "organic"]}\n \nНовых постов: {df_post.at[0, "post"]}')

        return msg

    @task
    def extract_for_plot():
        #Средняя активность пользователей за две недели
        q_avg = '''SELECT Date, AVG(views) AS avg_views, AVG(likes) AS avg_likes
                                FROM (
                                    SELECT toDate(time) AS Date, countIf(action = 'view') as views, countIf(action = 'like') as likes, user_id
                                    FROM simulator_20221020.feed_actions
                                    GROUP BY user_id, toDate(time)
                                    )
                                GROUP BY Date
                                HAVING Date <= yesterday() and Date > yesterday()-14'''
        #Ретеншн по неделям
        q_ret = '''SELECT toDate(this_week) AS Date,
                               status AS status,
                               AVG(num_users) AS "AVG(num_users)"
                        FROM
                          (SELECT this_week,
                                  previous_week, -uniq(user_id) as num_users,
                                                  status
                           FROM
                             (SELECT user_id,
                                     groupUniqArray(toMonday(toDate(time))) as weeks_visited,
                                     addWeeks(arrayJoin(weeks_visited), +1) this_week,
                                     if(has(weeks_visited, this_week) = 1, 'retained', 'gone') as status,
                                     addWeeks(this_week, -1) as previous_week
                              FROM simulator_20221020.feed_actions
                              group by user_id)
                           where status = 'gone'
                           group by this_week,
                                    previous_week,
                                    status
                           HAVING this_week != addWeeks(toMonday(today()), +1)
                           union all SELECT this_week,
                                            previous_week,
                                            toInt64(uniq(user_id)) as num_users,
                                            status
                           FROM
                             (SELECT user_id,
                                     groupUniqArray(toMonday(toDate(time))) as weeks_visited,
                                     arrayJoin(weeks_visited) this_week,
                                     if(has(weeks_visited, addWeeks(this_week, -1)) = 1, 'retained', 'new') as status,
                                     addWeeks(this_week, -1) as previous_week
                              FROM simulator_20221020.feed_actions
                              group by user_id)
                           group by this_week,
                                    previous_week,
                                    status) AS virtual_table
                        GROUP BY status,
                                 toDate(this_week)
                        ORDER BY "AVG(num_users)" DESC'''

        #Активность пользователей в течении дня 
        q_act = '''SELECT toStartOfHour(time) as time,
                             uniq(user_id) AS users,
                            'feed' AS service
                        FROM simulator_20221020.feed_actions
                        WHERE toDate(time) = yesterday()
                        GROUP BY time
                        ORDER BY time

                        UNION ALL 

                        SELECT toStartOfHour(time) as time,
                             uniq(user_id) AS users,
                            'message' AS service
                        FROM simulator_20221020.message_actions
                        WHERE toDate(time) = yesterday()
                        GROUP BY time
                        ORDER BY time'''

        df_avg = ph.read_clickhouse(q_avg, connection=connection)
        df_ret = ph.read_clickhouse(q_ret, connection=connection)
        df_act = ph.read_clickhouse(q_act, connection=connection)
        df_act['time'] = df_act['time'].dt.hour
        df1 = df_ret.loc[df_ret['status'] == 'gone']
        df1 = df1.rename(columns={"AVG(num_users)": "gone"})
        df2 = df_ret.loc[df_ret['status'] == 'retained']
        df2 = df2.rename(columns={"AVG(num_users)": "retained"})
        df3 = df_ret.loc[df_ret['status'] == 'new']
        df3 = df3.rename(columns={"AVG(num_users)": "new"})
        result = pd.merge(df1, df2, on="Date")
        final =  pd.merge(result, df3, on="Date")
        final = final.drop(['status_x', 'status_y', 'status'], axis=1)
        final['Date'] = pd.to_datetime(final['Date']).dt.date

        sns.set_theme()
        fig = plt.figure(figsize=(10, 12))
        ax1 = plt.subplot(3, 1, 1)
        ax2 = plt.subplot(3, 1, 1)
        ax3 = plt.subplot(3, 1, 2)
        ax4 = plt.subplot(3, 1, 3)

        sns.lineplot(data=df_avg, x = df_avg.loc[:,'Date'], y = df_avg.loc[:,'avg_likes'], marker='o', label= 'Average Likes', ax=ax1)
        sns.lineplot(data=df_avg, x = df_avg.loc[:,'Date'], y = df_avg.loc[:,'avg_views'], marker='o', label = 'Average Views', ax=ax2)
        sns.lineplot(data=df_act, x='time', y='users',  hue='service',  ax=ax3,  marker='o')
        final.set_index('Date').plot(kind='bar', stacked=True, ax = ax4)
        ax1.set_xlabel('')
        ax1.set_ylabel('')
        ax1.title.set_text('Средняя активность пользователей за 14 дней')
        ax3.set_xlabel('')
        ax3.set_ylabel('')
        ax3.title.set_text('Активность пользователей по сервисам за вчерашний день')
        ax4.set_xlabel('')
        ax4.set_ylabel('')
        ax4.title.set_text('Аудитория по неделям')
        fig.tight_layout(pad=3.0)
        plot_object = io.BytesIO()
        plt.savefig(plot_object) 
        plot_object.seek(0)
        plot_object.name = 'report_plot.png'
        plt.close()
        return plot_object


    @task
    def load(msg, plot, chat = None):
        chat_id = chat or -817148946
        my_token='5779793401:AAHJCsf63siz7R0_e6D-aGL0CHnmTlsZxyQ'
        bot = telegram.Bot(token=my_token)
        bot.sendMessage(chat_id=chat_id, text = msg)
        bot.sendPhoto(chat_id=chat_id, photo = plot)
        return
    
    msg = extract_for_text()
    plot = extract_for_plot()
    load(msg, plot)
dag_golubeva_app = dag_golubeva_app()
    
        

    


