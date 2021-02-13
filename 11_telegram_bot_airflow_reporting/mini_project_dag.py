from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from datetime import datetime
import pandas as pd


# default arguments for airflow
default_args = {
    'owner': 'a.nikitin-8',
    'depends_on_past': False,
    'start_date': datetime(2021, 2, 11),
    'retries': 0
}

# creating DAG
dag = DAG('ad_report',
          default_args=default_args,
          catchup=False,
          schedule_interval='0 12 * * 1')  # is executed every Monday at 12:00 p.m.


# url to download data
url = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vR-ti6Su94955DZ4Tky8EbwifpgZf_dTjpBdiVH0Ukhsq94jZdqoHuUytZsFZKfwpXEUCKRFteJRc9P/pub?gid=889004448&single=true&output=csv'
df = pd.read_csv(url, parse_dates=['date', 'time'])


# calculating dataframe with all necessary metrics for reporting
def calc_metrics(df):
    # count views
    views = ( df.query('event == "view"') 
    .groupby(['date'], as_index=False) 
    .agg({'event': 'count'}) 
    .rename(columns={'event': 'views_count'}) )

    # count clicks
    clicks = ( df.query('event == "click"')
    .groupby(['date'], as_index=False)
    .agg({'event': 'count'})
    .rename(columns={'event': 'clicks_count'}) )
    # count ctr
    ctr = ( clicks.merge(views, on='date')
    .assign(ctr_percentage = round(100 * clicks.clicks_count / views.views_count, 2)) )

    # count money_spent
    result = ( df.drop_duplicates(subset=['date'], keep='first')
    .loc[: , ['date','ad_cost']]
    .merge(ctr, on='date') )
    result = result.assign(money_spent = (result.ad_cost / 1000) * result.views_count)

    # calc percentage difference between two dates 
    result['clicks_dif'] = round(result.clicks_count.pct_change() * 100, 2)
    result['views_dif'] = round(result.views_count.pct_change() * 100, 2)
    result['ctr_dif'] = round(result.ctr_percentage.pct_change() * 100, 2)
    result['money_spent_dif'] = round(result.money_spent.pct_change() * 100, 2)

    return result


# creating a report and writing it to a txt-file
def report(result):
    # creating variables for reporting
    date = result.date.astype('str')[0]
    ad_id = df.ad_id.iloc[0]
    money = round(result.money_spent[1], 2)
    money_dif = round(result.money_spent_dif[1], 2)
    views = round(result.views_count[1], 2)
    views_dif = round(result.views_dif[1], 2)
    clicks = round(result.clicks_count[1], 2)
    clicks_dif = round(result.clicks_dif[1], 2)
    ctr = round(result.ctr_percentage[1], 2)
    ctr_dif = round(result.ctr_dif[1], 2)

    # writing report to a file
    with open('report_{}.txt'.format(date), 'w') as rep:
        rep.write(
f'''Published ad_id {ad_id} report for {date}:
Expenditures: {money} RUB ({money_dif}%)
Views: {views} ({views_dif}%)
Clicks: {clicks} ({clicks_dif}%)
CTR: {ctr} ({ctr_dif}%)
''')
    return 'report_{}.txt'.format(date)


# sending file with the report via telegram bot
def send_via_tlgrm(file_name):
    import requests
    import json
    from urllib.parse import urlencode
    import os
    # reading token and chat_id from a file
    with open('ini.json') as src:  # here should be path to a file with your token and chat_id info!!!
        data = json.load(src)

    # @david8test_bot
    token = data['token']
    chat_id = data['chat_id']  # your chat id
    
    # sending message
    message = 'Please find attached a report:'  # text which you want to send
    params = {'chat_id': chat_id, 'text': message}
    base_url = f'https://api.telegram.org/bot{token}/'
    url = base_url + 'sendMessage?' + urlencode(params)  
    resp = requests.get(url)
    
    # getting current working directory and definging path to file
    cwd = os.getcwd()  
    filepath = cwd + '/' + file_name
    
    # sending a file with report
    url = base_url + 'sendDocument?' + urlencode(params)
    files = {'document': open(filepath, 'rb')}
    resp = requests.get(url, files=files)
    ## Now you'll receive a text message and the file with a report from your bot

    
# function to execute the script
def main():
    result = calc_metrics(df)
    filename = report(result)
    send_via_tlgrm(filename)


# task
t1 = PythonOperator(
    task_id='write_ad_report',
    python_callable=main,
    dag=dag)