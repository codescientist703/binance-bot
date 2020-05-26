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

tz = pytz.timezone('Asia/Kolkata')
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def Real(url):
    uh = urllib.request.urlopen(url, context=ctx)
    data = uh.read().decode()
    info = json.loads(data)
    live = info['price'];
    time.sleep(1)
    return float(live) 


def main(args):
    price = []
    window_size =10
    time_now = datetime.datetime.now(tz).time()
    url = 'https://api.binance.com/api/v1/ticker/price?symbol={}'.format(args.ticker)
    live = Real(url)
    price.append(live)
    time.sleep(1)
    live = Real(url)
    price.append(live)
    model_name='model_double-dqn_GOOG_50_50'

    initial_offset = price[1] - price[0]

    agent = Agent(window_size, pretrained=True, model_name=model_name)
    profit, history = evaluate_model(agent, price, window_size, debug=True)
    show_eval_result(model_name, profit, initial_offset)
    print(history)
    

def evaluate_model(agent, price, window_size, debug):
    total_profit = 0
    t = 0
    
    history = []
    agent.inventory = []
    
    state = get_state(price, 0, window_size + 1)
    url = 'https://api.binance.com/api/v1/ticker/price?symbol=XMRUSDT'
    for t in range(40):
        mdata =  Real(url)   
        price.append(mdata)
        reward = 0
        next_state = get_state(price, t + 1, window_size + 1)
        
        # select an action
        action = agent.act(state, is_eval=True)

        # BUY
        if action == 1:
            agent.inventory.append(price[t])

            history.append((price[t], "BUY"))
            if debug:
                logging.debug("Buy at: {}".format(format_currency(price[t])))
        
        # SELL
        elif action == 2 and len(agent.inventory) > 0:
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

        done = (t == 39)

        agent.memory.append((state, action, reward, next_state, done))

        state = next_state
        #time.sleep(1)
 
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

