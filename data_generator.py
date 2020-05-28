import pandas as pd
import time
import dateparser
import pytz
import argparse
from datetime import datetime
from binance.client import Client
import os
from binance.exceptions import BinanceAPIException
# import matplotlib.pyplot as plt
# import mpl_finance

api_key = "iZHsmlsCReb9S6zVO05Vxy8ONQYK8J3CfshgNiRh3HlRShPULMj8EYBClftHBqi1"
api_secret = "4IHk54oeSmmoXGQqWNgi24SJ1uHaTSEBfN48nOhYex8ATFFOj2WoWZQfDFD0pzu1"

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
	#print(klines[-1])
	ochl = []
	for kline in klines:
		time1 = int(kline[0])
		open1 = float(kline[1])
		high = float(kline[2])
		low = float(kline[3])
		close = float(kline[4])
		volume = float(kline[5])
		ochl.append({'Date': time1,'Open':open1, 'Close':close,'High': high,'Low': low,'Volume': volume})
	#print(ochl[-1])
	'''
	fig, ax = plt.subplots()
	mpl_finance.candlestick_ochl(ax, ochl, width=1)
	ax.set(xlabel='Date', ylabel='Price', title='{} {}-{}'.format(symbol, start, end))
	plt.show(block=False)
	plt.pause(3)
	plt.close()
	'''
	return ochl


def generate(symbol):
	#list_of_symbols = ['XMRUSDT', 'LINKUSDT', 'LTCUSDT', 'BNBUSDT', 'EOSUSDT', 'BCHUSDT', 'BTCUSDT', 'ETHUSDT', 'XRPUSDT']  # Symbols to be traded
	
	client.get_deposit_address(asset='USDT')  # USDT or BTC

	#for symbol in list_of_symbols:

	data = get_historic_klines(symbol, "48 hours ago  UTC", "now UTC", Client.KLINE_INTERVAL_30MINUTE)
	df = pd.DataFrame(data)

	for i in df.index:
		mil_time = int(df.at[i,'Date'])
		df.at[i,'Date'] = datetime.fromtimestamp(mil_time/1000.0).date()

	path = 'training_data/' + symbol + '.csv'

	df.to_csv(path, index=False)

			


