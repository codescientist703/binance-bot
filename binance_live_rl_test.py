import lxml.html as lh
import time
import urllib.request
import argparse
import urllib.request, urllib.parse, urllib.error
import datetime
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
    count = 0
    total_profit = 0
    t=0
    history = []
    reward = 0
    price = []
    window_size =1
    time_now = datetime.datetime.now(tz).time()
    url = 'https://api.binance.com/api/v1/ticker/price?symbol={}'.format(args.ticker)
    live = Real(url)
    price.append(live)
    time.sleep(1)
    live = Real(url)
    price.append(live)

    initial_offset = price[1] - price[0]
    while(count < 40):
        url = 'https://api.binance.com/api/v1/ticker/price?symbol={}'.format(args.ticker)
        live = Real(url)
        count+=1        
        price.append(live)
        if count < window_size:
           continue
        model_name='model_double-dqn_GOOG_50_50'  
        print(live)
        state = get_state(price, 0, window_size + 1)
        next_state = get_state(price, t + 1, window_size + 1)
        agent = Agent(state_size=window_size, pretrained=True, model_name=model_name)
        agent.inventory = []
        total_profit = evaluate_model(agent,state,next_state, price, t, total_profit, history, reward, window_size=window_size)
        #show_eval_result(model_name, profit, initial_offset)
        t+=1
        state = next_state
    show_eval_result(model_name, total_profit, initial_offset)
    print(history)

def evaluate_model(agent, state, next_state, data, t, total_profit, history, reward, window_size, debug=False):
  
    print(t)
        # select an action
    action = agent.act(state, is_eval=True)

        # BUY
    if action == 1:
        agent.inventory.append(data[t])

        history.append((data[t], "BUY"))
        if debug:
            logging.debug("Buy at: {}".format(format_currency(data[t])))

        # SELL
    elif action == 2 and len(agent.inventory) > 0:
        bought_price = agent.inventory.pop(0)
        delta = data[t] - bought_price
        reward = delta #max(delta, 0)
        total_profit += delta

        history.append((data[t], "SELL"))
        if debug:
            logging.debug("Sell at: {} | Position: {}".format(
                    format_currency(data[t]), format_position(data[t] - bought_price)))
        # HOLD
    else:
        history.append((data[t], "HOLD"))

#        done = (t == data_length - 1)
    agent.memory.append((state, action, reward, next_state))

    return total_profit

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

