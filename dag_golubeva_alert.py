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
def dag_golubeva():

    @task()
    def extract_feed_yesterday():
        query = """SELECT toDate(time)  as Date,
                       countIf(action = 'view') as views, 
                       countIf(action = 'like') as likes,
                       (countIf(action = 'like')/countIf(action = 'view')) as CTR, 
                       count(distinct user_id) DAU
                    FROM 
                        simulator_20221020.feed_actions 
                    where 
                        toDate(time) = yesterday()

                    group by toDate(time)
                """
        df_cube = ph.read_clickhouse(query = query, connection=connection)
        return df_cube
    
    @task()
    def extract_feed_week():
        query = """SELECT toDate(time)  as Date,
                           countIf(action = 'view') as views, 
                           countIf(action = 'like') as likes,
                           (countIf(action = 'like')/countIf(action = 'view')) as CTR, 
                           count(distinct user_id) DAU
                        FROM 
                            simulator_20221020.feed_actions 
                        where 
                            toDate(time) between (today()-6) and today()

                        group by toDate(time)
                """
        df_cube = ph.read_clickhouse(query = query, connection=connection)
        return df_cube

    
    @task
    def transform_msg(df_cube):
        
        today = date.today()
        yesterday = today - timedelta(days = 1)
        msg = (f'Сводка по ключевым метрикам за {yesterday}:\n Views: {df_cube.at[0, "views"]}\n Likes: {df_cube.at[0, "likes"]}\n CTR: {round(df_cube.at[0, "CTR"],2)*100}%\n DAU: {df_cube.at[0, "DAU"]}')
        return msg
    
    @task
    def transform_plots(df):
        sns.set_theme()
        plt.figure(figsize=(10,12))
        plt.subplot(3, 1, 1)
        ax1 = sns.lineplot(data=df, x = df.loc[:,'Date'], y = df.loc[:,'likes'], marker='o', label= 'Likes')
        plt.subplot(3, 1, 1)
        ax1 = sns.lineplot(data=df, x = df.loc[:,'Date'], y = df.loc[:,'views'], marker='o', label = 'Views')
        plt.title('Views & Likes за неделю')
        plt.subplot(3, 1, 2)
        ax2 = sns.lineplot(data=df, x = df.loc[:,'Date'], y = df.loc[:,'DAU'], marker='o')
        plt.title('DAU за неделю')
        plt.subplot(3, 1, 3)
        ax3 = sns.lineplot(data=df, x = df.loc[:,'Date'], y = df.loc[:,'CTR'], marker='o')
        plt.title('CTR за неделю')
        ax1.set(ylabel=None)
        ax1.set(xlabel=None)
        ax2.set(ylabel=None)
        ax2.set(xlabel=None)
        ax3.set(ylabel=None)
        ax3.set(xlabel=None)
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
    
    df_cube1 = extract_feed_yesterday()
    df_cube2 = extract_feed_week()
    msg = transform_msg(df_cube1)
    plot =  transform_plots(df_cube2)
    load(msg, plot)
dag_golubeva = dag_golubeva()
    
        

    


