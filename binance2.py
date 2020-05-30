import lxml.html as lh
import time
import urllib.request
import argparse
import urllib.request, urllib.parse, urllib.error
import datetime
import logging
import pytz
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
import os
import coloredlogs
import json
import ssl
from docopt import docopt
from trading_bot.ops import get_state
from trading_bot.agent import Agent
from trading_bot.methods import evaluate_model
from trading_bot.utils import (
    get_stock_data,
    format_currency,
    format_position,
    show_eval_result,
    switch_k_backend_device
)
from binance.client import Client
import warnings
from quick_train import quick_train
import decimal
import math
import pandas as pd
tz = pytz.timezone('Asia/Kolkata')



api_key = "JB80jU6aTMYXcLapXKPc2Rmnn12CUcm3l7RlnYAT7w8esCFAKYOTmd4bAMWxB33U"
api_secret = "FsbKTSb7lCGLpQWoBad9Jobe8xpi177c2KrQ6Q31e86dUA5WgUqaliqHsILk7n5s"
client = Client(api_key, api_secret)
client.get_deposit_address(asset='USDT')



def Real(cur_symbol):
    live = float(client.get_symbol_ticker(symbol = cur_symbol)['price']);
    time.sleep(1)
    return live

def floatPrecision(f, n):
    n = int(math.log10(1 / float(n)))
    f = math.floor(float(f) * 10 ** n) / 10 ** n
    f = "{:0.0{}f}".format(float(f), n)
    return str(int(f)) if int(n) == 0 else f

def main(args):
    price = []

    cur_symbol = args.ticker

    quick_train(cur_symbol)
    window_size =10
    time_now = datetime.datetime.now(tz).time()

    for c in range(2):
        price.append(Real(cur_symbol))

    model_name='model_double-dqn_GOOG_50_50'

    initial_offset = price[1] - price[0]

    agent = Agent(window_size, pretrained=True, model_name=model_name)
    profit, history = evaluate_model(agent, price, window_size,cur_symbol, debug=False)
    show_eval_result(model_name, profit, initial_offset)
    print("Profit:", profit)
    buys = sells = holds = 0
    for i in history:
        if i[1] == "BUY":
            buys += 1
        elif i[1] == "SELL":
            sells += 1
        elif i[1] == "HOLD":
            holds += 1
    print("BUYS Percentage:", (buys/len(history)) * 100)
    print("SELLS Percentage:", (sells/len(history)) * 100)
    print("HOLDS Percentage:", (holds/len(history)) * 100)
    rpath = 'training_data/' + cur_symbol + '.csv'
    os.remove(rpath)

#--------------------------------------------------------------
    

def evaluate_model(agent, price, window_size, cur_symbol, debug):
    quantity_1 = 1  # any value between 1-4 : 1 =100%, 2=50%, 3 = 33%, 4 = 25%, 5 = 20% and so on...
    max_amount = 19  # Maximum authorized amount
    loss_limit = -25  # Maximum loss limit to terminate the trading in dollar
    buy_percent = 0.0005  # percent at which it should buy, currently 0.1% = 0.1/100 = 0.001
    sell_percent = 0.0029  # percent at which it should sell, currently 0.1%
    loss_percent = -0.0032  # stop loss if price falls, currently -0.3%
    transaction = 50  # number of maximum transactions
    buy_range = 0.0008  # allowed buy upto, currently 0.4%
    total_profit = 0
    spent_amount = 0
    loss = []
    quantity = {}

    buy_limit = 40
    num_buys = 0

    
    history = []
    agent.inventory = []
    
    state = get_state(price, 0, window_size + 1)
    step_size = float(next(filter(lambda f: f['filterType'] == 'LOT_SIZE', client.get_symbol_info(cur_symbol)['filters']))['stepSize'])
    t = 2
    while True:
        mdata =  Real(cur_symbol)   
        #print(mdata)
        price.append(mdata)
        reward = 0
        next_state = get_state(price, t + 1 - 2, window_size + 1)


        # select an action
        action = agent.act(state, is_eval=True)

        # BUY
        if num_buys==buy_limit and len(agent.inventory) == 0:
            break

        if action == 1  and len(agent.inventory)<5 and num_buys<buy_limit:

            quantity[mdata] = floatPrecision((max_amount / (quantity_1 * mdata)),step_size)

            #client.order_market_buy(symbol=cur_symbol,quantity=quantity[mdata])
            agent.inventory.append(price[t])

            history.append((price[t], "BUY"))
            if debug:
                logging.debug("Buy at: {}".format(format_currency(price[t])))

            df2 = pd.DataFrame({'Datetime': [datetime.datetime.now(tz)], 'Symbol': [cur_symbol], 'Buy/Sell': ['Buy'],
                                            'Quantity': [quantity_1], 'Price': [mdata], 'Profit/loss': [total_profit]})
            df2['Datetime'] = df2['Datetime'].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'))
            if not os.path.isfile('5result.csv'):
                df2.to_csv('5result.csv', index=False)
            else:
                df2.to_csv('5result.csv', index=False, mode='a', header=False)

            max_amount += total_profit
            loss.append(total_profit)
            num_buys += 1


        
        # SELL
        #The fix
        elif (action == 2 and len(agent.inventory) > 0 ):
            bought_price = agent.inventory.pop(0)
            delta = price[t] - bought_price
            reward = delta #max(delta, 0)
            total_profit += delta
            quantity1 = quantity[bought_price]
            #client.order_market_sell(symbol=cur_symbol,quantity=quantity[bought_price])

            spent_amount -= float(quantity1) * bought_price;

            max_amount += total_profit
            loss.append(total_profit)

            df2 = pd.DataFrame({'Datetime': [datetime.datetime.now(tz)], 'Symbol': [cur_symbol], 'Buy/Sell': ['Sell'],
                                            'Quantity': [quantity_1], 'Price': [mdata], 'Profit/loss': [total_profit]})
            df2['Datetime'] = df2['Datetime'].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'))
            if not os.path.isfile('5result.csv'):
                df2.to_csv('5result.csv', index=False)
            else:
                df2.to_csv('5result.csv', index=False, mode='a', header=False)

            history.append((price[t], "SELL"))
            if debug:
                logging.debug("Sell at: {} | Position: {}".format(
                    format_currency(price[t]), format_position(price[t] - bought_price)))


        # HOLD
        else:
            history.append((price[t], "HOLD"))

        t += 1;
        done = True

        agent.memory.append((state, action, reward, next_state, done))

        state = next_state
        #time.sleep(1)
   
 
    return total_profit, history


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    warnings.filterwarnings("ignore", category=FutureWarning)
    parser.add_argument('ticker', help = 'ticker')
    args = parser.parse_args()
    
    coloredlogs.install(level="DEBUG")
    switch_k_backend_device()
    


    try:
        main(args)
    except KeyboardInterrupt:
        print("Aborted")    

