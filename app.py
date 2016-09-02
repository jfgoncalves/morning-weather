# -*- coding: utf-8 -*-

import os
import yaml
import requests
import arrow
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

def get_hourly_conditions(hourly_data, event):

    event = str(event.replace(minute= 0).timestamp)
    hours = next((hours for hours in hourly_data if hours['FCTTIME']['epoch'] == event), None)

    if hours is None:
        hourly_conditions = hours
    else:
        hourly_conditions = {
        'summary': hours['condition'],
        'icon': hours['icon'],
        'precipProbability': hours['pop'],
        'temperature': hours['temp']['metric'],
        'windSpeed': hours['wspd']['metric'],
        'windDirection': hours['wdir']['dir'],
        'cloudCover': hours['sky'],
        'uvIndex': hours['uvi']
        }

    return (hourly_conditions)

def get_data(forecast):

    sunphase = forecast['sun_phase']
    today_forecast = forecast['forecast']['simpleforecast']['forecastday'][0]

    location_data = {'timezone': forecast['current_observation']['local_tz_long']}

    now = arrow.utcnow().to(location_data['timezone'])
    location_data['todayDate'] = now

    print (location_data)

    today_conditions = {
    'sunrise': now.replace(hour= int(sunphase['sunrise']['hour']),minute= int(sunphase['sunrise']['minute']), second= 0, microsecond= 0, tzinfo= location_data['timezone']),
    'sunset': now.replace(hour= int(sunphase['sunset']['hour']),minute= int(sunphase['sunset']['minute']), second= 0, microsecond= 0, tzinfo= location_data['timezone']),
    'highestTemp': today_forecast['high']['celsius'],
    'lowestTemp': today_forecast['low']['celsius']
    }

    event_conditions = get_hourly_conditions(forecast['hourly_forecast'], today_conditions['sunrise'])
    return (location_data, today_conditions, event_conditions)

def parse_data(data):
    if data[2] is None:
        parsed_data = None
    else:
        parsed_data = {
        'timezone': data[0]['timezone'],
        'today': data[0]['todayDate'].format('D MMMM', locale='fr_fr'),
        'summary': data[2]['summary'],
        'sunrise': str(data[1]['sunrise'].hour)+"h"+str(data[1]['sunrise'].minute),
        'sunset': str(data[1]['sunset'].hour)+"h"+str(data[1]['sunset'].minute),
        'hTemp': data[1]['highestTemp'],
        'lTemp': data[1]['lowestTemp'],
        'icon': data[2]['icon'],
        'chanceOfRain': data[2]['precipProbability'],
        'temperature': data[2]['temperature'],
        'windSpeed': data[2]['windSpeed'],
        'windDirection': data[2]['windDirection'],
        'cloudCover': data[2]['cloudCover'],
        'UVIndex': data[2]['uvIndex']
        }
    return (parsed_data)


def get_iconfile(icon):
    if icon in ('clear', 'sunny'):
        filename = 'clear-day'
    elif icon in ('nt_clear', 'nt_sunny'):
        filename = 'clear-night'
    elif icon in ('rain', 'chancerain', 'nt_rain', 'nt_chancerain'):
        filename = 'rain'
    elif icon in ('snow', 'chancesnow', 'flurries', 'chanceflurries'):
        filename = 'snow-day'
    elif icon in ('nt_snow', 'nt_chancesnow', 'nt_flurries', 'nt_chanceflurries'):
        filename = 'snow-night'
    elif icon in ('mostlysunny', 'partlysunny', 'partlycloudy'):
        filename = 'partly-cloudy-day'
    elif icon in ('nt_mostlysunny', 'nt_partlysunny', 'nt_partlycloudy'):
        filename = 'partly-cloudy-night'
    elif icon in ('cloudy', 'mostlycloudy'):
        filename = 'cloudy'
    elif icon in ('nt_cloudy', 'nt_mostlycloudy'):
        filename = 'cloudy-night'
    elif icon in ('sleet', 'chancesleet', 'nt_sleet', 'nt_chancesleet'):
        filename = 'sleet'
    elif icon in ('tstorms', 'chancetstorms', 'nt_tstorms', 'nt_chancetstorms'):
        filename = 'thunderstorm'
    elif icon in ('fog', 'haze', 'nt_fog', 'nt_haze'):
        filename = 'fog'
    else:
        filename = 'notfound'
        print ("Error: unknown condition: '%s'" % icon)

    filename = filename + '.png'
    return (filename)

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
        today = parse_data(today)
        send_email(cfg, today)
