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

from quick_train import quick_train

tz = pytz.timezone('Asia/Kolkata')


api_key = "JB80jU6aTMYXcLapXKPc2Rmnn12CUcm3l7RlnYAT7w8esCFAKYOTmd4bAMWxB33U"
api_secret = "FsbKTSb7lCGLpQWoBad9Jobe8xpi177c2KrQ6Q31e86dUA5WgUqaliqHsILk7n5s"
client = Client(api_key, api_secret)
client.get_deposit_address(asset='USDT')

cur_symbol = 'XMRUSDT'


def Real():
    live = float(client.get_symbol_ticker(symbol = cur_symbol)['price']);
    time.sleep(1)
    return live


def main(args):
    price = []
    global cur_symbol
    cur_symbol = args.ticker

    quick_train(cur_symbol)
    window_size =10
    time_now = datetime.datetime.now(tz).time()

    for c in range(2):
        price.append(Real())

    model_name='model_double-dqn_GOOG_50_50'

    initial_offset = price[1] - price[0]

    agent = Agent(window_size, pretrained=True, model_name=model_name)
    profit, history = evaluate_model(agent, price, window_size, debug=True)
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

#--------------------------------------------------------------
    

def evaluate_model(agent, price, window_size, debug):
    total_profit = 0
    t = 0
    
    history = []
    agent.inventory = []
    
    state = get_state(price, 0, window_size + 1)

    for t in range(2,100):
        mdata =  Real()   
        print(mdata)
        price.append(mdata)
        reward = 0
        next_state = get_state(price, t + 1 - 2, window_size + 1)
        
        # select an action
        action = agent.act(state, is_eval=True)

        # BUY
        if action == 1:
            agent.inventory.append(price[t])

            history.append((price[t], "BUY"))
            if debug:
                logging.debug("Buy at: {}".format(format_currency(price[t])))
        
        # SELL
        #The fix
        elif (action == 2 and len(agent.inventory) > 0 ):
            bought_price = agent.inventory.pop(0)
            delta = price[t] - bought_price
            reward = delta #max(delta, 0)
            total_profit += delta

            history.append((price[t], "SELL"))
            if debug:
                logging.debug("Sell at: {} | Position: {}".format(
                    format_currency(price[t]), format_position(price[t] - bought_price)))


        # HOLD
        else:
            history.append((price[t], "HOLD"))

        
        done = True

        agent.memory.append((state, action, reward, next_state, done))

        state = next_state
        #time.sleep(1)
   
    print(len(agent.inventory))
 
    return total_profit, history


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('ticker', help = 'ticker')
    args = parser.parse_args()

    coloredlogs.install(level="DEBUG")
    switch_k_backend_device()
    


    try:
        main(args)
    except KeyboardInterrupt:
        print("Aborted")    

