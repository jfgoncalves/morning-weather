# -*- coding: utf-8 -*-

import os
import yaml
import requests
import arrow
from multi_key_dict import multi_key_dict
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

cwd = os.getcwd()

# Load config

with open(cwd+'/config.yml', 'r') as ymlfile:
    cfg = yaml.load(ymlfile)

# The magic starts here

def get_forecast(key, pws, lang):
    baseURL = 'https://api.wunderground.com/api/'
    rqURL = baseURL+key+'/astronomy/forecast/conditions/hourly/lang:'+lang+'/q/pws:'+pws+'.json'
    rq = requests.get(rqURL)
    status = rq.status_code

    if status == 200:
        forecast = rq.json()
        return (forecast)
    else:
        return (None)

def get_hourly_conditions(hourly_data, sunrise):

    morningConditions = next((hours for hours in hourly_data if hours['FCTTIME']['hour'] == sunrise), None)
    return (morningConditions)

def get_data(forecast):

    sunphase = forecast['sun_phase']
    todayForecast = forecast['forecast']['simpleforecast']['forecastday'][0]
    tz = forecast['current_observation']['local_tz_long']

    morningConditions = get_hourly_conditions(forecast['hourly_forecast'], sunphase['sunrise']['hour'])
    now = arrow.get(morningConditions['FCTTIME']['epoch']).to(tz)

    if morningConditions is None:
        return (None)
    else:
        todayConditions = {
        'today': now.format('D MMMM', locale='fr_fr'),
        'summary': morningConditions['condition'],
        'sunrise': sunphase['sunrise']['hour']+'h'+sunphase['sunrise']['minute'],
        'sunset': sunphase['sunset']['hour']+'h'+sunphase['sunset']['minute'],
        'hTemp': todayForecast['high']['celsius'],
        'lTemp': todayForecast['low']['celsius'],
        'icon': morningConditions['icon'],
        'chanceOfRain': morningConditions['pop'],
        'temperature': morningConditions['temp']['metric'],
        'windSpeed': morningConditions['wspd']['metric'],
        'windDirection': morningConditions['wdir']['dir'],
        'cloudCover': morningConditions['sky'],
        'UVIndex': morningConditions['uvi']
        }
        return (todayConditions)

def get_iconfile(icon):

    icons = multi_key_dict()
    icons['clear', 'sunny'] = 'clear-day'
    icons['nt_clear', 'nt_sunny'] = 'clear-night'
    icons['rain', 'chancerain', 'nt_rain', 'nt_chancerain'] = 'rain'
    icons['snow', 'chancesnow', 'flurries', 'chanceflurries'] = 'snow-day'
    icons['nt_snow', 'nt_chancesnow', 'nt_flurries', 'nt_chanceflurries'] = 'snow-night'
    icons['mostlysunny', 'partlysunny', 'partlycloudy'] = 'partly-cloudy-day'
    icons['nt_mostlysunny', 'nt_partlysunny', 'nt_partlycloudy'] = 'partly-cloudy-night'
    icons['cloudy', 'mostlycloudy'] = 'cloudy'
    icons['nt_cloudy', 'nt_mostlycloudy'] = 'cloudy-night'
    icons['sleet', 'chancesleet', 'nt_sleet', 'nt_chancesleet'] = 'sleet'
    icons['tstorms', 'chancetstorms', 'nt_tstorms', 'nt_chancetstorms'] = 'thunderstorm'
    icons['fog', 'haze', 'nt_fog', 'nt_haze'] = 'fog'

    filename = icons.get(icon, None)
    if filename is None:
        print ("Error: Filename not found. Unknown weather condition: '%s'" % icon)
        return ('notfound.png')
    else:
        return (filename+'.png')

def send_email(credentials, data):
    if data is None:
        print ('Data unavailable.')
    else:
        fromaddr = credentials['email']['from']
        toaddr = credentials['email']['to']

        msg = MIMEMultipart()

        msg['From'] = fromaddr
        msg['To'] = toaddr
        msg['Subject'] = "Météo du {today}".format(**data)

        body = "{summary}. Le soleil se lèvera à {sunrise} et il fera {temperature}°C. Le vent soufflera à {windSpeed} km/h {windDirection}, le risque de pluie sera de {chanceOfRain}%, l'indice UV sera de {UVIndex} et la couverture nuageuse sera de {cloudCover}%. Pour la journée, la maximale sera de {hTemp}°C et la minimale de {lTemp}°C. Le soleil se couchera à {sunset}.".format(**data)

        msg.attach(MIMEText(body, 'plain'))

        filename = get_iconfile(data['icon'])
        attachment = open(cwd+'/assets/'+filename, 'rb')

        part = MIMEBase('application', 'octet-stream')
        part.set_payload((attachment).read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename= %s' % filename)

        msg.attach(part)

        server = smtplib.SMTP(credentials['email']['smtp'], credentials['email']['port'])
        server.starttls()
        server.login(fromaddr, credentials['email']['pwd'])
        text = msg.as_string()
        server.sendmail(fromaddr, toaddr, text)
        server.quit()

if __name__ == "__main__":
    forecast = get_forecast(cfg['wunderground']['key'], cfg['wunderground']['pws'], cfg['wunderground']['lang'])
    if forecast is None:
        print ('Weather Underground API unavailable.')
    else:
        today = get_data(forecast)
        send_email(cfg, today)
