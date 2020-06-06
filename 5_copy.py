import pandas as pd
import time
import dateparser
import pytz
import argparse
from datetime import datetime
from binance.client import Client
import os
from binance.exceptions import BinanceAPIException
from requests.exceptions import ConnectionError, ReadTimeout
from requests.packages.urllib3.exceptions import ProtocolError, ReadTimeoutError
import telebot
import decimal
import math

# import matplotlib.pyplot as plt
# import mpl_finance

api_key = "MEHTryQXxTsL8SuDZRS60JEaNkcgAg0wbC0mjSANHin9Pqto8TV9eMhn7A"
api_secret = "RGlxAH8Pr3japFlpuTEN5cwo7btBE3nPPOJvIgiP55EpKXeVdeDxvWF"

client = Client(api_key, api_secret)
tz = pytz.timezone('UTC')
buy = {}
loss = []
quantity = {}


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
    return ochl[-1][1], ochl[-1][2]

def format_e(n):
    a = '%E' % n
    print(a[-1])
    return a.split('E')[0].rstrip('0').rstrip('.') + 'E' + a.split('E')[1]

def floatPrecision(f, n):
    n = int(math.log10(1 / float(n)))
    f = math.floor(float(f) * 10 ** n) / 10 ** n
    f = "{:0.0{}f}".format(float(f), n)
    return str(int(f)) if int(n) == 0 else f

def Main():
    list_of_symbols = ['MATICUSDT']  # Symbols to be traded
    quantity_1 = 1  # any value between 1-4 : 1 =100%, 2=50%, 3 = 33%, 4 = 25%, 5 = 20% and so on...
    max_amount = 19  # Maximum authorized amount
    loss_limit = -25  # Maximum loss limit to terminate the trading in dollar
    buy_percent = 0.0005  # percent at which it should buy, currently 0.1% = 0.1/100 = 0.001
    sell_percent = 0.0029  # percent at which it should sell, currently 0.1%
    loss_percent = -0.0032  # stop loss if price falls, currently -0.3%
    transaction = 50  # number of maximum transactions
    buy_range = 0.0008  # allowed buy upto, currently 0.4%
    sleep_time = 4  # according to candle interval 15 for 5 MINUTE, 30 for 30 MINUTE, 45 for 1 HOUR
    spent_amount = 0
    count = 0
    count1 = 0
    buy_open = []  # to avoid buying at same candle
    bot = telebot.TeleBot("1266234270:AAGJVnSx6rYp1NDa_szOOoMyoA_6rqeqSZQ")

    bot.send_message(chat_id='-433229420', text='➤ START TRADING 5 MINUTE')
    while True:

        try:
            client.get_deposit_address(asset='USDT')  # USDT or BTC
            '''
            client.order_market_sell(
                       symbol='ZILUSDT',
                       quantity='1503.20000000')
            '''
            for symbol in list_of_symbols:

                open1, close = get_historic_klines(symbol, "1 hours ago UTC", "now UTC", Client.KLINE_INTERVAL_5MINUTE)

                step_size = float(next(filter(lambda f: f['filterType'] == 'LOT_SIZE', client.get_symbol_info(symbol)['filters']))['stepSize'])

                symbol = str(symbol)
                if open1 not in buy_open and count < transaction:
                    if (close >= (1 + buy_percent) * open1) and (symbol not in buy.keys()) and close < (
                            1 + buy_range) * open1:
                        #    print('hey')
                        if spent_amount <= (0.97 * max_amount):
                            count += 1
                            #step_size = float(next(filter(lambda f: f['filterType'] == 'LOT_SIZE', client.get_symbol_info(symbol)['filters']))['stepSize'])
                        
                            quantity[symbol] = floatPrecision((max_amount / (quantity_1 * close)),step_size )#abs(decimal.Decimal(step_size).as_tuple().exponent))
                            #print(quantity[symbol])
                            quantity1 = float(quantity[symbol])
                            #print(quantity1)
                            buy_open.append(open1)
                            '''
                            client.order_market_buy(
                                     symbol=symbol,
                                     quantity=quantity[symbol]
                                     )
                            '''
                            close1 = float(client.get_symbol_ticker(symbol = symbol)['price'])
                            spent_amount += close1 * (quantity1)
                            buy[symbol] = close1
                            bot.send_message(chat_id='-433229420', text='(➕) ACHAT De → ' + symbol + ' a ' + str(close1))
                            print('(➕) ACHAT De → ' + symbol + ' a ' + str(close))

                            df1 = pd.DataFrame({'Datetime': [datetime.now(tz)], 'Symbol': [symbol], 'Buy/Sell': ['Buy'],
                                                'Quantity': [quantity1], 'Price': [close1], 'Profit/loss': [0]})
                            df1['Datetime'] = df1['Datetime'].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'))
                            if not os.path.isfile('5result.csv'):
                                df1.to_csv('5result.csv', index=False)
                            else:
                                df1.to_csv('5result.csv', index=False, mode='a', header=False)

                if symbol in buy and count1 < transaction:
                    #print('hello')
                    if (close >= buy[symbol] * (1 + sell_percent)) or (close <= (1 + loss_percent) * buy[symbol]):
                        count1 +=1
                        '''
                        client.order_market_sell(
                                symbol=symbol,
                                quantity=floatPrecision(0.999 * float(quantity[symbol]),step_size))
                        '''
                        close2 = float(client.get_symbol_ticker(symbol = symbol)['price'])
                        profit = close2 - buy[symbol]

                        quantity1 = quantity[symbol]
                        spent_amount -= float(quantity1) * buy[symbol]
                        total_profit = round(profit * quantity1,2)
                        bot.send_message(chat_id='-433229420', text="(➖) VENTE De ➜ " + symbol + " a " + str(close2) )
						bot.send_message(chat_id='-433229420', text= "➤ Bénéfice Réalisé ➥ " + str(total_profit) + " USD $")
                        bot.send_message(chat_id='-420347911', text= "➤ Bénéfice Réalisé ➥ " + str(total_profit) + " USD $")
                        print("(➖) VENTE De ➜ " + symbol + " a " + str(close2) +
                                "➤ Bénéfice Réalisé ➥ " + str(total_profit) + " USD $")
                        df2 = pd.DataFrame({'Datetime': [datetime.now(tz)], 'Symbol': [symbol], 'Buy/Sell': ['Sell'],
                                            'Quantity': [quantity1], 'Price': [close2], 'Profit/loss': [total_profit]})
                        df2['Datetime'] = df2['Datetime'].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'))
                        df2.to_csv('5result.csv', index=False, mode='a', header=False)
                        max_amount += total_profit
                        loss.append(total_profit)
            
                        buy.pop(symbol)  # Removing the sold symbol

                if (loss_limit > sum(loss)) or (count1 >= int(transaction)):
                    bot.send_message(chat_id='-433229420', text="FIN DE TRADING")
                    raise SystemExit

                time.sleep(sleep_time)

        except BinanceAPIException as e:
            print(e, symbol)
            continue
        except ConnectionError or ProtocolError or ReadTimeoutError or ReadTimeout as e1:
            continue
        except KeyboardInterrupt:
            print(" ➣ Total ➥ " + str(round(sum(loss),2)) + "$")
            break

        except SystemExit:
            print("Exit")
            print(" ➣ Total ➥ " + str(round(sum(loss),2)) + "$")
            break


if __name__ == "__main__":
    Main()
