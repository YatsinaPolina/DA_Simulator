from datetime import datetime, timedelta
import pandas as pd
from io import StringIO
import requests
from datetime import date
import pandahouse as ph

from airflow.decorators import dag, task
from airflow.operators.python import get_current_context



# Дефолтные параметры, которые прокидываются в таски
default_args = {
    'owner': 'p-golubeva-12',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2022, 11, 11),
}

# Интервал запуска DAG
schedule_interval = '* 08 * * *'

@dag(default_args=default_args, schedule_interval=schedule_interval, catchup=False)
def dag_golubeva_etl():

    @task()
    def extract_feed():
        query = """SELECT user_id,
                       countIf(action = 'view') as views, 
                       countIf(action = 'like') as likes,
                       os,
                                       multiIf(age <= 20, '0 - 20', 
                            age > 20 and age <= 30, '21-30',
                            age > 31 and age <= 40, '31-40', 
                            '41+') as age,
                       if(gender=1, 'male','female') as gender
                    FROM 
                        simulator_20221020.feed_actions 
                    where 
                        toDate(time) = yesterday()

                    group by user_id,
                    os,
                    gender,
                    age
                """
        df_cube = ph.read_clickhouse(query = query, connection=connection)
        return df_cube
    
    @task()
    def extract_message():
        query = """select t1.user_id, t1.messages_sent, t1.users_sent, t2.messages_received, t2.users_received from 
                    (SELECT user_id,
                                           count(reciever_id) as messages_sent, 
                                           count( distinct reciever_id) as users_sent 


                                        FROM 
                                            simulator_20221020.message_actions 
                                        where 
                                            toDate(time) = yesterday()

                                        group by user_id) t1
                    left join
                    (
                    SELECT reciever_id,
                                           count(user_id) as messages_received,
                                           count( distinct user_id) as users_received
                                        FROM 
                                            simulator_20221020.message_actions 
                                        where 
                                            toDate(time) = yesterday()

                                        group by reciever_id
                    ) t2
                      on user_id = reciever_id                     

                """
        df_cube = ph.read_clickhouse(query = query, connection=connection)
        return df_cube
    
    @task
    def transform_merge(df_cube1, df_cube2):
        df_merged = pd.merge(df_cube1, df_cube2, how="outer", on=["user_id"]).dropna()
        return df_merged
    
    @task
    def transform_os(df_merged):
        df_cube_os = df_merged[['os','views','likes','messages_sent', 'users_sent', 'messages_received', 'users_received']]\
            .groupby(['os'])\
            .sum()\
            .reset_index()
        yesterday = date.today() - timedelta(days = 1)
        df_cube_os.insert(0,'event_date', yesterday )
        df_cube_os.insert(1,'dimension', 'os' )
        df_cube_os.rename(columns={'os':'dimension_value'}, inplace=True)
        return df_cube_os
    
    @task
    def transform_gender(df_merged):
        df_cube_gender = df_merged[['gender','views','likes','messages_sent', 'users_sent', 'messages_received', 'users_received']]\
            .groupby(['gender'])\
            .sum()\
            .reset_index()
        yesterday = date.today() - timedelta(days = 1)
        df_cube_gender.insert(0,'event_date', yesterday )
        df_cube_gender.insert(1,'dimension', 'gender' )
        df_cube_gender.rename(columns={'gender':'dimension_value'}, inplace=True)
        return df_cube_gender
    
    @task
    def transform_age(df_merged):
        df_cube_age = df_merged[['age','views','likes','messages_sent', 'users_sent', 'messages_received', 'users_received']]\
            .groupby(['age'])\
            .sum()\
            .reset_index()
        yesterday = date.today() - timedelta(days = 1)
        df_cube_age.insert(0,'event_date', yesterday )
        df_cube_age.insert(1,'dimension', 'age' )
        df_cube_age.rename(columns={'age':'dimension_value'}, inplace=True)
        return df_cube_age
    
    @task
    def load(df_cube_os, df_cube_gender, df_cube_age):
        q = """
        create table if not exists test.GolubevaP
        (
            event_date Date,
            dimension VARCHAR,
            dimension_value VARCHAR,
            views UInt64,
            likes UInt64,
            messages_sent UInt64,
            users_sent UInt64,
            messages_received UInt64,
            users_received UInt64
        ) ENGINE = MergeTree()
        order by event_date
        """
        
        ph.execute(query=q, connection=connection_load)
        ph.to_clickhouse(df=df_cube_os, table='GolubevaP', index=False,connection=connection_load)
        ph.to_clickhouse(df=df_cube_gender, table='GolubevaP',index=False, connection=connection_load)
        ph.to_clickhouse(df=df_cube_age, table='GolubevaP',index=False, connection=connection_load)

    df_cube1 = extract_feed()
    df_cube2 = extract_message()
    df_merged = transform_merge(df_cube1, df_cube2)
    df_cube_os = transform_os(df_merged)
    df_cube_gender = transform_gender(df_merged)
    df_cube_age = transform_age(df_merged)
    load(df_cube_os, df_cube_gender, df_cube_age)
    
    
dag_golubeva_etl= dag_golubeva_etl()
