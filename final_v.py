from __future__ import absolute_import
from pyti.exponential_moving_average import exponential_moving_average as ema
from pyti.simple_moving_average import simple_moving_average as sma
import pandas as pd
import time
import dateparser
import pytz
import numpy as np
import argparse
from datetime import datetime
from binance.client import Client
from six.moves import range
import mplfinance as mpf
import matplotlib.dates as mdates
import os
import threading
import sys
from binance.exceptions import BinanceAPIException
from requests.exceptions import ConnectionError, ReadTimeout
from requests.packages.urllib3.exceptions import ProtocolError, ReadTimeoutError
import subprocess
import mplfinance as mpf
import numpy as np
from pyti import catch_errors
from pyti.function_helper import fill_for_noncomputable_vals
from mpl_finance import candlestick2_ochl as cd
import matplotlib.pyplot as plt


symbol = 'BTCUSDT'
api_key = "iZHsmlsCReb9S6zVO05Vxy8ONQYK8J3CfshgNiRh3HlRShPULMj8EYBClftHBqi1"
api_secret = "4IHk54oeSmmoXGQqWNgi24SJ1uHaTSEBfN48nOhYex8ATFFOj2WoWZQfDFD0pzu1"

client = Client(api_key, api_secret)
tz = pytz.timezone('UTC')


def date_to_milliseconds(date_str):
    """Convert UTC date to milliseconds
    If using offset strings add "UTC" to date string e.g. "now UTC", "11 hours ago UTC"
    :param date_str: date in readable format, i.e. "January 01, 2018", "11 hours ago UTC", "now UTC"
    :type date_str: str
    """
    epoch = datetime.utcfromtimestamp(0).replace(tzinfo=pytz.utc)
    d = dateparser.parse(date_str)
    if d.tzinfo is None or d.tzinfo.utcoffset(d) is None:
        d = d.replace(tzinfo=pytz.utc)
    return int((d - epoch).total_seconds() * 1000.0)


def interval_to_milliseconds(interval):
    """Convert a Binance interval string to milliseconds
    For clarification see document or mail d3dileep@gmail.com
    :param interval: Binance interval string 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w
    :type interval: str
    :return:
         None if unit not one of m, h, d or w
         None if string not in correct format
         int value of interval in milliseconds
    """
    ms = None
    seconds_per_unit = {
        "m": 60,
        "h": 60 * 60,
        "d": 24 * 60 * 60,
        "w": 7 * 24 * 60 * 60
    }

    unit = interval[-1]
    if unit in seconds_per_unit:
        try:
            ms = int(interval[:-1]) * seconds_per_unit[unit] * 1000
        except ValueError:
            pass
    return ms


def get_historical_klines(symbol, interval, start_str, end_str=None):
    """Get Historical Klines from Binance
    If using offset strings for dates add "UTC" to date string e.g. "now UTC", "11 hours ago UTC", "1 Dec, 2017"
    :param symbol: Name of symbol pair e.g BNBBTC
    :param interval: Biannce Kline interval
    :param start_str: Start date string in UTC format
    :param end_str: optional - end date string in UTC format
    :return: list of Open High Low Close Volume values
    """
    output_data = []
    limit = 50
    timeframe = interval_to_milliseconds(interval)
    start_ts = date_to_milliseconds(start_str)
    end_ts = None
    if end_str:
        end_ts = date_to_milliseconds(end_str)

    idx = 0
    # it can be difficult to know when a symbol was listed on Binance so allow start time to be before list date
    symbol_existed = False
    while True:
        temp_data = client.get_klines(
            symbol=symbol,
            interval=interval,
            limit=limit,
            startTime=start_ts,
            endTime=end_ts
        )
        # handle the case where our start date is before the symbol pair listed on Binance
        if not symbol_existed and len(temp_data):
            symbol_existed = True
        if symbol_existed:
            output_data += temp_data
            start_ts = temp_data[len(temp_data) - 1][0] + timeframe
        else:
            start_ts += timeframe
        idx += 1
        if len(temp_data) < limit:
            break
        # sleep after every 3rd call to be kind to the API
        if idx % 3 == 0:
            time.sleep(1)

    return output_data


def get_historic_klines(symbol, start, end, interval):
    klines = get_historical_klines(symbol, interval, start, end)
    ochl = []
    for kline in klines:
        time1 = int(kline[0])
        open1 = float(kline[1])
        high = float(kline[2])
        low = float(kline[3])
        close = float(kline[4])
        volume = float(kline[5])
        ochl.append([time1, open1, close, high, low, volume])
    '''
    fig, ax = plt.subplots()
    mpl_finance.candlestick_ochl(ax, ochl, width=1)
    ax.set(xlabel='Date', ylabel='Price', title='{} {}-{}'.format(symbol, start, end))
    plt.show(block=False)
    plt.pause(3)
    plt.close()
    '''
    close = [row[4] for row in ochl]
    return close[-500:]


def percent_k(data, period):
    """
    %K.
    Formula:
    %k = data(t) - low(n) / (high(n) - low(n))
    """
    percent_k = [((data['Close'][idx] - np.min(data['Low'][idx + 1 - period:idx + 1])) / (np.max(data['High'][idx + 1 - period:idx + 1]) -np.min(data['Low'][idx + 1 - period:idx + 1]))) for idx in range(period - 1, len(data['Close']))]
    percent_k = fill_for_noncomputable_vals(data['Close'], percent_k)
    return percent_k


def percent_d(data, period):
    """
    %D.
    Formula:
    %D = SMA(%K, 3)
    """
    p_k = percent_k(data, period)
    percent_d = ema(p_k, 15)
    return percent_d

def get_percentd(symbol):
  data = get_historic_klines_stoch(symbol, "2days ago UTC", "now UTC", Client.KLINE_INTERVAL_5MINUTE)
  percent_d1 = percent_d(data, 50)[-500:]
  percent_k1 = percent_k(data, 50)[-500:]
  return percent_d1

def get_historic_klines_ochl(symbol, start, end, interval):
    klines = get_historical_klines(symbol, interval, start, end)
    ochl = []
    for kline in klines:
        time1 = int(kline[0])
        open1 = float(kline[1])
        high = float(kline[2])
        low = float(kline[3])
        close = float(kline[4])
        volume = float(kline[5])
        ochl.append([time1, open1, close, high, low, volume])
    '''
    fig, ax = plt.subplots()
    mpl_finance.candlestick_ochl(ax, ochl, width=1)
    ax.set(xlabel='Date', ylabel='Price', title='{} {}-{}'.format(symbol, start, end))
    plt.show(block=False)
    plt.pause(3)
    plt.close()
    '''

    return ochl[-500:]


def get_historic_klines_stochastic(symbol, start, end, interval):
    klines = get_historical_klines(symbol, interval, start, end)
    ochl = []
    for kline in klines:
        time1 = int(kline[0])
        open1 = float(kline[1])
        low = float(kline[2])
        high = float(kline[3])
        close = float(kline[4])
        volume = float(kline[5])
        ochl.append([time1, open1, close, high, low, volume])
    print(len(ochl))
    # fig, ax = plt.subplots(figsize=(10,5))
    # mpl_finance.candlestick_ochl(ax, ochl, width=1)
    # ax.set(xlabel='Date', ylabel='Price', title='{} {}-{}'.format(symbol, start, end))
    # plt.show()

    df= pd.DataFrame(ochl, columns=['time', 'Open', 'Close', 'High', 'Low', 'Volume'])

    df['L14'] = df['Low'].rolling(window=14).min()

    df['H14'] = df['High'].rolling(window=14).max()

    df['%K'] = 100*((df['Close'] - df['L14']) / (df['H14'] - df['L14']) )

    df['%D'] = df['%K'].rolling(window=3).mean()

    return df


def decision(hist,stochastic,data):
    print(hist[-1])

    if hist[-1] > 0:
        print("buy at " +  str(data[-1]))


    elif stochastic>0 and len(data)>0:
        print("sell at " + str(data[-1]))
        data.pop()

    else:
        print("hold")



if __name__ == '__main__':
    cn = 0
    data = []

    while cn<100:
        close = get_historic_klines(symbol, "2 days ago UTC", "now UTC", Client.KLINE_INTERVAL_5MINUTE)
        ochl = get_historic_klines_ochl(symbol, "2 days ago UTC", "now UTC", Client.KLINE_INTERVAL_5MINUTE)
        source = close
        data.append(source[-1])
        fastLength = 12
        slowLength = 26  # take from binance
        signalLength = 9

        fastMA = ema(source, fastLength)
        slowMA = ema(source, slowLength)

        macd = fastMA - slowMA
        signal = sma(macd, signalLength)
        hist = macd - signal

        stochastic_data = get_historic_klines_stochastic(symbol,"20 days ago UTC","now UTC",Client.KLINE_INTERVAL_1DAY)
        stochastic_li = stochastic_data['%K'].tolist()
        decision(hist,stochastic_li,source)
        cn += 1;






        


    

    #decision(macdo,signalo)
    



    """
    final = histo.join(macdo, lsuffix='_left', rsuffix='_right')
    final = final.join(signalo, lsuffix='_left', rsuffix='_right')

    fig, (ax1, ax2, ax3) = plt.subplots(3, figsize=(20, 20))

    p = get_percentd(symbol)
    ax2.plot(range(0, len(p)), p * 100)
    # plt.plot(range(0, len(percent_d1)),percent_k1)


    final['0_left'].plot(kind='bar', width=2, color=(final['0_left'] > 0).map({True: 'g', False: 'r'}))
    final['0_right'].plot(kind='line', linewidth=2, color='m')
    final[0].plot(kind='line', linewidth=2, color='b')
    #
    # # ax1 = sns.barplot(data=histo, palette='summer')
    # # ax1 = sns.barplot(data=histo, palette='summer')

    # # ax2 = ax1.twinx()
    # # ax2 = sns.lineplot(data=macdo, sort=False, color='blue')


    data = pd.DataFrame(ochl, columns=['Date', 'Open', 'Close', 'High', 'Low', 'Volume'])
    data['Date'] = pd.to_datetime(data['Date'], unit='ms')
    data['Date'] = pd.DatetimeIndex(data['Date'])
    data = data.set_index(data['Date'])

    data = data[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]

    cd(ax1, data['Open'], data['Close'], data['High'], data['Low'], width=4, colorup='g', colordown='r', alpha=0.75)



    plt.legend(['macd', 'signal'])
    fig.suptitle(symbol)
    plt.show()
    """
